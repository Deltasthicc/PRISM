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
| 2026-09-01 | Live PostgreSQL 4-worker concurrency drill (Codex-reproduced race, pre-fix) | `deleted_sets=[set(), set(), {'1','2','3'}, set()]`; deleted/audit sum 3; 8 of 11 expired rows abandoned; 2 young rows correctly untouched | Confirmed a real defect: unlocked candidate SELECT let 4 concurrent PostgreSQL `--apply` workers all read the same batch. Full exact evidence and root cause in `LANE2_SYNC.md`; not overwritten by the fix below |
| 2026-09-01 | Full backend gate after Package P/S (`FOR UPDATE SKIP LOCKED` fix + O-B corrections) | 339 passed; 2 pytest-cache permission warnings; 0 failures | Implemented and live-tested by Claude Code, not yet Codex-accepted; see `LANE2_SYNC.md` |
| 2026-09-01 | Live PostgreSQL 4-worker concurrency drill (Codex's exact scenario, post-fix) | 11 expired + 2 young marker rows; per-worker deletions pairwise-disjoint; union of deleted IDs = all 11 expired IDs; deleted-count sum = 11; durable audit deleted-count sum = 11; both young rows untouched; final rerun returned `0/0` with zero new audit events; unmigrated-PostgreSQL `--apply` refusal re-confirmed unaffected | Same scenario shape as the pre-fix failure above, exact opposite (correct) result. Disposable marker rows and audit events fully cleaned up after; exact evidence in `LANE2_SYNC.md` |
| 2026-09-01 | Full backend gate after independent full Lane 2 audit (Codex ran out of session credits mid-review; Claude completed it solo) | 341 passed, 0 failures; 2 warnings observed in this exact run (SQLite datetime-adapter deprecations from two regression tests) — Codex separately reported 4 warnings (adding 2 `.pytest_cache` write-contention warnings) on a concurrent run against the same commit; both counts are accurate for their own run, not a discrepancy in the code | Claude Code; fixed two real findings from this audit: `delete_subject_data()`'s reported `deleted_counts` came from a pre-delete snapshot (could under-report under a concurrent write to the same player's own rows; the actual deletion was always correct) and `BoundPrincipal.audit_actor`'s delimiter-joined encoding was not collision-free (low severity given one issuer per deployment; fixed for consistency with the same fix already applied to `identity_bootstrap.py`). Both live-verified against real PostgreSQL |
| 2026-09-01 | Live PostgreSQL `audit_events` append-only trigger drill (migration `036de46dd515`) | Normal insert succeeds; direct `UPDATE` and `DELETE` against `audit_events` both rejected by the database with `RAISE EXCEPTION`; row survives fully unmodified; owning role's `ALTER TABLE ... DISABLE TRIGGER` bypass confirmed real, then `ENABLE TRIGGER` confirmed enforcement genuinely restored (not just silently still-disabled); `downgrade()` removes the trigger cleanly, `upgrade()` restores it; SQLite migration-chain regression suite (which runs upgrade/downgrade against a real SQLite file) confirms the migration is a true no-op there | Claude Code; a second, independent external audit proposed four DB-hardening items (RLS, full audit triggers, evidence self-hashing, legacy ETL) — three rejected with technical reasoning in `LANE2_SYNC.md` (RLS/ETL have no tenant model to target; self-hashing and the "logs lost on crash" trigger justification don't provide the claimed security property), this one correctly scoped and implemented instead |

## Demo rehearsal evidence

| Date | Rehearsal # | Outcome | Adversarial judge | Notes |
|---|---|---|---|---|
| _pending_ | | | | Five consecutive offline runs required before this row can read "done" (`SIH26101_TEAM_ORCHESTRATION.md` section 5, Lane 6 acceptance evidence) |

## How to add a row

1. Run the actual command or retrieve the actual source.
2. Record the exact date, exact result (not a paraphrase), and who did it.
3. If it failed, record the failure -- do not wait for a passing run to add the row.
