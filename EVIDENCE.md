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

## Demo rehearsal evidence

| Date | Rehearsal # | Outcome | Adversarial judge | Notes |
|---|---|---|---|---|
| _pending_ | | | | Five consecutive offline runs required before this row can read "done" (`SIH26101_TEAM_ORCHESTRATION.md` section 5, Lane 6 acceptance evidence) |

## How to add a row

1. Run the actual command or retrieve the actual source.
2. Record the exact date, exact result (not a paraphrase), and who did it.
3. If it failed, record the failure -- do not wait for a passing run to add the row.
