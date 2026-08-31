# Identity and authorization contract

Owner: Lane 2 (Core Platform, Identity & Data)

Consumers: Lanes 1, 4, 5 and 6

Status: **local OIDC/RBAC foundation under cross-review. No government IdP, browser login flow or
protected product route is claimed.**

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

The first organization administrator binding is a controlled bootstrap operation and is not
available through a public route. A production process for bootstrap approval and recovery is not
defined yet.

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
leaves neither change nor audit row. The audit actor is the verified external `(issuer|sub)` key,
never a caller-supplied username.

Authentication failures are not currently persisted to the application database; rate limiting,
security telemetry and IdP event retention are Lane 6 operational work. Tokens and raw claims must
never be written to `AuditEvent.details`.

## 6. Route handoff and present limitations

Lane 2 supplies verification, binding and policy primitives only. Lane 5 owns attaching them to
`backend/routes/**`, including negative API tests. Until that integration lands, the current routes
remain username/player-ID demo interfaces and the application must not be described as protected.

Still open:

- secure browser session/token storage and logout;
- a government-approved issuer/client registration and claims contract;
- department/organization row keys and cross-tenant negative query evidence;
- trainer/cohort assignment and scoped trainer reads;
- role-change ingestion/audit reconciliation from the IdP;
- route-level 401/403 wiring, rate limits and security telemetry;
- key rotation/outage drills beyond local Keycloak verification; and
- independent security/production authorization.

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
