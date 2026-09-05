# Identity and authorization contract

Owner: Lane 2 (Core Platform, Identity & Data)

Consumers: Lanes 1, 4, 5 and 6

Status: **local OIDC/RBAC foundation implemented and independently reviewed by both agents
(Packages I/J/K/M). Lane 5 PR #2 added the first route adapter and protected exactly
`GET /learning/admin/overview` and `GET /learning/assessment/{player_id}/latest`; Package 3 then
added separately composable deployment-tenant and own-player dependencies plus HTTP-level negative
coverage. Other product routes remain unprotected. Key rotation is proven via a local mock JWKS
server and the real `PyJWKClient` class this project ships -- not a live Keycloak key-rotation drill
specifically. No government IdP or browser login flow is claimed.**

This contract implements the server-side boundary required by `PS-16`. It does not make the
application production-authorized: the accountable IdP, organization/department model, route
integration, security assessment and operating approval remain open.

## 1. Protocol and trust boundary

The FastAPI backend is an OAuth resource server. It accepts an access token only after the AuthN
layer verifies the configured issuer, audience, asymmetric signature/allowlisted algorithm,
expiry and required subject claims using the issuer's discovered JWKS. It never accepts identity,
role, player or tenant authority from an unsigned header or request body.

The browser login client is a separate concern. Lane 1/Lane 5 must use Authorization Code with
PKCE (`S256`), exact pre-registered redirect URIs, transaction-bound state/nonce and secure token
handling. The implicit and resource-owner-password grants are forbidden. No such browser flow is
implemented by Lane 2.

The local Keycloak realm is a real development OIDC issuer with synthetic accounts. It is not a
government-approved IdP, production deployment definition or evidence that MoSPI SSO is available.

## 2. External identity versus application subject

The verified external identity key is the exact pair `(issuer, sub)`. `preferred_username`, email,
display name and role text are not identity keys. OIDC `sub` is never assumed to equal
`players.player_id`.

`identity_bindings` resolves that external pair to an optional local player:

| Field | Semantics |
|---|---|
| `binding_id` | Immutable application UUID for the binding record. |
| `issuer`, `subject_id` | Exact, unique external identity pair. |
| `player_id` | Optional FK to the learner record; null for non-learner administrative identities. One identity record per player in v1. |
| `active` | Disabled bindings fail closed but are retained; approved reactivation reuses the same row and is audited. |
| `created_at`, `updated_at` | UTC lifecycle timestamps. |

Issuer values use HTTPS. Plain HTTP is accepted only for loopback development issuers. Issuer
strings are matched exactly rather than normalized after verification.

`resolve_bound_principal()` rejects missing, inactive or nonmatching bindings. The resulting
principal receives `tenant_scope="deployment-database"` from server code; no token/request tenant
claim can override the database selected by `DATABASE_URL`.

### 2.1 First organization-administrator bootstrap

The first binding is created only through the out-of-band module
`python -m security.identity_bootstrap`; it is never available through a public route. The workflow:

1. requires the database to be at the repository's single Alembic head;
2. requires a fresh database session and takes a transaction-scoped PostgreSQL advisory lock (or
   an immediate SQLite write lock) before checking state;
3. refuses to run if *any* identity-binding row already exists;
4. requires an exact acknowledgement containing a canonical JSON identity key:
   `BOOTSTRAP ORGANIZATION ADMIN {"issuer":"<issuer>","subject_id":"<subject>"}`;
5. creates one active binding with no `player_id` and an atomic
   `identity_binding.bootstrap` audit event; and
6. records the supplied change/operator reference explicitly as out-of-band and not as a verified
   OIDC identity.

Example from `backend/`, after setting `DATABASE_URL` to the migrated target database:

```powershell
$issuer = 'https://identity.example.test/realms/sih'
$subject = 'issuer-provided-stable-subject-id'
$confirmation = 'BOOTSTRAP ORGANIZATION ADMIN {"issuer":"https://identity.example.test/realms/sih","subject_id":"issuer-provided-stable-subject-id"}'
& .\.venv\Scripts\python.exe -m security.identity_bootstrap `
  --issuer $issuer `
  --subject-id $subject `
  --operator-reference 'approved-change-CR-26101' `
  --reason 'initial organization administrator bootstrap' `
  --confirmation $confirmation
```

Before applying, an accountable operator must independently confirm in the IdP that this exact
issuer-scoped subject is assigned the `organization_admin` realm role. The binding does not store or
grant that role; runtime authorization still requires it in a verified access token. The CLI never
accepts a token, password or client secret. Direct database access can still bypass application
controls, so production database credentials/change approval remain operational controls rather
than something this module can prove.

After the first binding exists, all later binding changes use the active-organization-admin,
audited functions in `security.rbac`. Bootstrap checks both the binding table and its retained audit
sentinel while holding the lock, so verified subject deletion of the only linked binding does not
turn bootstrap into a recovery/rebinding bypass. Direct database deletion of both records remains
outside the application's threat boundary and requires database operational controls.

## 3. Roles and permissions

Only these application roles are recognized:

`learner`, `trainer`, `content_reviewer`, `department_admin`, `organization_admin`, `auditor`.

Unknown IdP roles are ignored. The current fixed permission matrix is deliberately minimal:

| Role | Granted permissions in Lane 2 policy |
|---|---|
| learner | Own player/profile/assessment/pathway reads and relevant own writes; practice writes; content-draft creation |
| trainer | Content-draft creation only |
| content reviewer | Content review and approval |
| department admin | No permissions yet; recognized but fail-closed until server-derived department scope exists |
| organization admin | Organization aggregate analytics, role-target management, identity-binding management, subject export and deletion |
| auditor | Audit read and subject export; never deletion |

Trainer access to another learner is intentionally absent. The repository has no server-side
trainer/cohort assignment, and a role string alone is not object authorization. Likewise,
department-admin permission does not become safe raw department filtering until a server-derived
department scope exists.

Role assertions originate in the verified IdP token in the current local profile, but only the
fixed allowlist and matrix can create permissions. The application does not yet mirror IdP role
assignment/change events into `audit_events`; production role-governance evidence therefore
remains incomplete.

## 4. Object/function authorization requirements

Lane 5 route code must compose all applicable checks; a role check alone is insufficient.

| Operation class | Required checks |
|---|---|
| Learner-owned read/write | Valid access token → active binding → relevant learner permission → `scoped_to_own_player()` against the locally bound player ID. |
| Content review/approval | Valid token → active binding → content-reviewer permission → content lifecycle/state checks owned by Lane 4. |
| Department aggregate | Valid token → active binding → department-admin permission → future server-derived department scope; unavailable until that scope exists. |
| Organization aggregate | Valid token → active binding → organization-admin permission; response must remain aggregate/privacy-safe. |
| Identity binding create/deactivate | Valid token → active organization-admin principal → deployment tenant check → atomic change plus audit event. |
| Subject export | Organization admin or auditor permission, verified reason and a dedicated DB session; endpoint still unimplemented. |
| Subject deletion | Organization admin permission, verified reason and exact confirmation; endpoint still unimplemented. |
| Audit read | Auditor permission; disclosure/pagination route still unimplemented. |

Missing/invalid tokens map to HTTP 401 with a Bearer challenge when Lane 5 supplies the route
adapter. A valid identity lacking role, permission, binding or object scope maps to HTTP 403. Error
responses and logs must not contain token bodies, signing keys, sensitive claims or learner data.

## 5. Audit and transaction rules

Binding create/deactivate/reactivate writes `identity_binding.create`,
`identity_binding.deactivate` or `identity_binding.reactivate` through
`record_audit_event(commit=False)` in the same transaction as the state change. A failed commit
leaves neither change nor audit row. The audit actor is the verified external `(issuer, sub)` key,
never a caller-supplied username, encoded as `BoundPrincipal.audit_actor` — a canonical JSON object
(`{"issuer":"...","subject_id":"..."}`), not a delimiter-joined string. A plain `f"{issuer}|{sub}"`
join is not injective (neither `validate_issuer()` nor token verification rejects a literal `|` in
`sub`), so this uses the same collision-free encoding already established by
`identity_bootstrap.expected_bootstrap_confirmation()`.

Authentication failures are not currently persisted to the application database; rate limiting,
security telemetry and IdP event retention are Lane 6 operational work. Tokens and raw claims must
never be written to `AuditEvent.details`.

## 6. Route handoff and present limitations

Lane 5 owns attaching Lane 2's verification, binding and policy primitives to
`backend/routes/**`, including negative API tests. The reusable adapters are in
`backend/routes/authorization.py`: `require_principal`,
`require_deployment_tenant_dependency`, `require_permission_dependency` and
`require_own_player_dependency`. The last dependency is the exact consumption path for a route with
a `player_id` path parameter: it composes verified principal, deployment tenant, fixed permission
and locally-bound own-player scope while returning the same `BoundPrincipal` object unchanged.

Lane 5 PR #2 attached the adapter to exactly two routes: organization-admin aggregate access at
`GET /learning/admin/overview`, and learner-owned assessment access at
`GET /learning/assessment/{player_id}/latest`. Package 3 attaches the latter through
`require_own_player_dependency` rather than translating object scope by hand. This is meaningful
partial route enforcement, not permission to describe the whole API or browser application as
protected; every other player-ID/form route remains a demo interface until it receives its own
permission and object-scope contract.

Still open:

- secure browser session/token storage and logout;
- a government-approved issuer/client registration and claims contract;
- department/organization row keys and cross-tenant negative query evidence;
- trainer/cohort assignment and scoped trainer reads;
- role-change ingestion/audit reconciliation from the IdP;
- route-level 401/403 wiring for the remaining product routes, rate limits and security telemetry;
- IdP-side outage drills (a real Keycloak/IdP process actually going down mid-request); and
- independent security/production authorization.

Key rotation is verified (Package P): `PyJWKClient`'s real kid-matching/refetch behavior (not a
stub) was exercised against a local HTTP server serving a mutating JWKS document -- an
already-cached key kept verifying its own tokens, a newly-rotated-in key's unmatched `kid` forced a
real refetch and then verified, and a retired key was correctly rejected once that refetch had
actually happened. See `backend/tests/test_core_identity.py`'s key-rotation tests and
`LANE2_SYNC.md`'s Activity log for exact evidence. This proves the mechanism through the real
`PyJWKClient` class this project ships, not a live Keycloak rotation drill specifically -- Keycloak
uses the same standard JWKS contract, so this is the correct thing to have proven, not a
substitute that happens to be easier.

## 7. Standards basis

- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0-18.html)
- [OpenID Connect Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0-22.html)
- [RFC 8414: OAuth 2.0 Authorization Server Metadata](https://www.rfc-editor.org/rfc/rfc8414.html)
- [RFC 8725: JWT Best Current Practices](https://www.rfc-editor.org/rfc/rfc8725.html)
- [RFC 9068: JWT Profile for OAuth 2.0 Access Tokens](https://www.rfc-editor.org/rfc/rfc9068.html)
- [RFC 9700: OAuth 2.0 Security Best Current Practice](https://www.rfc-editor.org/rfc/rfc9700.html)

RFC 9068 is the preferred interoperable JWT access-token profile. The local Keycloak token uses
its own access-token `typ` convention; unless AuthN explicitly enforces RFC 9068 `at+jwt`, this
project must not claim RFC 9068 conformance.
