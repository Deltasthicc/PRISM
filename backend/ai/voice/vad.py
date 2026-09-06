"""
Lane 4 (Content AI & Voice) — Local Voice Activity Detection (VAD).

Provides streaming VAD for 16 kHz mono 16-bit PCM audio using the bundled
Silero VAD v6 ONNX model via faster-whisper.
Audio is processed strictly in-memory with zero raw audio persistence.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Protocol, Sequence
import numpy as np

# Audio format constants
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2  # 16-bit signed integer (PCM16 little-endian)
FRAME_SAMPLES = 512   # 32ms at 16kHz (Silero VAD v6 native chunk size)
FRAME_BYTES = FRAME_SAMPLES * BYTES_PER_SAMPLE  # 1024 bytes per frame

# Threshold defaults with operational rationale:
DEFAULT_SPEECH_THRESHOLD = 0.50
# 3 consecutive frames (3 * 32ms = 96ms) of speech probability >= threshold
# required to transition IDLE -> SPEECH. Prevents false triggers on keyboard clicks,
# mic pops, and brief transient ambient noise.
DEFAULT_MIN_SPEECH_FRAMES = 3

# 16 consecutive frames (16 * 32ms = 512ms) of silence probability required to
# transition SPEECH -> IDLE. Provides conversational hangover so inter-word pauses
# within a single utterance do not prematurely cut off the speaker.
DEFAULT_MIN_SILENCE_FRAMES = 16

# 5 frames (5 * 32ms = 160ms) of pre-speech audio maintained in a FIFO ring buffer.
# When speech onset is confirmed, these pre-speech frames are prepended to ensure
# unvoiced or low-energy onset consonants ('p', 't', 'k', 's') are preserved for STT.
DEFAULT_PRE_SPEECH_FRAMES = 5


class VADState(str, Enum):
    """Lifecycle states of the VAD stream."""
    IDLE = "idle"
    SPEECH = "speech"


class VADEventType(str, Enum):
    """Explicit events emitted by the VAD state machine."""
    NONE = "none"
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"


@dataclass(frozen=True)
class VADEvent:
    """An event emitted during VAD processing."""
    event_type: VADEventType
    state: VADState
    speech_probability: float
    frame_index: int
    timestamp_ms: float
    audio: bytes = b""


class VADModelProtocol(Protocol):
    """Protocol for pluggable VAD frame scoring models."""
    def predict_frame(self, frame_bytes: bytes) -> float:
        ...

    def reset(self) -> None:
        ...


class SileroVADDetector:
    """Wraps faster-whisper's bundled Silero VAD v6 ONNX model.

    Maintains recurrent hidden states (h, c) and context window across
    streaming 512-sample frames for accurate online inference.
    """

    def __init__(self, model: Any | None = None) -> None:
        if model is None:
            from faster_whisper.vad import get_vad_model
            self._model = get_vad_model()
        else:
            self._model = model

        self._session = getattr(self._model, "session", None)
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)

    def reset(self) -> None:
        """Reset internal recurrent states between sessions or utterances."""
        self._h.fill(0.0)
        self._c.fill(0.0)
        self._context.fill(0.0)

    def predict_frame(self, frame_bytes: bytes) -> float:
        """Score a 512-sample 16-bit PCM frame, returning speech probability in [0, 1]."""
        if len(frame_bytes) != FRAME_BYTES:
            raise ValueError(
                f"Expected {FRAME_BYTES} bytes ({FRAME_SAMPLES} samples), got {len(frame_bytes)}"
            )

        pcm16 = np.frombuffer(frame_bytes, dtype=np.int16)
        # Normalize int16 [-32768, 32767] to float32 [-1.0, 1.0]
        pcm_float = (pcm16.astype(np.float32) / 32768.0).reshape(1, FRAME_SAMPLES)

        if self._session is not None:
            # 576-sample tensor = 64 context samples + 512 frame samples
            model_input = np.concatenate([self._context, pcm_float], axis=1)
            outputs = self._session.run(
                None,
                {"input": model_input, "h": self._h, "c": self._c},
            )
            # outputs: [speech_probs, hn, cn]
            prob = float(outputs[0][0])
            self._h = outputs[1]
            self._c = outputs[2]
            self._context = pcm_float[:, -64:]
            return prob
        else:
            # Fallback to model __call__ if custom wrapper
            out = self._model(pcm_float.flatten(), num_samples=FRAME_SAMPLES)
            return float(out[0])


class VoiceActivityDetector:
    """Stream processor that ingests raw PCM16 audio bytes and emits VAD events.

    Maintains in-memory audio buffers, handles arbitrary byte chunk boundaries,
    and applies hangover and onset thresholds for natural turn-taking.
    """

    def __init__(
        self,
        model: VADModelProtocol | Callable[[bytes], float] | None = None,
        speech_threshold: float = DEFAULT_SPEECH_THRESHOLD,
        min_speech_frames: int = DEFAULT_MIN_SPEECH_FRAMES,
        min_silence_frames: int = DEFAULT_MIN_SILENCE_FRAMES,
        pre_speech_frames: int = DEFAULT_PRE_SPEECH_FRAMES,
    ) -> None:
        if model is None:
            self._model: VADModelProtocol | Callable[[bytes], float] = SileroVADDetector()
        else:
            self._model = model

        self.speech_threshold = speech_threshold
        self.min_speech_frames = max(1, min_speech_frames)
        self.min_silence_frames = max(1, min_silence_frames)
        self.pre_speech_frames = max(0, pre_speech_frames)

        # In-memory byte buffer for incomplete frames
        self._byte_buffer = bytearray()

        # In-memory ring buffer for pre-speech frames
        self._pre_speech_buffer: collections.deque[bytes] = collections.deque(
            maxlen=self.pre_speech_frames
        )

        # In-memory speech accumulator
        self._speech_buffer = bytearray()

        # State machine variables
        self._state = VADState.IDLE
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._frame_index = 0

    @property
    def state(self) -> VADState:
        """Current state of the detector: IDLE or SPEECH."""
        return self._state

    @property
    def frame_index(self) -> int:
        """Total number of full 512-sample frames processed so far."""
        return self._frame_index

    @property
    def timestamp_ms(self) -> float:
        """Current stream timeline in milliseconds."""
        return (self._frame_index * FRAME_SAMPLES / SAMPLE_RATE) * 1000.0

    def reset(self) -> None:
        """Reset all state machine variables, buffers, and model states."""
        self._byte_buffer.clear()
        self._pre_speech_buffer.clear()
        self._speech_buffer.clear()
        self._state = VADState.IDLE
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._frame_index = 0

        if hasattr(self._model, "reset") and callable(self._model.reset):
            self._model.reset()

    def process_bytes(self, chunk: bytes) -> list[VADEvent]:
        """Ingest an arbitrary slice of PCM16 bytes and return any emitted VAD events.

        Slices input into 1024-byte (512-sample / 32ms) frames. Any leftover
        bytes remain buffered until subsequent calls.
        """
        if not chunk:
            return []

        self._byte_buffer.extend(chunk)
        events: list[VADEvent] = []

        while len(self._byte_buffer) >= FRAME_BYTES:
            frame = bytes(self._byte_buffer[:FRAME_BYTES])
            del self._byte_buffer[:FRAME_BYTES]

            event = self._process_frame(frame)
            if event.event_type != VADEventType.NONE:
                events.append(event)

        return events

    def flush(self) -> list[VADEvent]:
        """Force-close any in-flight speech segment and return final events.

        Emits SPEECH_END if currently in SPEECH state with all accumulated audio.
        """
        events: list[VADEvent] = []
        if self._state == VADState.SPEECH and len(self._speech_buffer) > 0:
            audio_payload = bytes(self._speech_buffer)
            self._speech_buffer.clear()
            self._pre_speech_buffer.clear()
            self._state = VADState.IDLE
            self._consecutive_speech_frames = 0
            self._consecutive_silence_frames = 0

            events.append(
                VADEvent(
                    event_type=VADEventType.SPEECH_END,
                    state=VADState.IDLE,
                    speech_probability=0.0,
                    frame_index=self._frame_index,
                    timestamp_ms=self.timestamp_ms,
                    audio=audio_payload,
                )
            )

        # Discard any incomplete trailing frame bytes
        self._byte_buffer.clear()
        return events

    def _score_frame(self, frame: bytes) -> float:
        if hasattr(self._model, "predict_frame"):
            return float(self._model.predict_frame(frame))
        return float(self._model(frame))

    def _process_frame(self, frame: bytes) -> VADEvent:
        self._frame_index += 1
        current_time_ms = self.timestamp_ms
        prob = self._score_frame(frame)
        is_speech = prob >= self.speech_threshold

        if self._state == VADState.IDLE:
            self._pre_speech_buffer.append(frame)

            if is_speech:
                self._consecutive_speech_frames += 1
                if self._consecutive_speech_frames >= self.min_speech_frames:
                    # Transition IDLE -> SPEECH
                    self._state = VADState.SPEECH
                    self._consecutive_silence_frames = 0

                    # Seed speech buffer with pre-speech context (leading consonants)
                    self._speech_buffer.clear()
                    for pre_frame in self._pre_speech_buffer:
                        self._speech_buffer.extend(pre_frame)

                    return VADEvent(
                        event_type=VADEventType.SPEECH_START,
                        state=VADState.SPEECH,
                        speech_probability=prob,
                        frame_index=self._frame_index,
                        timestamp_ms=current_time_ms,
                        audio=bytes(self._speech_buffer),
                    )
            else:
                self._consecutive_speech_frames = 0

            return VADEvent(
                event_type=VADEventType.NONE,
                state=VADState.IDLE,
                speech_probability=prob,
                frame_index=self._frame_index,
                timestamp_ms=current_time_ms,
            )

        else:  # self._state == VADState.SPEECH
            self._speech_buffer.extend(frame)

            if is_speech:
                self._consecutive_silence_frames = 0
                return VADEvent(
                    event_type=VADEventType.NONE,
                    state=VADState.SPEECH,
                    speech_probability=prob,
                    frame_index=self._frame_index,
                    timestamp_ms=current_time_ms,
                )
            else:
                self._consecutive_silence_frames += 1
                if self._consecutive_silence_frames >= self.min_silence_frames:
                    # Transition SPEECH -> IDLE
                    self._state = VADState.IDLE
                    audio_payload = bytes(self._speech_buffer)
                    self._speech_buffer.clear()
                    self._pre_speech_buffer.clear()
                    self._consecutive_speech_frames = 0
                    self._consecutive_silence_frames = 0

                    return VADEvent(
                        event_type=VADEventType.SPEECH_END,
                        state=VADState.IDLE,
                        speech_probability=prob,
                        frame_index=self._frame_index,
                        timestamp_ms=current_time_ms,
                        audio=audio_payload,
                    )

                return VADEvent(
                    event_type=VADEventType.NONE,
                    state=VADState.SPEECH,
                    speech_probability=prob,
                    frame_index=self._frame_index,
                    timestamp_ms=current_time_ms,
                )
