# e2e

Owner: Lane 6 (Quality, Security, Release & Evidence) — `docs/internal/SIH26075_TEAM_ORCHESTRATION.md`
section 2.

Empty scaffold. No end-to-end test tooling is installed in this repository yet. The next real
step here (`SIH26075_MASTER_CHECKLIST.md`, P0 golden path) is:

- Add Playwright (or an equivalent browser-automation tool) as a frontend/dev dependency.
- Cover the cross-domain browser smoke: Academy -> each of the four domains -> room renders ->
  one answer submits -> progress returns.
- Cover refresh, back navigation, double submit, missing API, empty data and a second learner.
- Wire the resulting suite into `.github/workflows/ci.yml` as a job — it is deliberately absent
  from that workflow today; see the comment at the top of that file.

Do not claim E2E coverage exists in README.md or the master checklist until a real suite runs
here and its command/result is recorded in the final SIH26075 requirement evidence map.
