# Contracts index

Six thin, versioned interfaces coordinate the six lanes without shared file ownership. See
`SIH26101_TEAM_ORCHESTRATION.md` section 4 ("Contract-first dependency model") for why these exist
and who owns/consumes/approves changes to each one.

| File | Owner | Consumers |
|---|---|---|
| `data-authorization.md` | Lane 2 | Lanes 3, 4, 5, 6 |
| `competency-evidence.md` | Lane 3 | Lanes 1, 5, 6 |
| `content-ai.md` | Lane 4 | Lanes 1, 5, 6 |
| `openapi.json` | Lane 5 | Lanes 1, 2, 3, 4, 6 |
| `provider-adapter.md` | Lane 5 | Lanes 1, 2, 3, 4, 6 |
| `release-gates.md` | Lane 6 | all |

Every file here is currently a **scaffold** — a description of what the contract must eventually
say, not a working interface. A scaffold is not permission to skip writing the real contract
before another lane depends on it; see the "Change process" section inside each file.
