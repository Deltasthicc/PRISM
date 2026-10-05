# Contracts index

> **SIH26075 transition:** these contracts remain active technical interfaces. References to
> SIH26101, MoSPI, iGOT, or NSSTA inside older sections record the feature that originally motivated
> a contract; they do not define current product scope. Current requirements and ownership are in
> `docs/SIH26075_PROBLEM_STATEMENT.md` and `docs/internal/SIH26075_TEAM_ORCHESTRATION.md`.

Thin, versioned interfaces coordinate the six lanes without shared file ownership — nine today,
listed below (not a fixed count: a lane can add a narrowly scoped contract, like Lane 2's
`encryption-key-ownership.md`, as its own primitives grow). See `docs/internal/SIH26075_TEAM_ORCHESTRATION.md`
section 4 ("Contract-first dependency model") for why these exist and who owns/consumes/approves
changes to each one.

| File | Owner | Consumers | Status |
|---|---|---|---|
| `data-authorization.md` | Lane 2 | Lanes 3, 4, 5, 6 | Real, implemented interface — storage/query semantics, subject export/deletion, retention job, backup/restore; not yet an HTTP surface |
| `identity-authorization.md` | Lane 2 | Lanes 1, 4, 5, 6 | Real, implemented interface — OIDC verification, RBAC and identity-binding primitives, live-verified; wired into the routes (89 of 103 operations require a bound principal; the rest are pinned in `backend/tests/test_route_auth_inventory.py`) |
| `encryption-key-ownership.md` | Lane 2 | Lanes 2, 5, 6 | Real, implemented, deliberately unwired versioned authenticated-encryption envelope — no current model uses it; not production KMS/HSM key custody |
| `production-database-hardening.md` | Lane 2 | Lane 6, deployment/security owner | **Specify-only** — three-role PostgreSQL privilege matrix, `search_path` pinning, TLS verification policy, connection-pool budget formula; nothing in it is implemented or dev-drilled, pending real numbers/decisions from Lane 6 |
| `competency-evidence.md` | Lane 3 | Lanes 1, 5, 6 | **v1** — real, implemented interface: gap/pathway result shape, four-field role-target precedence, evidence-coverage and determinism semantics, bounded lab; persistence, HTTP exposure of the lab and three of five evidence types are explicitly not implemented |
| `content-ai.md` | Lane 4 | Lanes 1, 5, 6 | Scaffold |
| `openapi.json` | Lane 5 | Lanes 1, 2, 3, 4, 6 | **Generated** from the running app by `python -m scripts.export_openapi`; a backend test fails if it drifts (voice and dev-login routers excluded) |
| `provider-adapter.md` | Lane 5 | Lanes 1, 2, 3, 4, 6 | Scaffold |
| `release-gates.md` | Lane 6 | all | **Partially defined** — real CI gates documented; browser E2E, accessibility, load and deployment gates explicitly not implemented |

A **scaffold** is a description of what the contract must eventually say, not a working interface
yet — it is not permission to skip writing the real contract before another lane depends on it; see
the "Change process" section inside each file. Lane 2's three files and Lane 3's
`competency-evidence.md` are no longer scaffolds: read them for what is actually implemented and
independently verified today, and note precisely what each still marks as not implemented
(route-level enforcement, multi-tenant isolation, production KMS/HSM key custody for Lane 2;
persistence, HTTP exposure of the lab, and the remaining evidence types for Lane 3) rather than
assuming "implemented" means "protects the running product."

