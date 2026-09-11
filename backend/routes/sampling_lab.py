"""API for the bounded sampling-design virtual lab (backend/labs/sampling_lab.py).

The lab module itself has been real and fully tested since it was built --
deterministic expected outputs, resource-bounded submissions, no learner code
execution -- but had no route anywhere in the app, so it was never reachable
by a learner despite being genuine, working, safety-reviewed functionality.
This wires it in.

A correct submission is recorded as both an EvidenceRecord (competency-vector
scoring) and an AccuracyHistory update -- the exact same dual-write
competency_quiz.py's submit endpoint uses, for the same reason: PR #45 this
session found and fixed a real bug where recording only EvidenceRecord left
routes/game.py's Prerequisite Pathways room-unlock logic (which reads only
AccuracyHistory) never progressing. A new evidence-writing activity that
skipped that lesson would reintroduce the exact same bug for this lab.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from labs.sampling_lab import LabInputError, evaluate_submission, evidence_payload, list_tasks
from models.accuracy_history import AccuracyHistory
from models.governance import EvidenceRecord
from routes.learning_common import player_or_404
from services.game_logic import update_accuracy_history

router = APIRouter(prefix="/learning/sampling-lab", tags=["Sampling Lab"])


@router.get("/tasks")
async def get_tasks() -> dict:
    """List available lab tasks -- never includes the expected answer."""
    return {"tasks": list_tasks()}


class SubmissionIn(BaseModel):
    player_id: str
    task_id: str
    value: float


@router.post("/submit")
async def submit_answer(body: SubmissionIn, db: Session = Depends(get_db)) -> dict:
    player_or_404(db, body.player_id)
    try:
        result = evaluate_submission(body.task_id, body.value)
    except LabInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if result["correct"]:
        payload = evidence_payload(body.task_id)
        db.add(EvidenceRecord(player_id=body.player_id, **payload))

        acc = (
            db.query(AccuracyHistory)
            .filter(
                AccuracyHistory.player_id == body.player_id,
                AccuracyHistory.topic == payload["competency_id"],
            )
            .first()
        )
        if acc is None:
            acc = AccuracyHistory(player_id=body.player_id, topic=payload["competency_id"])
            db.add(acc)
            db.flush()
        new_l5, new_att, new_cor, new_acc = update_accuracy_history(
            acc.last_5_results or [], "correct", acc.attempts, acc.correct
        )
        acc.last_5_results = new_l5
        acc.attempts = new_att
        acc.correct = new_cor
        acc.recent_accuracy = new_acc
        if new_acc > 0.65:
            acc.mastered = True

        db.commit()

    return result
