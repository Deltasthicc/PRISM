"""API for the branching Judgment Simulation content type
(models/judgment_scenario.py) -- a decision tree an officer plays through
one choice at a time, seeing the honest consequence of each pick before
moving to the next decision point or an ending.

Three routes deliberately never leak the tree structure to a learner before
they've committed to a choice, since that would hand over the "right
answer":

- `GET /` lists only scenario_id/competency_id/title/situation_brief --
  never `nodes`.
- `GET /{scenario_id}/node/{node_id}` returns only a node's prompt and each
  choice's text/choice_id -- never `next_node_id`, `feedback` or
  `is_recommended`. `node_id="start"` is a reserved literal (never a real
  key in `nodes`) that resolves to the scenario's actual `start_node_id`,
  so a client can begin a run without already knowing that id.
- `POST /choose` is the one moment feedback/is_recommended are revealed --
  after the learner has already committed to the choice, not before.

`POST /complete` never trusts the client's own recommended-count or its
claim to have reached a genuine ending: it re-walks `nodes` from
`start_node_id` using only the submitted `path_taken`, exactly the same
"never trust the client's own verdict" posture labs/sampling_lab.py and
routes/sampling_lab.py hold for a submitted numeric answer. A successful
completion writes a real EvidenceRecord(evidence_type="observed_practice")
and updates AccuracyHistory for the scenario's competency_id -- the same
dual-write routes/sampling_lab.py does -- so a judgment simulation feeds
Prerequisite Pathways like every other real practice signal in this app.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from models.accuracy_history import AccuracyHistory
from models.governance import EvidenceRecord
from models.judgment_scenario import JudgmentScenario, JudgmentScenarioAttempt
from routes.authorization import require_own_player, require_principal
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal
from services.game_logic import update_accuracy_history
from services.judgment_scenario_content import is_terminal_node

router = APIRouter(prefix="/learning/scenarios", tags=["Judgment Simulations"])

# Reserved node_id literal for GET /{scenario_id}/node/{node_id} -- never a
# real key in a scenario's `nodes` dict (all real node ids come from the
# hand-authored content file). Resolves to that scenario's start_node_id so
# a client can begin a run without already knowing the internal start id.
_START_LITERAL = "start"


def _scenario_or_404(db: Session, scenario_id: str) -> JudgmentScenario:
    scenario = (
        db.query(JudgmentScenario)
        .filter(JudgmentScenario.scenario_id == scenario_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.get("/")
async def list_scenarios(
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
) -> dict:
    """Shared, curated scenario catalog -- never includes `nodes` (the
    decision tree, choice feedback and recommended flags)."""
    rows = db.query(JudgmentScenario).all()
    return {
        "scenarios": [
            {
                "scenario_id": row.scenario_id,
                "competency_id": row.competency_id,
                "title": row.title,
                "situation_brief": row.situation_brief,
            }
            for row in rows
        ]
    }


@router.get("/{scenario_id}/node/{node_id}")
async def get_node(
    scenario_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
) -> dict:
    """One node's prompt and choices -- `choice_id`/`text` only, never
    `next_node_id`, `feedback` or `is_recommended` (those are revealed only
    after a choice is committed, via POST /choose)."""
    scenario = _scenario_or_404(db, scenario_id)
    resolved_node_id = scenario.start_node_id if node_id == _START_LITERAL else node_id
    node = (scenario.nodes or {}).get(resolved_node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")

    return {
        "node_id": resolved_node_id,
        "prompt": node["prompt"],
        "choices": [
            {"choice_id": choice["choice_id"], "text": choice["text"]}
            for choice in node.get("choices") or []
        ],
    }


class ChooseRequest(BaseModel):
    player_id: str
    node_id: str
    choice_id: str


@router.post("/{scenario_id}/choose")
async def choose(
    scenario_id: str,
    body: ChooseRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
) -> dict:
    """Reveal one choice's consequence -- the one moment feedback and
    is_recommended are exposed. Nothing is persisted here: a run that is
    abandoned partway through is never worth a database row, only a full
    completion (POST /complete) is."""
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)
    scenario = _scenario_or_404(db, scenario_id)

    node = (scenario.nodes or {}).get(body.node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")

    choice = next(
        (c for c in node.get("choices") or [] if c["choice_id"] == body.choice_id),
        None,
    )
    if choice is None:
        raise HTTPException(status_code=404, detail="Choice not found")

    next_node_id = choice.get("next_node_id")
    next_node = (scenario.nodes or {}).get(next_node_id) if next_node_id else None
    is_ending = next_node_id is None or is_terminal_node(next_node or {})

    return {
        "feedback": choice["feedback"],
        "is_recommended": bool(choice.get("is_recommended")),
        "next_node_id": next_node_id,
        "is_ending": is_ending,
    }


class PathStep(BaseModel):
    node_id: str
    choice_id: str


class CompleteRequest(BaseModel):
    player_id: str
    path_taken: list[PathStep]


@router.post("/{scenario_id}/complete")
async def complete(
    scenario_id: str,
    body: CompleteRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
) -> dict:
    """Re-validate the entire path server-side by walking `nodes` from
    `start_node_id` -- never trust the client's own recommended-count or its
    claim to have reached a genuine ending. On success, writes a real
    EvidenceRecord and updates AccuracyHistory for the scenario's
    competency_id, exactly like routes/sampling_lab.py's submit endpoint."""
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)
    scenario = _scenario_or_404(db, scenario_id)
    nodes = scenario.nodes or {}

    if not body.path_taken:
        raise HTTPException(status_code=422, detail="path_taken must have at least one step")

    current_node_id: str | None = scenario.start_node_id
    recommended_count = 0
    reached_ending = False

    for step in body.path_taken:
        if current_node_id is None or step.node_id != current_node_id:
            raise HTTPException(
                status_code=422,
                detail=f"Path does not match the scenario graph at node {step.node_id!r}",
            )
        node = nodes.get(current_node_id)
        if node is None:
            raise HTTPException(status_code=422, detail=f"Unknown node {current_node_id!r}")

        choice = next(
            (c for c in node.get("choices") or [] if c["choice_id"] == step.choice_id),
            None,
        )
        if choice is None:
            raise HTTPException(
                status_code=422,
                detail=f"Choice {step.choice_id!r} is not a real edge from node {current_node_id!r}",
            )
        if choice.get("is_recommended"):
            recommended_count += 1

        next_node_id = choice.get("next_node_id")
        if next_node_id is None:
            current_node_id = None
            reached_ending = True
        else:
            current_node_id = next_node_id
            reached_ending = is_terminal_node(nodes.get(next_node_id) or {})

    if not reached_ending:
        raise HTTPException(
            status_code=422,
            detail="Path does not end at a genuine ending node",
        )

    total_choice_count = len(body.path_taken)
    ratio = recommended_count / total_choice_count if total_choice_count else 0.0

    attempt = JudgmentScenarioAttempt(
        player_id=body.player_id,
        scenario_id=scenario_id,
        path_taken=[step.model_dump() for step in body.path_taken],
        recommended_choice_count=recommended_count,
        total_choice_count=total_choice_count,
    )
    db.add(attempt)

    db.add(
        EvidenceRecord(
            player_id=body.player_id,
            competency_id=scenario.competency_id,
            evidence_type="observed_practice",
            value=ratio,
            detail=f"Judgment simulation: {scenario.title}",
        )
    )

    acc = (
        db.query(AccuracyHistory)
        .filter(
            AccuracyHistory.player_id == body.player_id,
            AccuracyHistory.topic == scenario.competency_id,
        )
        .first()
    )
    if acc is None:
        acc = AccuracyHistory(player_id=body.player_id, topic=scenario.competency_id)
        db.add(acc)
        db.flush()
    verdict = "correct" if ratio >= 0.5 else "incorrect"
    new_l5, new_att, new_cor, new_acc = update_accuracy_history(
        acc.last_5_results or [], verdict, acc.attempts, acc.correct
    )
    acc.last_5_results = new_l5
    acc.attempts = new_att
    acc.correct = new_cor
    acc.recent_accuracy = new_acc
    if new_acc > 0.65:
        acc.mastered = True

    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.attempt_id,
        "recommended_choice_count": attempt.recommended_choice_count,
        "total_choice_count": attempt.total_choice_count,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
    }


@router.get("/{scenario_id}/attempts")
async def list_attempts(
    scenario_id: str,
    player_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
) -> dict:
    """A learner's own past attempts at this scenario -- own-player scoped."""
    require_own_player(principal, player_id)
    player_or_404(db, player_id)
    _scenario_or_404(db, scenario_id)

    rows = (
        db.query(JudgmentScenarioAttempt)
        .filter(
            JudgmentScenarioAttempt.scenario_id == scenario_id,
            JudgmentScenarioAttempt.player_id == player_id,
        )
        .order_by(JudgmentScenarioAttempt.completed_at.desc())
        .all()
    )
    return {
        "attempts": [
            {
                "attempt_id": row.attempt_id,
                "path_taken": row.path_taken,
                "recommended_choice_count": row.recommended_choice_count,
                "total_choice_count": row.total_choice_count,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
            for row in rows
        ]
    }
