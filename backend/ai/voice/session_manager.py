"""
Lane 4 (Content AI & Voice) — In-Process Voice Session Manager.

Coordinates the in-process pipeline:
  PCM audio -> Faster-Whisper STT -> Context Manager -> Lane 4 Assistant -> Piper TTS.
Enforces access contexts, preserves citations, streams TTS sentence chunks,
implements barge-in cancellation and generation IDs, and instruments latency.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable

from ai.assistant import LearnerAssistant, default_assistant
from ai.provenance import AccessContext, AssistantResponse, AssistantResponseStatus
from ai.voice.context import ConversationContextManager
from ai.voice.stt import FasterWhisperSTT, TranscriptionResult, get_stt_engine
from ai.voice.tts import LocalPiperTTS, TTSChunk, TTSResult, get_tts_engine
from ai.voice.vad import VADEventType, VoiceActivityDetector


class SessionState(str, Enum):
    """High-level lifecycle state of the conversational voice session."""
    LISTENING = "listening"      # Awaiting learner speech input
    PROCESSING = "processing"    # Transcribing or executing RAG assistant
    SPEAKING = "speaking"        # Synthesizing and streaming TTS audio response
    INTERRUPTING = "interrupting"  # Barge-in detected, halting current generation


class VoiceTurnStatus(str, Enum):
    """Execution status of an in-process voice turn."""
    SUCCESS = "success"
    NO_SPEECH = "no_speech"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PROMPT_INJECTION_DETECTED = "prompt_injection_detected"
    STT_FAILURE = "stt_failure"
    ASSISTANT_FAILURE = "assistant_failure"
    TTS_FAILURE = "tts_failure"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class VoiceTurnTiming:
    """Latency breakdown for the conversational voice turn."""
    stt_duration_ms: float
    assistant_duration_ms: float
    tts_time_to_first_audio_ms: float
    tts_total_duration_ms: float
    total_speech_end_to_first_audio_ms: float
    total_turn_duration_ms: float
    cancellation_latency_ms: float = 0.0


def _zero_timing() -> VoiceTurnTiming:
    return VoiceTurnTiming(
        stt_duration_ms=0.0,
        assistant_duration_ms=0.0,
        tts_time_to_first_audio_ms=0.0,
        tts_total_duration_ms=0.0,
        total_speech_end_to_first_audio_ms=0.0,
        total_turn_duration_ms=0.0,
        cancellation_latency_ms=0.0,
    )


@dataclass(frozen=True)
class VoiceTurnResult:
    """Structured result of a voice session turn with provenance, timing, and generation ID."""
    turn_index: int
    status: VoiceTurnStatus
    transcript: str
    assistant_response: AssistantResponse | None
    tts_result: TTSResult | None
    timing: VoiceTurnTiming
    citations: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None
    generation_id: int = 0


class VoiceSessionManager:
    """In-process voice session coordinator connecting STT, Context, RAG Assistant, and TTS.

    Features generation ID tracking and cooperative cancellation for natural barge-in.
    """

    def __init__(
        self,
        stt_engine: FasterWhisperSTT | None = None,
        assistant: LearnerAssistant | None = None,
        tts_engine: LocalPiperTTS | None = None,
        context_manager: ConversationContextManager | None = None,
    ) -> None:
        self.stt_engine = stt_engine or get_stt_engine()
        self.assistant = assistant or default_assistant
        self.tts_engine = tts_engine or get_tts_engine()
        self.context_manager = context_manager or ConversationContextManager()

        self._turn_index = 0
        self._generation_counter = 0
        self._active_generation_id = 0
        self._session_state = SessionState.LISTENING
        self._active_cancellation_token: asyncio.Event | None = None
        self._cancellation_request_time: float | None = None

    @property
    def turn_index(self) -> int:
        return self._turn_index

    @property
    def generation_id(self) -> int:
        return self._active_generation_id

    @property
    def session_state(self) -> SessionState:
        return self._session_state

    def reset(self) -> None:
        """Reset session turn count and clear conversational context."""
        self._turn_index = 0
        self._generation_counter = 0
        self._active_generation_id = 0
        self._session_state = SessionState.LISTENING
        self._active_cancellation_token = None
        self._cancellation_request_time = None
        self.context_manager.clear()

    def cancel_current_turn(self, reason: str = "barge_in") -> None:
        """Cooperatively cancel the currently in-flight turn/generation immediately."""
        self._cancellation_request_time = time.perf_counter()
        if self._active_cancellation_token is not None:
            self._active_cancellation_token.set()

        if self._session_state in (SessionState.PROCESSING, SessionState.SPEAKING):
            self._session_state = SessionState.INTERRUPTING

    def handle_barge_in_pcm(
        self,
        frame_bytes: bytes,
        vad_detector: VoiceActivityDetector,
    ) -> bool:
        """Evaluate incoming audio frame through VAD while the assistant is in SPEAKING state.

        If a reliable speech onset (SPEECH_START) is detected with onset debounce,
        triggers cancellation immediately without waiting for speech completion.
        Returns True if barge-in was triggered, False otherwise.
        """
        if self._session_state != SessionState.SPEAKING:
            return False

        events = vad_detector.process_bytes(frame_bytes)
        for ev in events:
            if ev.event_type == VADEventType.SPEECH_START:
                self.cancel_current_turn(reason="barge_in_speech_onset")
                self._session_state = SessionState.LISTENING
                return True
        return False

    async def process_turn(
        self,
        pcm_bytes: bytes,
        access_context: AccessContext,
        source_id: str | None = None,
        top_k: int = 3,
        threshold: float = 0.20,
        on_tts_chunk: Callable[[TTSChunk], Any] | None = None,
        on_transcript: Callable[[TranscriptionResult], Any] | None = None,
        on_assistant: Callable[[AssistantResponse], Any] | None = None,
        cancellation_token: asyncio.Event | None = None,
    ) -> VoiceTurnResult:
        """Process finalized PCM audio through STT, Assistant, and TTS with cancellation support."""
        t0 = time.perf_counter()  # Intake / speech_end timestamp

        self._generation_counter += 1
        current_gen_id = self._generation_counter
        self._active_generation_id = current_gen_id
        self._turn_index = current_gen_id
        self._session_state = SessionState.PROCESSING

        # Cooperative cancellation token for this turn
        turn_cancel_tok = cancellation_token or asyncio.Event()
        self._active_cancellation_token = turn_cancel_tok
        self._cancellation_request_time = None

        def _is_cancelled() -> bool:
            return turn_cancel_tok.is_set() or self._active_generation_id != current_gen_id

        def _calc_cancel_latency(t_now: float) -> float:
            if self._cancellation_request_time is not None:
                return (t_now - self._cancellation_request_time) * 1000.0
            return 0.0

        if _is_cancelled():
            t_now = time.perf_counter()
            self._session_state = SessionState.LISTENING
            return VoiceTurnResult(
                turn_index=current_gen_id,
                generation_id=current_gen_id,
                status=VoiceTurnStatus.CANCELLED,
                transcript="",
                assistant_response=None,
                tts_result=None,
                timing=VoiceTurnTiming(
                    stt_duration_ms=0.0,
                    assistant_duration_ms=0.0,
                    tts_time_to_first_audio_ms=0.0,
                    tts_total_duration_ms=0.0,
                    total_speech_end_to_first_audio_ms=0.0,
                    total_turn_duration_ms=round((t_now - t0) * 1000.0, 2),
                    cancellation_latency_ms=round(_calc_cancel_latency(t_now), 2),
                ),
                error_message="Turn cancelled before STT execution.",
            )

        # ─── 1. Speech-to-Text ───────────────────────────────────────────────
        try:
            stt_result: TranscriptionResult = await self.stt_engine.transcribe_async(pcm_bytes)
        except Exception as exc:
            t_now = time.perf_counter()
            self._session_state = SessionState.LISTENING
            return VoiceTurnResult(
                turn_index=current_gen_id,
                generation_id=current_gen_id,
                status=VoiceTurnStatus.STT_FAILURE,
                transcript="",
                assistant_response=None,
                tts_result=None,
                timing=VoiceTurnTiming(
                    stt_duration_ms=round((t_now - t0) * 1000.0, 2),
                    assistant_duration_ms=0.0,
                    tts_time_to_first_audio_ms=0.0,
                    tts_total_duration_ms=0.0,
                    total_speech_end_to_first_audio_ms=0.0,
                    total_turn_duration_ms=round((t_now - t0) * 1000.0, 2),
                ),
                error_message=f"STT transcription failed: {exc}",
            )

        t_stt_done = time.perf_counter()
        stt_duration_ms = (t_stt_done - t0) * 1000.0
        transcript_text = stt_result.text.strip()

        if _is_cancelled():
            t_now = time.perf_counter()
            self._session_state = SessionState.LISTENING
            return VoiceTurnResult(
                turn_index=current_gen_id,
                generation_id=current_gen_id,
                status=VoiceTurnStatus.CANCELLED,
                transcript=transcript_text,
                assistant_response=None,
                tts_result=None,
                timing=VoiceTurnTiming(
                    stt_duration_ms=round(stt_duration_ms, 2),
                    assistant_duration_ms=0.0,
                    tts_time_to_first_audio_ms=0.0,
                    tts_total_duration_ms=0.0,
                    total_speech_end_to_first_audio_ms=0.0,
                    total_turn_duration_ms=round((t_now - t0) * 1000.0, 2),
                    cancellation_latency_ms=round(_calc_cancel_latency(t_now), 2),
                ),
                error_message="Turn cancelled after STT completion.",
            )

        # Stop early on empty transcript without calling Assistant or TTS
        if not transcript_text:
            self._session_state = SessionState.LISTENING
            return VoiceTurnResult(
                turn_index=current_gen_id,
                generation_id=current_gen_id,
                status=VoiceTurnStatus.NO_SPEECH,
                transcript="",
                assistant_response=None,
                tts_result=None,
                timing=VoiceTurnTiming(
                    stt_duration_ms=round(stt_duration_ms, 2),
                    assistant_duration_ms=0.0,
                    tts_time_to_first_audio_ms=0.0,
                    tts_total_duration_ms=0.0,
                    total_speech_end_to_first_audio_ms=0.0,
                    total_turn_duration_ms=round(stt_duration_ms, 2),
                ),
            )

        if on_transcript:
            cb_res = on_transcript(stt_result)
            if asyncio.iscoroutine(cb_res):
                await cb_res

        # ─── 2. Assistant / RAG ──────────────────────────────────────────────
        if _is_cancelled():
            t_now = time.perf_counter()
            self._session_state = SessionState.LISTENING
            return VoiceTurnResult(
                turn_index=current_gen_id,
                generation_id=current_gen_id,
                status=VoiceTurnStatus.CANCELLED,
                transcript=transcript_text,
                assistant_response=None,
                tts_result=None,
                timing=VoiceTurnTiming(
                    stt_duration_ms=round(stt_duration_ms, 2),
                    assistant_duration_ms=0.0,
                    tts_time_to_first_audio_ms=0.0,
                    tts_total_duration_ms=0.0,
                    total_speech_end_to_first_audio_ms=0.0,
                    total_turn_duration_ms=round((t_now - t0) * 1000.0, 2),
                    cancellation_latency_ms=round(_calc_cancel_latency(t_now), 2),
                ),
                error_message="Turn cancelled before Assistant execution.",
            )

        try:
            assistant_response: AssistantResponse = await self.assistant.answer_query(
                query=transcript_text,
                access_context=access_context,
                source_id=source_id,
                top_k=top_k,
                threshold=threshold,
            )
        except Exception as exc:
            t_now = time.perf_counter()
            self._session_state = SessionState.LISTENING
            return VoiceTurnResult(
                turn_index=current_gen_id,
                generation_id=current_gen_id,
                status=VoiceTurnStatus.ASSISTANT_FAILURE,
                transcript=transcript_text,
                assistant_response=None,
                tts_result=None,
                timing=VoiceTurnTiming(
                    stt_duration_ms=round(stt_duration_ms, 2),
                    assistant_duration_ms=round((t_now - t_stt_done) * 1000.0, 2),
                    tts_time_to_first_audio_ms=0.0,
                    tts_total_duration_ms=0.0,
                    total_speech_end_to_first_audio_ms=0.0,
                    total_turn_duration_ms=round((t_now - t0) * 1000.0, 2),
                ),
                error_message=f"Assistant query failed: {exc}",
            )

        t_assistant_done = time.perf_counter()
        assistant_duration_ms = (t_assistant_done - t_stt_done) * 1000.0

        if on_assistant:
            cb_res = on_assistant(assistant_response)
            if asyncio.iscoroutine(cb_res):
                await cb_res

        # If cancelled while assistant was executing, discard answer and do NOT commit to context
        if _is_cancelled():
            t_now = time.perf_counter()
            self._session_state = SessionState.LISTENING
            return VoiceTurnResult(
                turn_index=current_gen_id,
                generation_id=current_gen_id,
                status=VoiceTurnStatus.CANCELLED,
                transcript=transcript_text,
                assistant_response=None,
                tts_result=None,
                timing=VoiceTurnTiming(
                    stt_duration_ms=round(stt_duration_ms, 2),
                    assistant_duration_ms=round(assistant_duration_ms, 2),
                    tts_time_to_first_audio_ms=0.0,
                    tts_total_duration_ms=0.0,
                    total_speech_end_to_first_audio_ms=0.0,
                    total_turn_duration_ms=round((t_now - t0) * 1000.0, 2),
                    cancellation_latency_ms=round(_calc_cancel_latency(t_now), 2),
                ),
                citations=[c.to_dict() for c in assistant_response.citations],
                error_message="Turn cancelled during/after Assistant execution.",
            )

        # Map assistant response status
        if assistant_response.status == AssistantResponseStatus.INSUFFICIENT_EVIDENCE:
            turn_status = VoiceTurnStatus.INSUFFICIENT_EVIDENCE
        elif assistant_response.status == AssistantResponseStatus.PROMPT_INJECTION_DETECTED:
            turn_status = VoiceTurnStatus.PROMPT_INJECTION_DETECTED
        else:
            turn_status = VoiceTurnStatus.SUCCESS

        citations = [c.to_dict() for c in assistant_response.citations]

        # ─── 3. Local Text-to-Speech (Piper) ─────────────────────────────────
        self._session_state = SessionState.SPEAKING

        answer_text = assistant_response.answer.strip()
        tts_result: TTSResult | None = None
        tts_error: str | None = None
        t_tts_first_audio: float | None = None
        audio_chunks: list[bytes] = []
        sample_rate = 22050
        channels = 1
        sample_width = 2
        was_cancelled_in_tts = False

        t_tts_start = time.perf_counter()
        try:
            tts_stream = self.tts_engine.synthesize_stream(
                answer_text,
                generation_id=current_gen_id,
                cancellation_token=turn_cancel_tok,
            )

            async def _handle_chunk(chunk: TTSChunk) -> bool:
                nonlocal was_cancelled_in_tts, t_tts_first_audio, sample_rate, channels, sample_width
                if _is_cancelled() or chunk.generation_id != self._active_generation_id:
                    was_cancelled_in_tts = True
                    return False

                if t_tts_first_audio is None:
                    t_tts_first_audio = time.perf_counter()
                    sample_rate = chunk.sample_rate
                    channels = chunk.channels
                    sample_width = chunk.sample_width

                audio_chunks.append(chunk.audio)
                if on_tts_chunk:
                    cb_res = on_tts_chunk(chunk)
                    if asyncio.iscoroutine(cb_res):
                        await cb_res
                return True

            if hasattr(tts_stream, "__aiter__"):
                async for chunk in tts_stream:
                    if not await _handle_chunk(chunk):
                        break
            else:
                for chunk in tts_stream:
                    if not await _handle_chunk(chunk):
                        break

            t_tts_done = time.perf_counter()

            if was_cancelled_in_tts or _is_cancelled():
                self._session_state = SessionState.LISTENING
                t_now = time.perf_counter()
                return VoiceTurnResult(
                    turn_index=current_gen_id,
                    generation_id=current_gen_id,
                    status=VoiceTurnStatus.CANCELLED,
                    transcript=transcript_text,
                    assistant_response=assistant_response,
                    tts_result=None,
                    timing=VoiceTurnTiming(
                        stt_duration_ms=round(stt_duration_ms, 2),
                        assistant_duration_ms=round(assistant_duration_ms, 2),
                        tts_time_to_first_audio_ms=round(
                            ((t_tts_first_audio - t_tts_start) * 1000.0) if t_tts_first_audio else 0.0,
                            2,
                        ),
                        tts_total_duration_ms=round((t_now - t_tts_start) * 1000.0, 2),
                        total_speech_end_to_first_audio_ms=round(
                            ((t_tts_first_audio - t0) * 1000.0) if t_tts_first_audio else 0.0,
                            2,
                        ),
                        total_turn_duration_ms=round((t_now - t0) * 1000.0, 2),
                        cancellation_latency_ms=round(_calc_cancel_latency(t_now), 2),
                    ),
                    citations=citations,
                    error_message="Turn cancelled during TTS generation.",
                )

            full_audio = b"".join(audio_chunks)
            bytes_per_sample = channels * sample_width
            num_samples = len(full_audio) // bytes_per_sample if bytes_per_sample > 0 else 0
            audio_duration_ms = (num_samples / sample_rate * 1000.0) if sample_rate > 0 else 0.0
            tts_processing_ms = (t_tts_done - t_tts_start) * 1000.0
            tts_first_ms = ((t_tts_first_audio - t_tts_start) * 1000.0) if t_tts_first_audio else 0.0

            tts_result = TTSResult(
                audio=full_audio,
                sample_rate=sample_rate,
                channels=channels,
                sample_width=sample_width,
                duration_ms=round(audio_duration_ms, 2),
                processing_time_ms=round(tts_processing_ms, 2),
                time_to_first_audio_ms=round(tts_first_ms, 2),
            )
        except Exception as exc:
            t_tts_done = time.perf_counter()
            tts_error = f"TTS synthesis failed: {exc}"
            turn_status = VoiceTurnStatus.TTS_FAILURE

        t_end = time.perf_counter()
        tts_total_duration_ms = (t_tts_done - t_tts_start) * 1000.0
        tts_first_latency = (
            ((t_tts_first_audio - t_tts_start) * 1000.0) if t_tts_first_audio is not None else 0.0
        )
        speech_end_to_first_audio = (
            ((t_tts_first_audio - t0) * 1000.0) if t_tts_first_audio is not None else 0.0
        )
        total_turn_duration_ms = (t_end - t0) * 1000.0

        # Commit completed turn to bounded conversation context ONLY if not cancelled
        self.context_manager.add_turn(transcript_text, assistant_response.answer)
        self._session_state = SessionState.LISTENING

        return VoiceTurnResult(
            turn_index=current_gen_id,
            generation_id=current_gen_id,
            status=turn_status,
            transcript=transcript_text,
            assistant_response=assistant_response,
            tts_result=tts_result,
            timing=VoiceTurnTiming(
                stt_duration_ms=round(stt_duration_ms, 2),
                assistant_duration_ms=round(assistant_duration_ms, 2),
                tts_time_to_first_audio_ms=round(tts_first_latency, 2),
                tts_total_duration_ms=round(tts_total_duration_ms, 2),
                total_speech_end_to_first_audio_ms=round(speech_end_to_first_audio, 2),
                total_turn_duration_ms=round(total_turn_duration_ms, 2),
                cancellation_latency_ms=0.0,
            ),
            citations=citations,
            error_message=tts_error,
        )
