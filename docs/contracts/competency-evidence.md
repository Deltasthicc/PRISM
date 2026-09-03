# Competency, evidence and pathway service interface contract

Owner: Lane 3 (Competency & Learning Intelligence)

Consumers: Lanes 1, 5, 6

Change approval: Lane 2, Lane 5 and a named domain reviewer
(`SIH26101_TEAM_ORCHESTRATION.md` section 4)

Contract version: **v1**

Status: **v1 — the gap/pathway result shape, role-target selection, evidence-coverage semantics,
determinism (golden fixtures, section 5.1) and the bounded lab's input/output are defined and
test-covered. Persistence of evidence, HTTP exposure of the lab, three of the five evidence
types, an `activity` layer and dated target history are NOT implemented.** Section 8 states the
boundary exactly; section 9 lists what other
lanes must do before the loop closes end to end.

Everything here describes `backend/services/learning_engine.py`,
`backend/services/role_targets.py`, `backend/services/behavioral_anchors.py`,
`backend/services/curricula.py`, `backend/services/ps02_coverage.py` and
`backend/labs/sampling_lab.py` as they actually behave, and is pinned by
`backend/tests/test_competency_*.py` (136 backend tests passing on 2026-09-03). It is not a claim
of MoSPI/CBC validation — see section 6.

## 1. Versioning

Four independently-changeable policies, each carrying its own version so a consumer can tell
which one moved (`CLAUDE.md` invariant #5):

| Policy | Version field | Current value |
|---|---|---|
| Blend of demonstrated vs self-reported evidence (65/35) | `method.policy_version` | `prototype-v1` |
| Role-target selection | `method.role_target_framework_version` | `prototype-v1` |
| Behavioural anchor text | per-anchor `version` | `1` |
| Competency definition | per-competency `version` | `1` |
| Bounded lab | `lab_version` in every lab result | `prototype-v1` |

A consumer must not cache a result across a version change. Bumping any of these is a contract
change under section 10.

## 2. Role-target selection

```python
analyse_competencies(
    curriculum_slug: str,
    self_ratings: dict[str, float],      # {competency_id: 0-5}
    measured_scores: dict[str, float],   # {competency_id: 0-5}
    experience_level: str = "beginner",
    job_role: str = "",
    designation: str = "",
    current_assignment: str = "",
    department: str = "",
) -> dict
```

The four profile fields select the target, replacing the previous experience-level-only cap
(`SIH26101_MASTER_CHECKLIST.md` section 4.1). Precedence is most-specific-first and fixed:

`job_role` → `designation` → `current_assignment` → `department` → the competency's own
curriculum-wide `target_level`.

Keys are matched case-insensitively after trimming; a blank field is skipped. The first field
that carries a target *for that specific competency* wins — a field may match a role and still be
skipped for a competency it says nothing about. `matched_field` reports which field produced the
target (`null` for the curriculum default), so a UI can explain the selection rather than assert
it.

The experience-level ceiling still applies **on top of** the role target:
`pathway_target = min(role_target, experience_cap(experience_level))`. Caps are
beginner 3, intermediate 4, advanced 5, expert 5; an unrecognised level caps at 3.

`ValueError` is raised for an unknown `curriculum_slug`, or for a `self_ratings` key outside the
requested curriculum. Lane 5 maps both to HTTP 422 (unknown curriculum currently returns 404 on
`GET /learning/pathway/{player_id}`; that inconsistency is Lane 5's to resolve).

## 3. Evidence types and the blend

The evidence vocabulary is Lane 2's `EVIDENCE_TYPES` (`backend/models/governance.py`) verbatim,
so no relabeling is needed when evidence moves into `EvidenceRecord` rows:
`self_report`, `diagnostic`, `observed_practice`, `reviewer`, `provider_imported`.

Lane 3 currently **produces only two**: `self_report` (from `self_ratings`) and
`observed_practice` (from `measured_scores`, derived by Lane 5's route from `AccuracyHistory`).

| Evidence present | `observed_level` | `evidence` text |
|---|---|---|
| both | `measured × 0.65 + self × 0.35` | `65% demonstrated performance + 35% self-assessment` |
| demonstrated only | `measured` | `demonstrated performance` |
| self-report only | `self` | `self-assessment only; diagnostic evidence still required` |
| neither | `0.0` | `no evidence yet` |

The 65/35 blend is a transparent prototype policy, **not validated psychometrics**
(`CODEX.md` architecture invariants). Self-ratings never raise a score above demonstrated
performance on their own.

### "No evidence" is not low ability

`CLAUDE.md` invariant #3 is enforced in the data, not by consumer convention:

- `has_evidence: false` and `evidence_state: "NO EVIDENCE"`.
- `priority` is forced to `"unassessed"` — it can never read `critical`/`high`/`medium` without
  at least one evidence source behind it.
- `observed_anchor` is `null` (nothing observed, so nothing to describe), while `target_anchor`
  still resolves — the target is known even when the learner's level is not.
- `recommended_action` says a baseline diagnostic is needed, not that foundation remediation is.

`gap` is still computed and still drives sort order, so unassessed competencies stay visible in
`skill_gaps` and `pathway` rather than silently disappearing.

### Uncertainty

`confidence` is a qualitative band derived from coverage (`SIH26101_MASTER_CHECKLIST.md`
section 4.1, "display evidence coverage and uncertainty"):

| Coverage | `confidence` |
|---|---|
| nothing | `none` |
| `self_report` only | `low` |
| `observed_practice` only | `moderate` |
| both | `moderate` |

`high` is **deliberately unreachable**. Emitting it would imply a validated instrument that does
not exist; do not add it without one. This is a band, never a numeric confidence interval.

## 4. Competency result shape

Every entry in `competencies`, `skill_gaps` and `pathway` carries all of the following.

| Field | Type | Meaning |
|---|---|---|
| `competency_id` | string | Globally unique across all curricula |
| `label`, `description` | string | Display text from `curricula.py` |
| `prerequisites` | string[] | Competency IDs that must come first |
| `observed_level` | float, 2dp | Blended level on a 0–5 scale |
| `observed_label` | string | `not yet evidenced`/`foundation`/`working knowledge`/`practitioner`/`advanced`/`expert` |
| `observed_anchor` | object \| null | Anchor record for the observed level; null below level 1 or outside anchor coverage |
| `target_anchor` | object \| null | Anchor record for `pathway_target` |
| `pathway_target` | float | `min(role_target, experience_cap)` — what this learner is being asked to reach |
| `role_target` | float | The role's target before the experience ceiling |
| `role_target_source` | string | `internal-prototype` (a role override) or `curriculum-default` |
| `role_target_assurance` | string | Always `PROVISIONAL` today |
| `matched_role` | string | The matched key, lowercased, or `*` for the curriculum default |
| `matched_field` | string \| null | `job_role`/`designation`/`current_assignment`/`department`, null for the default |
| `gap` | float, 2dp | `max(0, pathway_target - observed_level)` |
| `priority` | string | `unassessed`/`critical`/`high`/`medium`/`maintain` |
| `has_evidence` | bool | Whether any evidence source exists |
| `evidence_sources` | string[] | Subset of `["observed_practice", "self_report"]`, in that order |
| `evidence_state` | string \| null | `"NO EVIDENCE"` when absent, else null |
| `confidence` | string | `none`/`low`/`moderate` |
| `evidence` | string | Human-readable explanation of how `observed_level` was derived |

Priority tiers, when evidence exists: `gap >= 2.5` critical, `>= 1.5` high, `>= 0.5` medium,
otherwise maintain.

An **anchor record** (`observed_anchor`, `target_anchor`) is:

```json
{
  "descriptor": "Can calculate a simple random sample size for a given confidence level and margin of error.",
  "source": "internal-prototype",
  "status": "unreviewed-pending-domain-expert",
  "assurance": "PROVISIONAL",
  "reviewed_by": null,
  "version": 1
}
```

Anchors cover the `official-statistics` curriculum only, and only the nine canonical demo-path
competencies within it — the PS-02 breadth competencies added alongside them are represented in
the taxonomy but not yet described level by level.
`behavioral_anchors.unanchored_competencies()` reports exactly which. For every other curriculum,
and for any unanchored competency, both anchor fields are `null` — consumers must handle null,
not assume prose exists.

## 4.1 PS-02 named competency coverage

`services/ps02_coverage.py` maps all 33 competencies named in
`docs/SIH26101_PROBLEM_STATEMENT.md`'s "Explicit competency scope" (10 statistical, 12 technical,
5 digital governance, 6 behavioural/managerial) to the competency IDs representing them, and
`validate_ps02_coverage()` raises at import if a mapping is dropped or points at a competency
that no longer exists.

`coverage_report()` returns that traceability per category — named item, competency ID, label,
curriculum slug and authoring status — for Lane 5 to expose and Lane 6 to use as evidence-matrix
input. Several named items deliberately share one competency (Python, R, Stata, SPSS and SAS all
map to `os_statistical_programming`); the mapping is explicit so a reviewer can challenge any
grouping. This proves *representation* only — every mapped competency is still `PROVISIONAL`.

## 5. Pathway and top-level result

`skill_gaps` is every competency with `gap >= 0.5`, sorted by descending gap then curriculum
order. `pathway` re-orders exactly those entries prerequisite-first (a competency never appears
before something it depends on), ties broken by the same gap/order rule, and adds two fields:

| Field | Type | Meaning |
|---|---|---|
| `step` | int | 1-based position |
| `recommended_action` | string | Baseline-diagnostic wording when `unassessed`, foundation wording below level 1, otherwise targeted learning |

Ordering is deterministic: identical inputs always produce an identical pathway, with no model
call anywhere in the computation.

The top-level result adds `curriculum_slug`, `curriculum_name`, `domain`, the five profile inputs
echoed back (`experience_level`, `job_role`, `designation`, `current_assignment`, `department`),
`method` (section 1's version fields plus `scale`, `demonstrated_weight`,
`self_assessment_weight`, `note`, `behavioral_anchor_default_source`,
`behavioral_anchor_default_status`), and `courses` — which comes from Lane 5's
`services/learning_catalog.py` and is governed by `provider-adapter.md`, not this contract.

### 5.1 Determinism and golden fixtures

"Deterministic" is proven, not asserted: `backend/tests/fixtures/golden_pathways/` pins six
realistic scenarios' full output (minus `courses`, which is Lane 5's env-dependent concern, not a
Lane 3 policy output). `test_competency_golden_fixtures.py` fails on any drift from the pinned
values, and separately calls each scenario twice in the same process and asserts byte-identical
JSON — the literal definition of deterministic, independent of whether any fixture file is stale.

Each fixture's numbers were hand-verified against the documented formulas before being trusted
(e.g. the blend scenario's `2.0 × 0.65 + 4.0 × 0.35 = 2.7`, gap `2.3`, landing in the `high` tier
just below the `critical` threshold — confirmed by hand, not assumed from generator output). A
fixture is golden because a human checked it once, not merely because a script produced it.

A fixture is regenerated only by deliberately running
`backend/tests/fixtures/generate_golden_fixtures.py` after a reviewed policy change (a new blend
weight, a new priority threshold, new anchor text), followed by hand-verifying the diff before
committing — never as a reflex to make a failing test pass. This satisfies
`SIH26101_TEAM_ORCHESTRATION.md` section 5's Lane 3 acceptance evidence: "Golden policy fixtures
produce stable gaps and pathways."

## 6. Status vocabulary

Lane 3 emits only the fixed documented terms (`CODEX.md` / `CLAUDE.md`: use `SIMULATED`,
`CATALOGUE`, `LIVE`, `PROVISIONAL`, `NO EVIDENCE` "precisely"):

- **`PROVISIONAL`** — every role target, behavioural anchor and competency definition. All are
  team-authored and unvalidated. `SIH26101_MASTER_CHECKLIST.md` section 3.3 requires exactly this
  label; section 4.1 marks MoSPI/NSSTA/CBC validation `BLOCKED-EXTERNAL`.
- **`NO EVIDENCE`** — a competency with no self-report and no demonstrated evidence.

The vocabulary defines no positive counterpart to `NO EVIDENCE`, so `evidence_state` is null when
evidence exists rather than carrying an invented term. `SIMULATED`/`CATALOGUE`/`LIVE` are provider
states owned by Lane 5.

Lane 3 must never describe its taxonomy or five levels as official FRAC/KCM. The structure follows
the public role → activity → competency pattern; the wording is the team's, pending review.

## 7. Bounded lab contract (PS-08)

`backend/labs/sampling_lab.py`. Safety posture is contractual, not incidental: no lab accepts,
compiles or executes learner-supplied code (`SIH26101_MASTER_CHECKLIST.md` section 4.4;
`SIH26101_WINNING_PLAYBOOK.md` section 10). Tasks are module constants; a learner supplies exactly
one number.

```python
list_tasks() -> list[dict]              # task_id, title, prompt, answer_label,
                                        # demonstrated_level, level_claim_assurance, competency_id
expected_answer(task_id) -> tuple[float, list[dict]]
evaluate_submission(task_id, submitted_answer) -> dict
evidence_payload(task_id) -> dict
```

`list_tasks()` never returns expected answers or task parameters. `evaluate_submission` returns
`lab_id`, `lab_version`, `task_id`, `competency_id`, `submitted`, `expected`, `tolerance`,
`correct`, `demonstrated_level` (null unless correct), `level_claim_assurance`, `steps`,
`feedback` and `evidence`.

- **Deterministic**: the same `task_id` always yields the same expected value and the same worked
  steps. Current tasks: `srs-basic` → 385, `srs-finite-population` → 382,
  `proportional-allocation` → 540.
- **Learning feedback**: `steps` is returned whether the answer was right or wrong.
- **Bounds**: `LabInputError` (a `ValueError` subclass) is raised for a non-numeric, boolean,
  NaN, infinite, negative or over-`MAX_ANSWER` submission, and for an unknown `task_id`. Lane 5
  must map it to HTTP 422, never 500.
- **Evidence**: a correct attempt returns an `EvidenceRecord`-shaped payload
  (`{competency_id, evidence_type: "observed_practice", value, detail}`); an incorrect attempt
  returns `evidence: null`. A failed attempt is never recorded as a low-ability judgment.

This module computes and explains only. It never writes to the database — persisting an attempt
is Lane 2/5 work.

## 8. What is not implemented

Stated plainly so no consumer or slide over-claims:

- **Three of five evidence types are never produced.** `diagnostic`, `reviewer` and
  `provider_imported` exist in the vocabulary only. Full separation needs Lane 2's
  `EvidenceRecord` rows.
- **Nothing is persisted by Lane 3.** Evidence, targets and lab attempts are computed in memory
  and returned; storage is Lane 2's, exposure is Lane 5's.
- **The lab has no HTTP route.** It is importable and tested, not reachable from the browser.
- **The engine's role fields are not yet wired.** `routes/learning.py` still passes only
  `experience_level`, so the four-field targeting is unreachable through the API (section 9.1).
- **No `activity` layer.** FRAC is role → activity → competency; this contract and Lane 2's
  `RoleTarget` both jump role → competency (section 9.3).
- **No dated target history.** No `valid_from`/`valid_to`; a target is simply "in effect now".
- **Anchors cover nine competencies** in one curriculum (`official-statistics`) out of four
  curricula. PS-02 breadth competencies are represented but unanchored; see
  `unanchored_competencies()`.
- **PS-02 coverage is representation, not validation.** Every named competency maps to a real
  competency, but all of them are `PROVISIONAL`.
- **No override/appeal, no readiness metric.** Both are Lane 3 "next package" items.
- **No MoSPI/CBC/NSSTA validation of anything here.** `BLOCKED-EXTERNAL`.

## 9. Open handoffs

Filed per `SIH26101_TEAM_ORCHESTRATION.md` section 8 — Lane 3 does not edit another lane's files.

### 9.1 Lane 5 — pass the profile fields through

`routes/learning.py`'s `assess_competencies()` and `get_pathway()` call `analyse_competencies()`
with `experience_level` only. Both should also pass `profile.job_role`, `profile.designation`,
`profile.current_assignment` and `profile.department`. All four are optional keyword arguments
defaulting to `""`, so the current call sites keep working unchanged — this is additive, not
breaking. Until it lands, `SIH26101_WINNING_PLAYBOOK.md` section 2's prohibition still applies:
do not describe the API as "role-aware", because through HTTP it is not yet.

### 9.2 Lane 5 — expose and persist the lab

Needs `GET` for `list_tasks()` and `POST` for `evaluate_submission()`, mapping `LabInputError`
to 422. On a correct attempt, persist the returned `evidence` payload so the result feeds back
into `measured_scores` — that is what closes `SIH26101_WINNING_PLAYBOOK.md` section 1's
target → evidence → gap → practice → reassessment loop and satisfies PS-10.

### 9.3 Lane 2 — `RoleTarget` key semantics and the activity layer

`RoleTarget.role` is documented as "a designation or job_role string, or `*`". This contract
selects targets from `current_assignment` and `department` as well
(`SIH26101_MASTER_CHECKLIST.md` section 4.1 requires all four), which that column cannot express
without a widened definition or a key-type column. Separately, neither model has an `activity`
layer, while `SIH26101_WINNING_PLAYBOOK.md` section 8 scripts the team to describe the data model
as role → activity → competency. Both need a decision before that claim is made on stage.

### 9.4 Lane 6 — stale claims in root docs

`README.md` and `SIH26101_MASTER_CHECKLIST.md` still state that targeting is experience-level-only
and that stored role fields do not affect targets. That is now false at the service layer (true
still at the HTTP layer until 9.1 lands). `SIH26101_WINNING_PLAYBOOK.md` section 8 also scripts
"anchors derived from public role and training sources"; the accurate phrasing is that they follow
FRAC's structure with team-authored wording, pending review.

## 10. Change process

`SIH26101_TEAM_ORCHESTRATION.md` section 8: open a proposal with old/new examples and
compatibility impact; the owner and named approvers (Lane 2, Lane 5, domain reviewer) accept or
reject; the producer change merges first with compatibility tests; consumers update in separate
PRs; Lane 6 verifies the integrated story.

Additive optional fields are compatible and do not require a version bump. Removing or retyping a
field in sections 4, 5 or 7, changing precedence in section 2, changing the blend weights or a
priority/confidence threshold, or introducing a new status term all require a contract version
bump and approval.
