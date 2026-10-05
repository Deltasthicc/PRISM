"""The committed docs/contracts/openapi.json must match the real API.

It used to be a hand-written scaffold that CI only checked for valid JSON, so
it could (and did) drift from the routes actually served. Regenerate with
`python -m scripts.export_openapi` from `backend/`.
"""
from __future__ import annotations

import json

from scripts.export_openapi import CONTRACT_PATH, build_openapi


def test_committed_openapi_contract_matches_the_running_app():
    assert CONTRACT_PATH.exists(), "docs/contracts/openapi.json is missing"
    committed = CONTRACT_PATH.read_text(encoding="utf-8")
    assert committed == build_openapi(), (
        "docs/contracts/openapi.json is stale; run `python -m scripts.export_openapi` from backend/"
    )


def test_contract_documents_the_routes_this_product_depends_on():
    paths = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["paths"]
    for required in (
        "/auth/me",
        "/auth/register",
        "/learning/catalogue/enroll",
        "/learning/admin/overview",
        "/learning/cohorts",
    ):
        assert required in paths, f"{required} missing from the API contract"
