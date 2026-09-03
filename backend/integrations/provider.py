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