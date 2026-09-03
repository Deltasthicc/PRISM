# Contracts index

Thin, versioned interfaces coordinate the six lanes without shared file ownership — eight today,
listed below (not a fixed count: a lane can add a narrowly scoped contract, like Lane 2's
`encryption-key-ownership.md`, as its own primitives grow). See `SIH26101_TEAM_ORCHESTRATION.md`
section 4 ("Contract-first dependency model") for why these exist and who owns/consumes/approves
changes to each one.

| File | Owner | Consumers | Status |
|---|---|---|---|
| `data-authorization.md` | Lane 2 | Lanes 3, 4, 5, 6 | Real, implemented interface — storage/query semantics, subject export/deletion, retention job, backup/restore; not yet an HTTP surface |
| `identity-authorization.md` | Lane 2 | Lanes 1, 4, 5, 6 | Real, implemented interface — OIDC verification, RBAC and identity-binding primitives, live-verified; not yet wired into `routes/**` |
| `encryption-key-ownership.md` | Lane 2 | Lanes 2, 5, 6 | Real, implemented, deliberately unwired versioned authenticated-encryption envelope — no current model uses it; not production KMS/HSM key custody |
| `competency-evidence.md` | Lane 3 | Lanes 1, 5, 6 | Scaffold |
| `content-ai.md` | Lane 4 | Lanes 1, 5, 6 | Scaffold |
| `openapi.json` | Lane 5 | Lanes 1, 2, 3, 4, 6 | Scaffold |
| `provider-adapter.md` | Lane 5 | Lanes 1, 2, 3, 4, 6 | Scaffold |
| `release-gates.md` | Lane 6 | all | Scaffold |

A **scaffold** is a description of what the contract must eventually say, not a working interface
yet — it is not permission to skip writing the real contract before another lane depends on it; see
the "Change process" section inside each file. Lane 2's three files and Lane 3's
`competency-evidence.md` are no longer scaffolds: read them for what is actually implemented and
independently verified today, and note precisely what each still marks as not implemented
(route-level enforcement, multi-tenant isolation, production KMS/HSM key custody for Lane 2;
persistence, HTTP exposure of the lab, and the remaining evidence types for Lane 3) rather than
assuming "implemented" means "protects the running product."

