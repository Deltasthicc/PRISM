"""
Lane 4 (Content AI & Voice) — Local Faster-Whisper tiny.en STT.

Provides offline, CPU-quantized (int8) speech-to-text transcription for 16 kHz
mono 16-bit PCM audio using faster-whisper.
Audio is processed strictly in-memory (no raw audio persistence or temporary files).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import threading
import time
from typing import Any
import numpy as np

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2  # 16-bit signed PCM

DEFAULT_MODEL_SIZE = "tiny.en"
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE_TYPE = "int8"


@dataclass(frozen=True)
class TranscriptionResult:
    """Structured transcription result with duration and latency metrics."""
    text: str
    duration_ms: float
    processing_time_ms: float
    real_time_factor: float


class FasterWhisperSTT:
    """Lazy-loaded, thread-safe speech-to-text engine wrapping faster-whisper tiny.en."""

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = DEFAULT_DEVICE,
        compute_type: str = DEFAULT_COMPUTE_TYPE,
        model_instance: Any | None = None,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = model_instance
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        """Whether the underlying Whisper model is currently loaded in memory."""
        return self._model is not None

    def _ensure_model(self) -> Any:
        """Load the model on first demand in a thread-safe manner."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from faster_whisper import WhisperModel
                    self._model = WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
        return self._model

    def transcribe(
        self,
        pcm_bytes: bytes,
        sample_rate: int = SAMPLE_RATE,
    ) -> TranscriptionResult:
        """Transcribe in-memory 16 kHz mono PCM16 audio bytes.

        Args:
            pcm_bytes: 16-bit signed little-endian PCM audio bytes.
            sample_rate: Audio sample rate. Must be exactly 16000 Hz.

        Returns:
            TranscriptionResult with transcribed text and latency metrics.

        Raises:
            ValueError: If sample_rate is not 16000 or pcm_bytes length is odd.
        """
        if sample_rate != SAMPLE_RATE:
            raise ValueError(
                f"Unsupported sample rate: {sample_rate} Hz. "
                f"FasterWhisperSTT strictly requires {SAMPLE_RATE} Hz mono PCM16."
            )

        if len(pcm_bytes) % BYTES_PER_SAMPLE != 0:
            raise ValueError(
                f"Invalid PCM16 byte length: {len(pcm_bytes)} bytes is not a multiple of "
                f"{BYTES_PER_SAMPLE} bytes per sample."
            )

        num_samples = len(pcm_bytes) // BYTES_PER_SAMPLE
        duration_ms = (num_samples / SAMPLE_RATE) * 1000.0

        if num_samples == 0:
            return TranscriptionResult(
                text="",
                duration_ms=0.0,
                processing_time_ms=0.0,
                real_time_factor=0.0,
            )

        # Convert in-memory PCM16 buffer to normalized float32 numpy array [-1.0, 1.0]
        pcm16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        audio_float = pcm16.astype(np.float32) / 32768.0

        model = self._ensure_model()

        t_start = time.perf_counter()
        segments, _ = model.transcribe(
            audio_float,
            language="en",
            task="transcribe",
            beam_size=1,
            vad_filter=False,
            word_timestamps=False,
        )
        # Collect text from segments
        transcribed_text = " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
        t_end = time.perf_counter()

        processing_time_ms = (t_end - t_start) * 1000.0
        rtf = (processing_time_ms / duration_ms) if duration_ms > 0 else 0.0

        return TranscriptionResult(
            text=transcribed_text,
            duration_ms=round(duration_ms, 2),
            processing_time_ms=round(processing_time_ms, 2),
            real_time_factor=round(rtf, 4),
        )

    async def transcribe_async(
        self,
        pcm_bytes: bytes,
        sample_rate: int = SAMPLE_RATE,
    ) -> TranscriptionResult:
        """Asynchronously transcribe PCM audio in a background worker thread."""
        return await asyncio.to_thread(self.transcribe, pcm_bytes, sample_rate)


_singleton_lock = threading.Lock()
_singleton_engine: FasterWhisperSTT | None = None


def get_stt_engine() -> FasterWhisperSTT:
    """Return the process-wide shared FasterWhisperSTT singleton instance."""
    global _singleton_engine
    if _singleton_engine is None:
        with _singleton_lock:
            if _singleton_engine is None:
                _singleton_engine = FasterWhisperSTT()
    return _singleton_engine
