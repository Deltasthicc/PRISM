# Lane 5 Execution Checklist

Last reviewed: 5 September 2026

## Immediate package

- [x] Protect admin overview with organization analytics permission.
- [x] Add latest-assessment endpoint with own-player scope.
- [x] Count latest distinct learner assessment streams.
- [x] Split learning routes by profile/competency, content/quiz, integration and analytics behavior.
- [x] Preserve all existing public `/learning/*` paths through the route split.
- [x] Publish the complete current OpenAPI surface and version it.
- [ ] Define stable error, pagination and idempotency conventions.
- [ ] Add provider contract tests for healthy, timeout, 401, 429, 5xx, duplicate and partial responses.
- [ ] Replace environment-only provider status with an authenticated capability check.
- [ ] Align leaderboard period and displayed copy.

## Dependencies and external gates

- [ ] Lane 2 review of route authorization composition.
- [ ] Lane 6 CI, contract compatibility and release evidence.
- [ ] Lane 1 browser PKCE/session integration.
- [ ] Lane 4 content job contract before queued job APIs.
- [ ] Approved iGOT/NSSTA endpoint, credentials, sandbox and data-sharing contract before any live adapter claim.

## Truth constraints

- `SIMULATED` is an offline fixture only.
- `CATALOGUE` means a public catalogue link, not synchronized provider data.
- `LIVE` requires a successful authenticated capability check.
- No provider IDs, enrolments, completions or government approvals may be fabricated.
