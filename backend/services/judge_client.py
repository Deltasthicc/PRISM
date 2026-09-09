"""Judge0 client — real, sandboxed code execution for the DSA sandbox.

Per SIH26101_MASTER_CHECKLIST.md section 4.4 ("do not execute arbitrary
learner code on the API host; use an isolated short-lived sandbox with
CPU/memory/time/network limits"), submitted code is never run in-process or
via a bare subprocess here -- every submission is delegated to a real Judge0
instance (self-hosted or the public Judge0 CE API), which is exactly that
kind of isolated sandbox. JUDGE0_BASE_URL defaults to the public,
keyless https://ce.judge0.com demo instance; a real deployment handling
untrusted traffic at scale should point this at a self-hosted instance (see
.env.example) and set JUDGE0_API_KEY if the target requires one
(e.g. a RapidAPI-hosted Judge0).
"""
import os
import httpx
from dotenv import load_dotenv

from services.dsa_lang_gen import LANGUAGES, DEFAULT_LANGUAGE

load_dotenv()

JUDGE0_BASE_URL = os.getenv("JUDGE0_BASE_URL", "https://ce.judge0.com").rstrip("/")
JUDGE0_API_KEY = os.getenv("JUDGE0_API_KEY")
JUDGE0_API_HOST = os.getenv("JUDGE0_API_HOST")  # RapidAPI-hosted instances need this alongside the key

# Confirmed against Judge0 CE's live /languages endpoint at build time --
# see the DSA sandbox PR description for how this was verified, not guessed.
# services/dsa_lang_gen.py owns the language -> Judge0 ID mapping since the
# harness generator and the judge client must always agree on it.
PYTHON_LANGUAGE_ID = LANGUAGES["python"]["judge0_id"]  # "Python (3.8.1)" -- kept for backward compat

# Real wall-clock ceiling for one Judge0 round trip: the sandbox itself
# enforces a much shorter CPU-time limit (cpu_time_limit below); this is
# just how long we're willing to wait on the HTTP call before giving up and
# reporting "judge_unavailable" rather than hanging the request.
_HTTP_TIMEOUT_S = 20.0

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S)
    return _client


class JudgeUnavailableError(Exception):
    """Raised when Judge0 itself couldn't be reached or timed out -- distinct
    from any verdict about the submitted code, which should never look like
    a real Wrong Answer/Runtime Error when the judge simply didn't run."""


# Judge0's own status IDs (https://ce.judge0.com/statuses) -- 1/2 (In
# Queue/Processing) never reach us because every call below passes
# `wait=true`, which blocks until a terminal status is assigned.
_ACCEPTED = 3
_WRONG_ANSWER = 4
_TIME_LIMIT_EXCEEDED = 5
_COMPILATION_ERROR = 6
# 7-12 are Judge0's various runtime-error subtypes (SIGSEGV, SIGXFSZ,
# SIGFPE, SIGABRT, NZEC, Other) -- Python has no separate compile step, so a
# SyntaxError surfaces here (as NZEC, id 11) with the traceback in stderr,
# not as a distinct compilation error.
_RUNTIME_ERROR_IDS = frozenset(range(7, 13))
_INTERNAL_ERROR = 13
_EXEC_FORMAT_ERROR = 14


async def run_test_case(
    source_code: str, stdin: str, expected_output: str, language: str = DEFAULT_LANGUAGE
) -> dict:
    """Run one test case against Judge0 and return a normalized verdict:
    {status, stdout, stderr, compile_output, time, passed}.

    `status` is one of: accepted, wrong_answer, compile_error, runtime_error,
    time_limit_exceeded, judge_unavailable.

    `language` must be one of services.dsa_lang_gen.LANGUAGES' keys; compiled
    languages (Java/C++/C#) get a longer cpu_time_limit since Judge0 counts
    compilation time against it too.
    """
    if language not in LANGUAGES:
        raise ValueError(f"unsupported language: {language!r}")
    language_id = LANGUAGES[language]["judge0_id"]
    cpu_time_limit = 5 if language in ("python", "javascript") else 10

    headers = {"Content-Type": "application/json"}
    if JUDGE0_API_KEY:
        headers["X-RapidAPI-Key"] = JUDGE0_API_KEY
    if JUDGE0_API_HOST:
        headers["X-RapidAPI-Host"] = JUDGE0_API_HOST

    try:
        response = await _get_client().post(
            f"{JUDGE0_BASE_URL}/submissions",
            params={"base64_encoded": "false", "wait": "true"},
            headers=headers,
            json={
                "source_code": source_code,
                "language_id": language_id,
                "stdin": stdin,
                "expected_output": expected_output,
                # Real limits, not a formality -- an infinite loop or a fork
                # bomb must fail fast, not hang the judge or this request.
                "cpu_time_limit": cpu_time_limit,
                "memory_limit": 128000,
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JudgeUnavailableError(str(exc)) from exc

    body = response.json()
    status_id = body.get("status", {}).get("id")
    if status_id == _ACCEPTED:
        status = "accepted"
    elif status_id == _WRONG_ANSWER:
        status = "wrong_answer"
    elif status_id == _COMPILATION_ERROR:
        status = "compile_error"
    elif status_id == _TIME_LIMIT_EXCEEDED:
        status = "time_limit_exceeded"
    elif status_id in _RUNTIME_ERROR_IDS:
        status = "runtime_error"
    else:  # internal error, exec format error, or an unrecognized future ID
        status = "judge_unavailable"

    return {
        "status": status,
        "stdout": body.get("stdout"),
        "stderr": body.get("stderr"),
        "compile_output": body.get("compile_output"),
        "time": body.get("time"),
        "passed": status == "accepted",
    }
