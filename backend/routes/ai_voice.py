"""
Lane 4 (Content AI & Voice) — Local WebSocket Transport.

Exposes /ai/voice/stream for full-duplex conversational voice streaming over WebSockets.
Coordinates asynchronous client PCM receiving, VAD processing, STT, RAG Assistant,
and sentence-incremental Piper TTS output.
Authentication is explicitly deferred to Stage 7 (uses local/test AccessContext).
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import logging
import time
from typing import Any, Callable
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ai.provenance import AccessContext
from ai.voice.session_manager import (
    SessionState,
    VoiceSessionManager,
    VoiceTurnResult,
    VoiceTurnStatus,
)
from ai.voice.stt import TranscriptionResult
from ai.voice.tts import TTSChunk
from ai.voice.vad import VADEventType, VoiceActivityDetector

from db.database import SessionLocal
from routes.authorization import _DEMO_AUTH_DISABLED, _demo_principal
from security.identity import AuthenticationError, get_current_subject
from security.rbac import (
    AuthorizationError,
    BoundPrincipal,
    require_deployment_tenant,
    resolve_bound_principal,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/voice", tags=["Voice AI (Local)"])

_FORBIDDEN_IDENTITY_FIELDS = frozenset({"tenant_id", "user_id", "player_id", "roles"})

# Dependency injection hooks for deterministic testing
_session_factory: Callable[[], VoiceSessionManager] | None = None
_vad_factory: Callable[[], VoiceActivityDetector] | None = None
_auth_verifier: Callable[[str | None, Any], BoundPrincipal] | None = None


def set_voice_factories(
    session_factory: Callable[[], VoiceSessionManager] | None = None,
    vad_factory: Callable[[], VoiceActivityDetector] | None = None,
    auth_verifier: Callable[[str | None, Any], BoundPrincipal] | None = None,
) -> None:
    """Set factory overrides for testing without real model weights or Keycloak."""
    global _session_factory, _vad_factory, _auth_verifier
    _session_factory = session_factory
    _vad_factory = vad_factory
    _auth_verifier = auth_verifier


def reset_voice_factories() -> None:
    """Restore default session, VAD, and auth instantiation."""
    global _session_factory, _vad_factory, _auth_verifier
    _session_factory = None
    _vad_factory = None
    _auth_verifier = None


def _authenticate_token(raw_auth_header: str | None) -> BoundPrincipal:
    """Validate bearer token, resolve bound principal, and verify deployment tenant.

    Fails closed immediately on missing, invalid, or unauthorized credentials
    unless an explicit test factory is injected, or the same DISABLE_AUTH demo
    bypass routes/authorization.py's require_principal already uses is set --
    this endpoint had no such bypass before, meaning voice could never work in
    exactly the DISABLE_AUTH=true local/demo setup the rest of this app runs
    in (no bearer token to send, and no local Keycloak in that setup to issue
    one). Reusing the same well-labeled bypass here, rather than inventing a
    second one, keeps this consistent with every other route's demo behavior.
    Never set DISABLE_AUTH=true for a deployment handling real user data.
    """
    if _auth_verifier is not None:
        return _auth_verifier(raw_auth_header, None)

    if _DEMO_AUTH_DISABLED:
        return _demo_principal()

    if not raw_auth_header:
        raise AuthenticationError("Authentication required.")

    with SessionLocal() as db:
        subject = get_current_subject(raw_auth_header)
        principal = resolve_bound_principal(db, subject)
        require_deployment_tenant(principal)
        return principal


@router.websocket("/stream")
async def voice_stream_endpoint(websocket: WebSocket) -> None:
    """Full-duplex WebSocket endpoint for authenticated local voice streaming.

    Security & Protocol Lifecycle:
      1. Accept connection.
      2. Authenticate principal via Authorization header or initial JSON message.
         Fails closed with code 1008 if unauthenticated/unauthorized.
      3. Negotiate audio configuration {"type": "start", "sample_rate": 16000, "channels": 1, "format": "pcm_s16le"}.
      4. Server derives AccessContext strictly from verified BoundPrincipal.
         Client-supplied tenant_id/user_id/roles cannot override server identity.
      5. Emit JSON {"type": "ready", "session_id": ..., "tenant_id": ..., "user_id": ..., "roles": [...]}.
      6. Client streams binary PCM16 frames. Server VAD detects speech onset/offset.
      7. Server runs STT -> Assistant (access-filtered RAG) -> Piper TTS.
      8. Client speech during playback triggers barge-in interrupt immediately.
    """
    await websocket.accept()

    session_id = str(uuid.uuid4())
    send_lock = asyncio.Lock()

    # ─── 1. Authentication & Audio Handshake ─────────────────────────────────
    raw_auth_header = websocket.headers.get("authorization")

    try:
        raw_first_msg = await websocket.receive_text()
        first_msg = json.loads(raw_first_msg)
    except Exception:
        await websocket.send_json(
            {
                "type": "error",
                "code": "INVALID_HANDSHAKE",
                "message": "Malformed handshake JSON.",
            }
        )
        await websocket.close(code=1003)
        return

    # Reject client-supplied authoritative identity fields immediately (Option B)
    if any(field in first_msg for field in _FORBIDDEN_IDENTITY_FIELDS):
        await websocket.send_json(
            {
                "type": "error",
                "code": "SPOOFING_ATTEMPT_REJECTED",
                "message": "Client-controlled identity fields are not permitted.",
            }
        )
        await websocket.close(code=1008)
        return

    msg_type = first_msg.get("type")

    # Support separate "auth" message or credential embedded in "start" message for browser clients
    if msg_type == "auth":
        token_candidate = first_msg.get("authorization") or first_msg.get("token")
        if token_candidate and not raw_auth_header:
            raw_auth_header = (
                token_candidate
                if token_candidate.startswith("Bearer ")
                else f"Bearer {token_candidate}"
            )

        # Authenticate now
        try:
            principal = _authenticate_token(raw_auth_header)
        except AuthenticationError:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "Authentication failed.",
                }
            )
            await websocket.close(code=1008)
            return
        except AuthorizationError:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "ACCESS_DENIED",
                    "message": "Access denied.",
                }
            )
            await websocket.close(code=1008)
            return

        # Receive subsequent start message
        try:
            raw_start_msg = await websocket.receive_text()
            start_msg = json.loads(raw_start_msg)
        except Exception:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "INVALID_HANDSHAKE",
                    "message": "Malformed start configuration JSON.",
                }
            )
            await websocket.close(code=1003)
            return

        # Reject client-supplied authoritative identity fields in subsequent start frame
        if any(field in start_msg for field in _FORBIDDEN_IDENTITY_FIELDS):
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "SPOOFING_ATTEMPT_REJECTED",
                    "message": "Client-controlled identity fields are not permitted.",
                }
            )
            await websocket.close(code=1008)
            return
    elif msg_type == "start":
        start_msg = first_msg
        token_candidate = start_msg.get("authorization") or start_msg.get("token")
        if token_candidate and not raw_auth_header:
            raw_auth_header = (
                token_candidate
                if token_candidate.startswith("Bearer ")
                else f"Bearer {token_candidate}"
            )

        # Authenticate
        try:
            principal = _authenticate_token(raw_auth_header)
        except AuthenticationError:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "Authentication failed.",
                }
            )
            await websocket.close(code=1008)
            return
        except AuthorizationError:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "ACCESS_DENIED",
                    "message": "Access denied.",
                }
            )
            await websocket.close(code=1008)
            return
    else:
        await websocket.send_json(
            {
                "type": "error",
                "code": "EXPECTED_START_MESSAGE",
                "message": f"Expected 'start' or 'auth' message, got '{msg_type}'.",
            }
        )
        await websocket.close(code=1003)
        return

    # Validate audio configuration parameters
    if start_msg.get("type") != "start":
        await websocket.send_json(
            {
                "type": "error",
                "code": "EXPECTED_START_MESSAGE",
                "message": "Expected 'start' configuration message.",
            }
        )
        await websocket.close(code=1003)
        return

    sample_rate = start_msg.get("sample_rate", 16000)
    if sample_rate != 16000:
        await websocket.send_json(
            {
                "type": "error",
                "code": "UNSUPPORTED_SAMPLE_RATE",
                "message": f"Sample rate {sample_rate} Hz is unsupported. Expected exactly 16000 Hz.",
            }
        )
        await websocket.close(code=1003)
        return

    channels = start_msg.get("channels", 1)
    if channels != 1:
        await websocket.send_json(
            {
                "type": "error",
                "code": "UNSUPPORTED_CHANNELS",
                "message": f"Channel count {channels} is unsupported. Expected mono (1 channel).",
            }
        )
        await websocket.close(code=1003)
        return

    audio_format = str(start_msg.get("format", "pcm_s16le")).lower()
    if audio_format not in ("pcm_s16le", "pcm16", "pcm_16le"):
        await websocket.send_json(
            {
                "type": "error",
                "code": "UNSUPPORTED_FORMAT",
                "message": f"Format '{audio_format}' is unsupported. Expected 'pcm_s16le'.",
            }
        )
        await websocket.close(code=1003)
        return

    # ─── 2. Server-Derived AccessContext ────────────────────────────────────
    # CRITICAL: Client-supplied tenant_id/user_id/roles cannot override server identity
    tenant_id = principal.tenant_scope
    user_id = principal.player_id or principal.subject.subject_id
    roles = tuple(principal.roles)
    access_context = AccessContext(tenant_id=tenant_id, user_id=user_id, roles=roles)

    # Acknowledge ready with server-confirmed identity and audio config
    await websocket.send_json(
        {
            "type": "ready",
            "session_id": session_id,
            "sample_rate": 16000,
            "channels": 1,
            "format": "pcm_s16le",
            "user_id": user_id,
            "tenant_id": tenant_id,
            "roles": list(roles),
        }
    )

    # ─── 3. Initialize In-Memory Session & VAD ────────────────────────────────
    session_manager: VoiceSessionManager = (
        _session_factory() if _session_factory else VoiceSessionManager()
    )
    vad_detector: VoiceActivityDetector = (
        _vad_factory() if _vad_factory else VoiceActivityDetector()
    )

    active_turn_task: asyncio.Task | None = None

    async def _safe_send_json(payload: dict[str, Any]) -> None:
        async with send_lock:
            try:
                await websocket.send_json(payload)
            except Exception:
                pass

    async def _safe_send_bytes(payload: bytes) -> None:
        async with send_lock:
            try:
                await websocket.send_bytes(payload)
            except Exception:
                pass

    async def _handle_turn_execution(audio_payload: bytes) -> None:
        """Asynchronous turn execution task running concurrently with the receive loop."""
        turn_gen_id = session_manager.generation_id + 1

        async def _on_transcript(tr: TranscriptionResult) -> None:
            await _safe_send_json(
                {
                    "type": "transcript",
                    "text": tr.text,
                    "duration_ms": tr.duration_ms,
                    "processing_time_ms": tr.processing_time_ms,
                    "real_time_factor": tr.real_time_factor,
                    "generation_id": turn_gen_id,
                }
            )

        async def _on_assistant(resp: Any) -> None:
            await _safe_send_json(
                {
                    "type": "assistant",
                    "status": resp.status.value if hasattr(resp.status, "value") else str(resp.status),
                    "answer": resp.answer,
                    "citations": [c.to_dict() for c in resp.citations],
                    "generation_id": turn_gen_id,
                }
            )

        async def _on_chunk(chunk: TTSChunk) -> None:
            # Drop chunk if stale or superseded by a newer generation
            if chunk.generation_id != session_manager.generation_id:
                return

            # Emit metadata event immediately before binary audio frame
            await _safe_send_json(
                {
                    "type": "audio_chunk",
                    "chunk_index": chunk.chunk_index,
                    "generation_id": chunk.generation_id,
                    "sample_rate": chunk.sample_rate,
                    "channels": chunk.channels,
                    "sample_width": chunk.sample_width,
                    "duration_ms": chunk.duration_ms,
                    "time_to_chunk_ms": chunk.time_to_chunk_ms,
                }
            )
            await _safe_send_bytes(chunk.audio)

        try:
            result: VoiceTurnResult = await session_manager.process_turn(
                pcm_bytes=audio_payload,
                access_context=access_context,
                on_tts_chunk=_on_chunk,
                on_transcript=_on_transcript,
                on_assistant=_on_assistant,
            )

            if result.status == VoiceTurnStatus.CANCELLED:
                await _safe_send_json(
                    {
                        "type": "interrupt",
                        "generation_id": result.generation_id,
                        "timing": asdict(result.timing),
                    }
                )
            elif result.status in (VoiceTurnStatus.STT_FAILURE, VoiceTurnStatus.ASSISTANT_FAILURE, VoiceTurnStatus.TTS_FAILURE):
                await _safe_send_json(
                    {
                        "type": "error",
                        "code": result.status.value.upper(),
                        "message": result.error_message or "Turn processing error.",
                        "generation_id": result.generation_id,
                    }
                )
            else:
                await _safe_send_json(
                    {
                        "type": "turn_complete",
                        "generation_id": result.generation_id,
                        "status": result.status.value,
                        "timing": asdict(result.timing),
                    }
                )
        except asyncio.CancelledError:
            # Cancelled from outside (e.g. barge-in or disconnect)
            pass
        except Exception as exc:
            await _safe_send_json(
                {
                    "type": "error",
                    "code": "INTERNAL_TURN_ERROR",
                    "message": "An internal error occurred during voice turn processing.",
                }
            )

    # ─── 3. Full-Duplex Receive Loop ─────────────────────────────────────────
    try:
        while True:
            message = await websocket.receive()
            msg_type = message.get("type")

            if msg_type == "websocket.disconnect":
                break

            # Handle Binary Audio Frames (PCM16)
            if "bytes" in message and message["bytes"] is not None:
                pcm_data = message["bytes"]
                if not pcm_data:
                    continue

                # Case A: Assistant is currently speaking -> Check for Barge-in speech onset
                if session_manager.session_state == SessionState.SPEAKING:
                    interrupted = session_manager.handle_barge_in_pcm(
                        pcm_data, vad_detector=vad_detector
                    )
                    if interrupted:
                        # Cancel active turn task
                        if active_turn_task and not active_turn_task.done():
                            active_turn_task.cancel()

                        await _safe_send_json(
                            {
                                "type": "interrupt",
                                "generation_id": session_manager.generation_id,
                            }
                        )
                        await _safe_send_json(
                            {
                                "type": "speech_start",
                                "timestamp_ms": vad_detector.timestamp_ms,
                            }
                        )
                    continue

                # Case B: Standard input listening / processing
                events = vad_detector.process_bytes(pcm_data)
                for ev in events:
                    if ev.event_type == VADEventType.SPEECH_START:
                        await _safe_send_json(
                            {
                                "type": "speech_start",
                                "timestamp_ms": ev.timestamp_ms,
                            }
                        )

                    elif ev.event_type == VADEventType.SPEECH_END:
                        await _safe_send_json(
                            {
                                "type": "speech_end",
                                "timestamp_ms": ev.timestamp_ms,
                                "duration_ms": (len(ev.audio) // 2 / 16000.0) * 1000.0,
                            }
                        )

                        # Cancel any lingering previous turn task before starting new turn
                        if active_turn_task and not active_turn_task.done():
                            active_turn_task.cancel()

                        # Spawn turn processing task concurrently so receive loop remains responsive
                        active_turn_task = asyncio.create_task(_handle_turn_execution(ev.audio))

            # Handle JSON Control Messages (flush, client interrupt)
            elif "text" in message and message["text"] is not None:
                try:
                    ctrl_msg = json.loads(message["text"])
                    if any(field in ctrl_msg for field in _FORBIDDEN_IDENTITY_FIELDS):
                        await _safe_send_json(
                            {
                                "type": "error",
                                "code": "SPOOFING_ATTEMPT_REJECTED",
                                "message": "Client-controlled identity fields are not permitted.",
                            }
                        )
                        await websocket.close(code=1008)
                        break

                    ctrl_type = ctrl_msg.get("type")

                    if ctrl_type == "flush":
                        flush_events = vad_detector.flush()
                        for ev in flush_events:
                            if ev.event_type == VADEventType.SPEECH_END:
                                await _safe_send_json(
                                    {
                                        "type": "speech_end",
                                        "timestamp_ms": ev.timestamp_ms,
                                        "duration_ms": (len(ev.audio) // 2 / 16000.0) * 1000.0,
                                    }
                                )
                                if active_turn_task and not active_turn_task.done():
                                    active_turn_task.cancel()
                                active_turn_task = asyncio.create_task(_handle_turn_execution(ev.audio))

                    elif ctrl_type == "interrupt":
                        session_manager.cancel_current_turn(reason="client_explicit_interrupt")
                        if active_turn_task and not active_turn_task.done():
                            active_turn_task.cancel()

                        await _safe_send_json(
                            {
                                "type": "interrupt",
                                "generation_id": session_manager.generation_id,
                            }
                        )
                except json.JSONDecodeError:
                    await _safe_send_json(
                        {
                            "type": "error",
                            "code": "INVALID_JSON",
                            "message": "Unable to parse control text message.",
                        }
                    )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(f"Voice WebSocket session terminated with error: {exc}")
    finally:
        # ─── 4. Disconnect Cleanup ───────────────────────────────────────────
        if active_turn_task and not active_turn_task.done():
            active_turn_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(active_turn_task), timeout=0.5)
            except Exception:
                pass

        session_manager.reset()
        vad_detector.reset()
