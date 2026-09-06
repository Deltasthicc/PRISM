"""
Lane 4 (Content AI & Voice) — Local Piper English TTS.

Provides offline, sentence-incremental speech synthesis using local Piper TTS.
Audio is generated strictly in-memory with zero raw audio persistence or temporary files.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import threading
import time
from typing import Any, Iterator

# Default text and audio parameters
DEFAULT_MAX_TEXT_LENGTH = 2000  # Characters
DEFAULT_SAMPLE_RATE = 22050     # Standard Piper medium voice sample rate in Hz
DEFAULT_CHANNELS = 1            # Mono
DEFAULT_SAMPLE_WIDTH = 2        # 16-bit PCM (2 bytes per sample)


@dataclass(frozen=True)
class TTSChunk:
    """An incremental audio chunk synthesized for a single sentence."""
    audio: bytes
    sample_rate: int
    channels: int
    sample_width: int
    duration_ms: float
    chunk_index: int
    time_to_chunk_ms: float
    generation_id: int = 0


@dataclass(frozen=True)
class TTSResult:
    """Complete synthesized audio result with latency metrics."""
    audio: bytes
    sample_rate: int
    channels: int
    sample_width: int
    duration_ms: float
    processing_time_ms: float
    time_to_first_audio_ms: float


class LocalPiperTTS:
    """Lazy-loaded, thread-safe text-to-speech engine wrapping local Piper TTS.

    Separates the software runtime (installed piper-tts package) from the
    voice model asset (configurable path/env var, no automatic downloads).
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        config_path: str | Path | None = None,
        voice_instance: Any | None = None,
        max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
    ) -> None:
        self.model_path = Path(model_path) if model_path else None
        self.config_path = Path(config_path) if config_path else None
        self.max_text_length = max_text_length
        self._voice = voice_instance
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        """Whether the underlying PiperVoice model instance is currently loaded in RAM."""
        return self._voice is not None

    @property
    def is_model_available(self) -> bool:
        """Whether a valid Piper voice model asset is configured and exists locally on disk."""
        if self._voice is not None:
            return True
        path = self._resolve_model_path()
        return path is not None and path.is_file()

    def _resolve_model_path(self) -> Path | None:
        if self.model_path:
            return self.model_path
        env_path = os.getenv("PIPER_MODEL_PATH")
        if env_path:
            return Path(env_path)
        return None

    def _resolve_config_path(self, model_path: Path) -> Path | None:
        if self.config_path and self.config_path.is_file():
            return self.config_path
        env_config = os.getenv("PIPER_CONFIG_PATH")
        if env_config and Path(env_config).is_file():
            return Path(env_config)
        # Default Piper convention: <model>.onnx.json
        candidate = Path(str(model_path) + ".json")
        if candidate.is_file():
            return candidate
        return None

    def _ensure_voice(self) -> Any:
        """Load the Piper voice model on first demand in a thread-safe manner."""
        if self._voice is None:
            with self._lock:
                if self._voice is None:
                    model_path = self._resolve_model_path()
                    if not model_path or not model_path.is_file():
                        raise FileNotFoundError(
                            f"Piper voice model not found at '{model_path}'. "
                            "A local Piper voice model (.onnx) must be explicitly configured "
                            "via constructor argument or PIPER_MODEL_PATH environment variable."
                        )

                    config_path = self._resolve_config_path(model_path)
                    from piper import PiperVoice

                    self._voice = PiperVoice.load(
                        model_path=model_path,
                        config_path=config_path,
                    )
        return self._voice

    def _validate_text(self, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError(f"Input text must be a string, got {type(text).__name__}")
        if len(text) > self.max_text_length:
            raise ValueError(
                f"Input text length ({len(text)} chars) exceeds maximum allowed limit "
                f"of {self.max_text_length} characters."
            )
        return text.strip()

    def synthesize_stream(
        self,
        text: str,
        generation_id: int = 0,
        cancellation_token: Any | None = None,
    ) -> Iterator[TTSChunk]:
        """Progressively synthesize text sentence-by-sentence into incremental audio chunks.

        Yields TTSChunk objects as sentences complete, enabling low time-to-first-audio.
        Terminates synthesis immediately if cancellation_token is set.
        """
        cleaned_text = self._validate_text(text)
        if not cleaned_text:
            return

        voice = self._ensure_voice()

        def _is_cancelled() -> bool:
            if cancellation_token is None:
                return False
            check = getattr(cancellation_token, "is_set", None)
            if callable(check):
                return bool(check())
            return bool(cancellation_token)

        with self._lock:
            t_start = time.perf_counter()
            chunk_index = 0

            # PiperVoice.synthesize yields one AudioChunk per sentence
            for chunk in voice.synthesize(cleaned_text):
                if _is_cancelled():
                    break

                t_now = time.perf_counter()
                time_to_chunk_ms = (t_now - t_start) * 1000.0

                raw_bytes = chunk.audio_int16_bytes
                sample_rate = int(chunk.sample_rate)
                channels = int(chunk.sample_channels)
                sample_width = int(chunk.sample_width)

                bytes_per_sample = channels * sample_width
                num_samples = len(raw_bytes) // bytes_per_sample if bytes_per_sample > 0 else 0
                duration_ms = (num_samples / sample_rate * 1000.0) if sample_rate > 0 else 0.0

                yield TTSChunk(
                    audio=raw_bytes,
                    sample_rate=sample_rate,
                    channels=channels,
                    sample_width=sample_width,
                    duration_ms=round(duration_ms, 2),
                    chunk_index=chunk_index,
                    time_to_chunk_ms=round(time_to_chunk_ms, 2),
                    generation_id=generation_id,
                )
                chunk_index += 1

    def synthesize(
        self,
        text: str,
        generation_id: int = 0,
        cancellation_token: Any | None = None,
    ) -> TTSResult:
        """Synthesize text into complete raw PCM audio with duration and latency metrics."""
        cleaned_text = self._validate_text(text)
        if not cleaned_text:
            return TTSResult(
                audio=b"",
                sample_rate=DEFAULT_SAMPLE_RATE,
                channels=DEFAULT_CHANNELS,
                sample_width=DEFAULT_SAMPLE_WIDTH,
                duration_ms=0.0,
                processing_time_ms=0.0,
                time_to_first_audio_ms=0.0,
            )

        t_start = time.perf_counter()
        audio_buffers: list[bytes] = []
        sample_rate = DEFAULT_SAMPLE_RATE
        channels = DEFAULT_CHANNELS
        sample_width = DEFAULT_SAMPLE_WIDTH
        time_to_first_audio_ms = 0.0

        for chunk in self.synthesize_stream(
            cleaned_text,
            generation_id=generation_id,
            cancellation_token=cancellation_token,
        ):
            if not audio_buffers:
                time_to_first_audio_ms = chunk.time_to_chunk_ms
                sample_rate = chunk.sample_rate
                channels = chunk.channels
                sample_width = chunk.sample_width
            audio_buffers.append(chunk.audio)

        t_end = time.perf_counter()
        processing_time_ms = (t_end - t_start) * 1000.0

        full_audio = b"".join(audio_buffers)
        bytes_per_sample = channels * sample_width
        num_samples = len(full_audio) // bytes_per_sample if bytes_per_sample > 0 else 0
        duration_ms = (num_samples / sample_rate * 1000.0) if sample_rate > 0 else 0.0

        return TTSResult(
            audio=full_audio,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            duration_ms=round(duration_ms, 2),
            processing_time_ms=round(processing_time_ms, 2),
            time_to_first_audio_ms=round(time_to_first_audio_ms, 2),
        )

    async def synthesize_async(self, text: str) -> TTSResult:
        """Asynchronously synthesize text in a background worker thread."""
        return await asyncio.to_thread(self.synthesize, text)


_singleton_lock = threading.Lock()
_singleton_tts_engine: LocalPiperTTS | None = None


def get_tts_engine() -> LocalPiperTTS:
    """Return the process-wide shared LocalPiperTTS singleton instance."""
    global _singleton_tts_engine
    if _singleton_tts_engine is None:
        with _singleton_lock:
            if _singleton_tts_engine is None:
                _singleton_tts_engine = LocalPiperTTS()
    return _singleton_tts_engine
