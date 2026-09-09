"""Replaceable learning-provider boundary owned by Lane 5."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderResult:
    status: str
    data: dict
    idempotency_key: str | None = None


class LearningProviderAdapter(Protocol):
    """Minimum provider contract; implementations must never fabricate records."""

    def search_catalogue(self, query: str, *, cursor: str | None = None) -> ProviderResult: ...

    def get_course(self, provider_record_id: str) -> ProviderResult: ...

    def request_enrolment(self, provider_record_id: str, *, idempotency_key: str) -> ProviderResult: ...

    def import_completions(self, *, cursor: str | None = None) -> ProviderResult: ...

    def health_check(self) -> ProviderResult: ...

    def reconcile(self, *, cursor: str | None = None) -> ProviderResult: ...


class LiveHTTPProviderAdapter:
    """A real adapter shape for a configured provider base URL.

    This is the piece services/learning_catalog.py's `integration_status()`
    was missing: docs/contracts/provider-adapter.md's own contract says "an
    environment variable alone must never imply LIVE; that requires a
    successful authenticated capability check" -- before this class existed,
    `integration_status()` only ever checked `bool(os.getenv(...))`, so
    setting `IGOT_API_BASE_URL=anything` (even a typo, an unreachable host,
    or a URL with no real service behind it) would have flipped the UI to
    "Live iGOT Karmayogi API configured" with zero verification.

    `health_check()` makes one real, short-timeout, unauthenticated GET
    against `{base_url}/health` and reports the genuine outcome -- `LIVE`
    only on a real 2xx response, `ERROR` otherwise (network failure, non-2xx,
    timeout). No approved iGOT/NSSTA endpoint contract, credentials or
    sandbox exist yet (PS-05/PS-17's BLOCKED-EXTERNAL boundary per
    docs/SIH26101_PROBLEM_STATEMENT.md) -- so pointing this at a real
    provider URL today will genuinely report `ERROR`, which is the honest
    "real mode configured but not actually reachable" result the caller is
    supposed to see, not a fabricated `LIVE`. The other methods below are
    deliberately unimplemented rather than guessed at a fake request shape:
    building a real search/enrolment/completion call requires the actual
    contract this project does not have.
    """

    status = "LIVE"

    def __init__(self, base_url: str, timeout_seconds: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def health_check(self) -> ProviderResult:
        import httpx

        try:
            response = httpx.get(f"{self.base_url}/health", timeout=self.timeout_seconds)
            response.raise_for_status()
            return ProviderResult("LIVE", {"capabilities": [], "http_status": response.status_code})
        except httpx.HTTPError as exc:
            return ProviderResult("ERROR", {"capabilities": [], "error": str(exc)})

    def _no_contract(self, **extra) -> ProviderResult:
        return ProviderResult(
            "ERROR",
            {"reason": "no approved provider endpoint contract exists yet", **extra},
        )

    def search_catalogue(self, query: str, *, cursor: str | None = None) -> ProviderResult:
        return self._no_contract(query=query, items=[], next_cursor=None)

    def get_course(self, provider_record_id: str) -> ProviderResult:
        return self._no_contract(provider_record_id=provider_record_id, found=False)

    def request_enrolment(self, provider_record_id: str, *, idempotency_key: str) -> ProviderResult:
        result = self._no_contract(provider_record_id=provider_record_id, accepted=False)
        return ProviderResult(result.status, result.data, idempotency_key)

    def import_completions(self, *, cursor: str | None = None) -> ProviderResult:
        return self._no_contract(events=[], next_cursor=None)

    def reconcile(self, *, cursor: str | None = None) -> ProviderResult:
        return self._no_contract(matched=0, conflicts=[], next_cursor=None)


class SimulatedIGOTAdapter:
    """Deterministic offline fixture, visibly distinct from a live adapter."""

    status = "SIMULATED"

    def search_catalogue(self, query: str, *, cursor: str | None = None) -> ProviderResult:
        return ProviderResult(self.status, {"query": query, "items": [], "next_cursor": None})

    def get_course(self, provider_record_id: str) -> ProviderResult:
        return ProviderResult(self.status, {"provider_record_id": provider_record_id, "found": False})

    def request_enrolment(self, provider_record_id: str, *, idempotency_key: str) -> ProviderResult:
        return ProviderResult(self.status, {"accepted": False, "reason": "simulation-only"}, idempotency_key)

    def import_completions(self, *, cursor: str | None = None) -> ProviderResult:
        return ProviderResult(self.status, {"events": [], "next_cursor": None})

    def health_check(self) -> ProviderResult:
        return ProviderResult(self.status, {"capabilities": []})

    def reconcile(self, *, cursor: str | None = None) -> ProviderResult:
        return ProviderResult(self.status, {"matched": 0, "conflicts": [], "next_cursor": None})