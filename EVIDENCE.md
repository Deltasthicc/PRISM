# Evidence log

Owner: shared -- every lane appends its own evidence here; Lane 6 maintains the file structure
(`SIH26101_TEAM_ORCHESTRATION.md` section 2). Required by
`SIH26101_MASTER_CHECKLIST.md` section 3.1.

This file is the append-only record of things that were actually checked, not asserted. Never
overwrite a failed result with a later success -- add a new row instead.

## Official-source evidence

Fill in once the SPOC/portal confirmation happens. Do not fabricate a row here before the source
has actually been retrieved.

| Date retrieved | Claim | Source URL | Local hash (if downloaded) | Retrieved by |
|---|---|---|---|---|
| _pending_ | SIH 2026 team/eligibility rules | _pending SPOC/portal link_ | _pending_ | _pending_ |
| _pending_ | Official problem-statement artifact/deadline | _pending portal link_ | _pending_ | _pending_ |

## Test/build evidence

| Date | Command | Result | Notes |
|---|---|---|---|
| 2026-08-29 | `python -m pytest` (backend) | 42 passed | See `SIH26101_MASTER_CHECKLIST.md` section 8 for the full log |
| 2026-08-29 | `npm run lint` (frontend) | passed | |
| 2026-09-01 | `backend/.venv/Scripts/python.exe -m pytest -q` | 237 passed; 2 pytest-cache permission warnings | Lane 2 Packages A–N accepted; detailed command/drill trail in `LANE2_SYNC.md` |
| 2026-09-01 | PostgreSQL 16 migration/startup drills | Alembic forward/backward, legacy adoption, partial-schema rejection and stale-revision startup refusal passed | Disposable/local Compose databases; head `cf4271f204a3` |
| 2026-09-01 | Local Keycloak 26.7.2 OIDC/RBAC verification | identity verifier, binding, bootstrap and authorization negatives passed | Development issuer only; no browser route or government IdP claim |
| 2026-09-01 | PostgreSQL backup/restore concurrency and adversarial tests | concurrent backup/restore completed; exact marker/revision/table checks passed; zero matching container temp residue | Local Docker drill only; no scheduled/offsite/encrypted DR claim |
| 2026-09-01 | Full backend gate after immutable Package P and independently accepted Package Q | 272 passed; 2 pytest-cache permission warnings | Package P destructive-path review findings remain explicitly open in `LANE2_SYNC.md`; pass count is not self-approval |

## Demo rehearsal evidence

| Date | Rehearsal # | Outcome | Adversarial judge | Notes |
|---|---|---|---|---|
| _pending_ | | | | Five consecutive offline runs required before this row can read "done" (`SIH26101_TEAM_ORCHESTRATION.md` section 5, Lane 6 acceptance evidence) |

## How to add a row

1. Run the actual command or retrieve the actual source.
2. Record the exact date, exact result (not a paraphrase), and who did it.
3. If it failed, record the failure -- do not wait for a passing run to add the row.
