# Content/AI Service Interface and Evaluation Fixtures Contract

**Owner:** Lane 4 (Content AI, RAG & Evaluation)  
**Consumers:** Lane 1 (Frontend), Lane 2 (Identity/Data), Lane 3 (Competency), Lane 5 (API/Integrations), Lane 6 (Release & Evidence)  
**Status:** **ACTIVE / RATIFIED CONTRACT** (Implementation in `backend/ai/*` and `backend/routes/ai_real.py`)

---

## 1. Immutable Source Provenance & Chunk Schemas

### `SourceVersion`
```json
{
  "source_id": "string (UUID)",
  "version": 1,
  "sha256": "string (64-char hex hash)",
  "filename": "string",
  "content_type": "string (pdf | pptx | docx | md | txt | vtt | srt)",
  "character_count": 14250,
  "created_at": "string (ISO 8601 UTC)",
  "metadata": {}
}
```

### `SourceLocator`
```json
{
  "locator_type": "page | slide | section | paragraph | timecode",
  "index": 3,
  "label": "Slide 3 | Page 12 | Section: Sampling Frame | Timecode 00:01:20 - 00:01:45",
  "start_char": 0,
  "end_char": 450,
  "start_timecode": "00:01:20.000",
  "end_timecode": "00:01:45.000"
}
```

### `Chunk`
```json
{
  "chunk_id": "string (UUID)",
  "source_id": "string (UUID)",
  "source_version": 1,
  "text": "string (sanitized untrusted content)",
  "locators": [ { "locator_type": "slide", "index": 2, "label": "Slide 2" } ],
  "tenant_id": "string (e.g. 'default', 'mospi_hq')",
  "allowed_roles": ["learner", "trainer", "admin"],
  "token_count": 85,
  "metadata": {}
}
```

---

## 2. Pre-Retrieval Access & Search Interface

### Endpoint: `POST /ai/retrieval/search`
* **Consumer:** Lane 5 / Backend Services
* **Request:**
```json
{
  "query": "string",
  "tenant_id": "string (default: 'default')",
  "user_id": "string (default: 'anonymous')",
  "roles": ["learner"],
  "source_id": "string | null",
  "top_k": 3,
  "threshold": 0.20
}
```
* **Response:**
```json
{
  "query": "What are primary sampling units in crop surveys?",
  "retrieved_count": 1,
  "is_insufficient_evidence": false,
  "results": [
    {
      "chunk": { "...": "Chunk object" },
      "relevance_score": 0.7842,
      "matched_terms": ["primary", "sampling", "units", "crop"]
    }
  ],
  "citations": [
    {
      "citation_id": "uuid",
      "chunk_id": "uuid",
      "source_id": "uuid",
      "source_version": 1,
      "filename": "agri_stats.md",
      "locator_label": "Section: Crop Estimation",
      "quote": "The primary sampling units are revenue villages...",
      "confidence_score": 0.7842
    }
  ]
}
```

---

## 3. Learner Assistant Contract (`PS-06`)

### Endpoint: `POST /ai/assistant/query`
* **Consumer:** Lane 1 (Assistant Chat UI) / Lane 5
* **Request:**
```json
{
  "query": "What does this manual say about missing price imputation?",
  "tenant_id": "default",
  "user_id": "learner-uuid",
  "roles": ["learner"],
  "source_id": "optional-document-uuid",
  "top_k": 3
}
```
* **Response Status Taxonomy:**
  - `supported`: Query derived from verified evidence with exact citations.
  - `insufficient_evidence`: Top retrieval score fell below `threshold` (abstains cleanly).
  - `out_of_scope`: Query unrelated to ingested materials (abstains cleanly).
  - `prompt_injection_detected`: Query contained adversarial override patterns (refusal).
  - `retrieval_failure` / `system_failure`: Upstream failure.
* **Response Shape:**
```json
{
  "query": "What does this manual say about missing price imputation?",
  "answer": "According to Section: Imputation Methods: For temporarily missing price quotations, geometric mean price relatives from the same elementary stratum are imputed.",
  "status": "supported",
  "citations": [
    {
      "citation_id": "uuid",
      "chunk_id": "uuid",
      "source_id": "uuid",
      "source_version": 1,
      "filename": "cpi_manual.md",
      "locator_label": "Section: Imputation Methods",
      "quote": "For temporarily missing price quotations, geometric mean price relatives from the same elementary stratum are imputed.",
      "confidence_score": 0.85
    }
  ],
  "retrieved_chunks": [ "...RetrievedChunk objects..." ],
  "abstention_reason": null,
  "model_version": "gemini-flash-lite-latest",
  "created_at": "2026-09-01T04:20:00Z"
}
```

---

## 4. Assessment Item Review State Machine (`PS-12`)

### Lifecycle States
```
draft ──[auto checks pass]──> auto_checked ──[expert sign-off]──> approved ──> pilot ──> published
  │                                │                                 │           │           │
  └────────────────────────────────┴─────────────────────────────────┴───────────┴───────────┴──> retired
```

* **Valid States:**
  1. `draft`: Raw generated output from model or extractive fallback.
  2. `auto_checked`: Deterministically validated (4 unique options, valid answer index 0–3, source excerpt verified verbatim in text, valid Bloom taxonomy).
  3. `expert_review`: In review by designated subject matter expert / trainer.
  4. `approved`: Confirmed by domain reviewer for inclusion in item bank.
  5. `pilot`: Field tested in low-stakes practice.
  6. `published`: Active in official diagnostics.
  7. `retired`: Deprecated from active use.

### Endpoint: `POST /ai/quiz/review`
* **Request:**
```json
{
  "item": { "...QuizQuestionItem payload..." },
  "target_state": "approved",
  "reviewer_id": "expert-statistician-01",
  "notes": "Verified against 2024 CPI Manual update."
}
```

---

## 5. Explicit Answer Grading Contract

### Function: `grade_student_answer(...)` / Endpoint: `POST /ai/answer/judge`
* **Output Structure:**
```json
{
  "learner_answer": "It minimizes the sum of squared residuals.",
  "expected_answer": "Sum of squared residuals",
  "score": 1.0,
  "verdict": "correct",
  "damage_multiplier": 2.0,
  "feedback": "Perfect! Your answer matches the expected answer exactly.",
  "evidence_quote": "Ordinary Least Squares (OLS) regression minimizes the sum of squared residuals.",
  "grader_version": "deterministic-exact-v1",
  "evaluated_at": "2026-09-01T04:25:00Z"
}
```

---

## 6. Gold-Set Evaluation Fixture & Metrics

### Endpoint: `GET /ai/evaluation/report`
* **Dataset Version:** `SYNTHETIC_GOLD_SET_V1`
* **Benchmark Metrics Reported:**
  - `retrieval_recall_at_k` (Threshold: $\ge 0.85$)
  - `citation_accuracy` (Threshold: $\ge 0.90$)
  - `abstention_accuracy` (Threshold: $\ge 0.85$)
  - `injection_defense_rate` (Threshold: $\ge 0.95$)
  - `grading_agreement` (Threshold: $\ge 0.80$)
  - `question_groundedness` (Threshold: $1.00$)

---

## 7. Local Conversational Voice Streaming Contract (`/ai/voice/stream`)

* **Endpoint:** `WebSocket /ai/voice/stream`
* **Consumer:** Lane 1 (Voice UI) / Local Conversational Assistants
* **Status:** **STAGE 7 IMPLEMENTED (Authenticated WebSocket + RBAC Integration)**
* **Zero Persistence Guarantee:** All raw audio buffers, synthesized speech chunks, and bearer tokens remain strictly in memory; zero audio files or credentials are written to disk.

### 7.1 Lifecycle & Authenticated Handshake Negotiation

Authentication integrates directly with the repository's authoritative security architecture (`get_current_subject`, `resolve_bound_principal`, and `require_deployment_tenant`). Tokens in URL query parameters (`?token=...`) are strictly prohibited and never processed.

#### Handshake Authentication Mechanisms
Clients authenticate through one of three mechanisms:
1. **HTTP Upgrade Header:**
   Standard `Authorization: Bearer <token>` header during the WebSocket handshake upgrade.
2. **Initial Auth Frame:**
   First message sent over WebSocket:
   ```json
   {
     "type": "auth",
     "token": "<bearer_token>"
   }
   ```
3. **Combined Start Frame:**
   First message sent over WebSocket with inline credentials:
   ```json
   {
     "type": "start",
     "token": "<bearer_token>",
     "sample_rate": 16000,
     "channels": 1,
     "format": "pcm_s16le"
   }
   ```

#### Server-Derived Principal & RBAC Enforcement
* **Identity Resolution:**
  - Token is verified against OIDC / bearer verification pipelines to resolve `SubjectIdentity`.
  - Identity is bound against database principal storage to resolve `BoundPrincipal`.
  - Valid tenant scope is enforced via `require_deployment_tenant(principal)`.
  - Immutable `AccessContext` is constructed strictly server-side:
    - `tenant_id = principal.tenant_scope`
    - `user_id = principal.player_id or principal.subject.subject_id`
    - `roles = tuple(principal.roles)`
* **Anti-Spoofing & Client Override Protection:**
  - Any client-provided `user_id`, `player_id`, `tenant_id`, or `roles` in payload frames are strictly ignored and discarded.
  - The session's RAG retrieval and tool executions are hard-scoped to the derived `tenant_id` and authorized `roles`.
* **Rejection & Termination:**
  - Unauthenticated connections, expired/invalid tokens, unbound principals, or cross-tenant scope mismatches fail closed.
  - WebSocket is closed with code `1008` (Policy Violation) and clear rejection reason (`AUTHENTICATION_REQUIRED`, `INVALID_CREDENTIALS`, `EXPIRED_CREDENTIALS`, `TENANT_SCOPE_REQUIRED`, `ACCESS_DENIED`).

#### Handshake Sequence
1. **Client Connection:** Client connects to `ws://.../ai/voice/stream`.
2. **Authentication / Start Negotiation:** Client provides credentials via header or initial frame, and specifies audio format (16000 Hz, 1 channel, `pcm_s16le`).
3. **Server Ready (Server $\to$ Client):**
   ```json
   {
     "type": "ready",
     "session_id": "uuid-v4",
     "user_id": "resolved-user-id",
     "tenant_id": "resolved-tenant-id",
     "roles": ["student", "player"],
     "sample_rate": 16000,
     "channels": 1,
     "format": "pcm_s16le"
   }
   ```

### 7.2 Full-Duplex Audio & Control Framing

* **Audio Ingestion:** Client streams binary WebSocket frames of raw 16-bit little-endian PCM at 16,000 Hz.
* **VAD Events (Server $\to$ Client):**
  - Speech Onset: `{"type": "speech_start", "timestamp_ms": 192.0}`
  - Speech Offset: `{"type": "speech_end", "timestamp_ms": 1400.0, "duration_ms": 1208.0}`
* **Turn Processing Events (Server $\to$ Client):**
  - STT Transcription:
    ```json
    {
      "type": "transcript",
      "text": "What are primary sampling units?",
      "duration_ms": 1208.0,
      "processing_time_ms": 320.5,
      "real_time_factor": 0.265,
      "generation_id": 1
    }
    ```
  - Assistant RAG Result:
    ```json
    {
      "type": "assistant",
      "status": "supported",
      "answer": "The primary sampling units are revenue villages in rural areas.",
      "citations": [ { "...": "Citation object" } ],
      "generation_id": 1
    }
    ```
  - Incremental Audio Chunks:
    Each audio chunk is preceded immediately by a small JSON metadata frame, followed by a binary PCM audio frame:
    ```json
    {
      "type": "audio_chunk",
      "chunk_index": 0,
      "generation_id": 1,
      "sample_rate": 22050,
      "channels": 1,
      "sample_width": 2,
      "duration_ms": 1450.0,
      "time_to_chunk_ms": 180.2
    }
    ```
    *(Binary frame with raw PCM bytes follows)*
  - Turn Complete:
    ```json
    {
      "type": "turn_complete",
      "generation_id": 1,
      "status": "success",
      "timing": {
        "stt_duration_ms": 320.5,
        "assistant_duration_ms": 150.2,
        "tts_time_to_first_audio_ms": 180.2,
        "tts_total_duration_ms": 520.1,
        "total_speech_end_to_first_audio_ms": 650.9,
        "total_turn_duration_ms": 990.8,
        "cancellation_latency_ms": 0.0
      }
    }
    ```

### 7.3 Client Control Messages (Client $\to$ Server)

* **Flush Speech Buffer:** `{"type": "flush"}` (forces completion of active speech segment and launches turn).
* **Manual Interrupt:** `{"type": "interrupt"}` (cooperatively cancels active processing or playback).

### 7.4 Barge-In & Cooperative Cancellation Semantics

* When the client sends speech PCM frames while the assistant is speaking (`SPEAKING` state), the server evaluates VAD onset with hysteresis debounce.
* Upon speech onset detection:
  1. Active background generation task is cooperatively cancelled.
  2. In-flight and queued TTS audio chunks are dropped.
  3. Server emits `{"type": "interrupt", "generation_id": N}` to notify client to halt local speaker output.
  4. Server emits `{"type": "speech_start", "timestamp_ms": ...}` and begins accumulating the new user utterance.
  5. The interrupted generation is discarded and not committed to conversational context.

