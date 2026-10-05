# e2e

Owner: Lane 6 (Quality, Security, Release & Evidence) — `docs/internal/SIH26075_TEAM_ORCHESTRATION.md`
section 2.

The browser tests live in [`frontend/e2e/`](../frontend/e2e) so they can use the frontend's own
`@playwright/test` install. Run them with `npm run build && npm run test:e2e` from `frontend/`; CI
runs them in the `frontend-checks` job.

What exists: sign-in routing for every registration state, skip link, document language and
direction, and onboarding-dialog focus handling. **Every backend and identity-provider call in
those specs is stubbed**, so they prove frontend behaviour, not integration.

Still open (do not claim): a suite against a live backend and Keycloak; the Academy → quiz →
progress golden path; refresh, back-navigation, double-submit, missing-API and second-learner
cases; automated accessibility scanning. Record any real run's command and result in the final
SIH26075 requirement evidence map.
