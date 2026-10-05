"""Export the running FastAPI app's real OpenAPI document.

Usage (from `backend/`):

    python -m scripts.export_openapi            # rewrite docs/contracts/openapi.json
    python -m scripts.export_openapi --check    # exit 1 if the committed file is stale

`tests/test_openapi_contract.py` runs the same comparison, so a route added,
removed or reshaped without regenerating the contract fails the test suite.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "openapi.json"


# Routers that exist only in some environments (optional ML packages for the
# local voice pipeline; the ENABLE_DEV_LOGIN flag for the dev login bridge).
# They are left out so the contract is identical on every machine and in CI.
ENVIRONMENT_DEPENDENT_TAGS = frozenset({"Voice AI (Local)", "Local Dev Login"})


def _referenced_schemas(node, found: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            found.add(ref.rsplit("/", 1)[1])
        for value in node.values():
            _referenced_schemas(value, found)
    elif isinstance(node, list):
        for value in node:
            _referenced_schemas(value, found)


def _without_environment_dependent_routes(document: dict) -> dict:
    paths = {}
    for path, operations in document["paths"].items():
        kept = {
            method: operation
            for method, operation in operations.items()
            if not ENVIRONMENT_DEPENDENT_TAGS.intersection(operation.get("tags", []))
        }
        if kept:
            paths[path] = kept
    document["paths"] = paths

    schemas = document.get("components", {}).get("schemas", {})
    needed: set[str] = set()
    _referenced_schemas(paths, needed)
    pending = list(needed)
    while pending:
        inner: set[str] = set()
        _referenced_schemas(schemas.get(pending.pop(), {}), inner)
        pending.extend(inner - needed)
        needed |= inner
    if schemas:
        document["components"]["schemas"] = {name: body for name, body in schemas.items() if name in needed}
    return document


def _api_routes(routes):
    from fastapi.routing import APIRoute

    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from _api_routes(route.original_router.routes)


def _requires_principal(dependant) -> bool:
    from routes.authorization import require_principal

    return dependant.call is require_principal or any(
        _requires_principal(child) for child in dependant.dependencies
    )


def _with_bearer_security(document: dict, app) -> dict:
    """Declare bearer auth on every operation that really depends on
    `require_principal` (FastAPI only emits `security` for its own OAuth2
    helpers, which this app does not use), so the contract tells clients which
    calls need a token."""
    protected = {
        (method.lower(), route.path)
        for route in _api_routes(app.routes)
        if _requires_principal(route.dependant)
        for method in route.methods
    }
    for path, operations in document["paths"].items():
        for method, operation in operations.items():
            if (method, path) in protected:
                operation["security"] = [{"bearerAuth": []}]
    document.setdefault("components", {}).setdefault("securitySchemes", {})["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "OIDC access token from the configured identity provider.",
    }
    return document


def build_openapi() -> str:
    from main import app

    document = _without_environment_dependent_routes(copy.deepcopy(app.openapi()))
    document = _with_bearer_security(document, app)
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail instead of rewriting when stale")
    args = parser.parse_args(argv)

    generated = build_openapi()
    current = CONTRACT_PATH.read_text(encoding="utf-8") if CONTRACT_PATH.exists() else ""
    if args.check:
        if generated != current:
            print(f"{CONTRACT_PATH} is stale; run `python -m scripts.export_openapi`.", file=sys.stderr)
            return 1
        return 0

    CONTRACT_PATH.write_text(generated, encoding="utf-8", newline="\n")
    print(f"wrote {CONTRACT_PATH} ({len(generated)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
