"""Two-stage adaptive diagnostic API -- see services/adaptive_diagnostic.py
for the real engine and the full honesty rationale (never invents a
misconception signal that isn't really there, never pads a targeted
follow-up with unrelated items).

Stage 1 is a broad, competency-balanced quiz across a whole curriculum.
Stage 2, only offered when stage 1's wrong answers carried a real
misconception tag, is a small follow-up quiz built entirely from OTHER
real items already tagged with that same misconception -- deepening
practice exactly where the evidence points, the same "targeted diagnostic"
idea a two-stage adaptive assessment is supposed to deliver, without
fabricating item content to do it.

Every graded answer (both stages) writes the same real AccuracyHistory +
EvidenceRecord(evidence_type="observed_practice") pair
routes/competency_quiz.py's own submit_quiz() writes, so this feeds
Prerequisite Pathways and the competency vector exactly like every other
real practice signal in this app -- not a parallel, uncounted score.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from models.accuracy_history import AccuracyHistory
from models.governance import EvidenceRecord
from routes.authorization import require_own_player, require_principal
from routes.learning_common import player_or_404
from security.audit import record_audit_event
from security.rbac import BoundPrincipal
from services import adaptive_diagnostic as engine
from services.curricula import CURRICULA
from services.game_logic import update_accuracy_history

router = APIRouter(prefix="/learning/diagnostic", tags=["Adaptive Diagnostic"])


def _competency_labels() -> dict[str, str]:
    return {
        competency["id"]: competency["label"]
        for curriculum in CURRICULA.values()
        for competency in curriculum["competencies"]
    }


def _public_item(item: dict) -> dict:
    """Never leaks answer_index/explanation/misconception -- those only
    reach the client after grading, same boundary competency_quiz.py holds."""
    labels = _competency_labels()
    return {
        "item_id": item["item_id"],
        "question": item["question"],
        "options": item["options"],
        "competency_id": item["competency_id"],
        "competency_label": labels.get(item["competency_id"], item["competency_id"]),
        "difficulty": item["difficulty"],
    }


def _session_or_404(session_id: str) -> dict:
    session = engine.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Diagnostic session not found or expired")
    return session


def _record_evidence(db: Session, player_id: str, graded: list[dict], instrument: str) -> list[str]:
    """Same real dual-write competency_quiz.py's submit_quiz() does --
    AccuracyHistory (drives Prerequisite Pathways) + EvidenceRecord
    (competency vector). One row per competency_id touched in this stage."""
    accuracy_rows: dict[str, AccuracyHistory] = {}
    by_competency: dict[str, list[dict]] = {}
    for entry in graded:
        by_competency.setdefault(entry["competency_id"], []).append(entry)
        acc = accuracy_rows.get(entry["competency_id"])
        if acc is None:
            acc = (
                db.query(AccuracyHistory)
                .filter(AccuracyHistory.player_id == player_id, AccuracyHistory.topic == entry["competency_id"])
                .first()
            )
            if acc is None:
                acc = AccuracyHistory(player_id=player_id, topic=entry["competency_id"])
                db.add(acc)
                db.flush()
            accuracy_rows[entry["competency_id"]] = acc
        verdict = "correct" if entry["correct"] else "incorrect"
        new_l5, new_att, new_cor, new_acc = update_accuracy_history(
            acc.last_5_results or [], verdict, acc.attempts, acc.correct
        )
        acc.last_5_results = new_l5
        acc.attempts = new_att
        acc.correct = new_cor
        acc.recent_accuracy = new_acc
        if new_acc > 0.65:
            acc.mastered = True

    evidence_record_ids: list[str] = []
    for competency_id, entries in by_competency.items():
        correct = sum(1 for e in entries if e["correct"])
        total = len(entries)
        level = round(min(5.0, (correct / total) * 5)) if total else 0
        record = EvidenceRecord(
            player_id=player_id,
            competency_id=competency_id,
            evidence_type="observed_practice",
            value=level,
            detail=json.dumps(
                {"instrument": instrument, "correct": correct, "total": total},
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
        db.add(record)
        db.flush()
        evidence_record_ids.append(record.evidence_id)

    db.commit()
    return evidence_record_ids


class StartStage1Request(BaseModel):
    player_id: str
    curriculum_slug: str


@router.post("/stage1/start")
async def start_stage1(
    body: StartStage1Request,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)

    result = engine.start_stage1(body.curriculum_slug, body.player_id)
    if result is None:
        raise HTTPException(
            status_code=503,
            detail=f"No real multiple-choice content available yet for curriculum {body.curriculum_slug!r}",
        )
    session_id, items = result
    return {
        "session_id": session_id,
        "curriculum_slug": body.curriculum_slug,
        "items": [_public_item(item) for item in items],
    }


class AnswerIn(BaseModel):
    item_id: str
    selected_index: int = Field(ge=0, le=3)


class SubmitStage1Request(BaseModel):
    session_id: str
    player_id: str
    answers: list[AnswerIn] = Field(min_length=1)


@router.post("/stage1/submit")
async def submit_stage1(
    body: SubmitStage1Request,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)
    session = _session_or_404(body.session_id)
    if session["player_id"] != body.player_id:
        raise HTTPException(status_code=403, detail="This diagnostic session belongs to a different player")
    if session["stage1_submitted"]:
        raise HTTPException(status_code=422, detail="Stage 1 has already been submitted for this session")

    submitted_ids = {a.item_id for a in body.answers}
    if submitted_ids != set(session["stage1_item_ids"]):
        raise HTTPException(status_code=422, detail="Submit exactly the items issued for stage 1")

    pool = engine.curriculum_item_pool(session["curriculum_slug"])
    result = engine.grade_stage(session, 1, [a.model_dump() for a in body.answers], pool)

    target_misconception = engine.determine_target_misconception(result["misconception_counter"])
    session["stage1_submitted"] = True
    session["stage1_results"] = result
    session["target_misconception"] = target_misconception

    evidence_record_ids = _record_evidence(db, body.player_id, result["graded"], "adaptive-diagnostic-stage1")
    record_audit_event(
        db,
        actor=body.player_id,
        action="adaptive_diagnostic.stage1_submit",
        entity_type="player",
        entity_id=body.player_id,
        details={"session_id": body.session_id, "curriculum_slug": session["curriculum_slug"]},
        commit=True,
    )

    misconception_signal = None
    if target_misconception:
        stage2_candidates = engine.stage2_candidate_items(
            session["curriculum_slug"], target_misconception, set(session["stage1_item_ids"])
        )
        misconception_signal = {
            "misconception": target_misconception,
            "label": engine.misconception_label(target_misconception) or target_misconception,
            "wrong_answer_count": result["misconception_counter"][target_misconception],
            "stage2_available": bool(stage2_candidates),
            "stage2_item_count_available": len(stage2_candidates),
        }

    return {
        "session_id": body.session_id,
        "correct": result["correct"],
        "total": result["total"],
        "graded": result["graded"],
        "misconception_signal": misconception_signal,
        "evidence_record_ids": evidence_record_ids,
    }


class Stage2ActionRequest(BaseModel):
    session_id: str
    player_id: str


@router.post("/stage2/start")
async def start_stage2(
    body: Stage2ActionRequest,
    principal: BoundPrincipal = Depends(require_principal),
):
    require_own_player(principal, body.player_id)
    session = _session_or_404(body.session_id)
    if session["player_id"] != body.player_id:
        raise HTTPException(status_code=403, detail="This diagnostic session belongs to a different player")
    if not session["stage1_submitted"]:
        raise HTTPException(status_code=422, detail="Submit stage 1 before starting stage 2")
    if not session["target_misconception"]:
        raise HTTPException(
            status_code=422,
            detail="No real misconception signal was found in stage 1 -- there is nothing honest to target for stage 2",
        )
    if session["stage2_item_ids"] is not None:
        raise HTTPException(status_code=422, detail="Stage 2 has already been started for this session")

    candidates = engine.stage2_candidate_items(
        session["curriculum_slug"], session["target_misconception"], set(session["stage1_item_ids"])
    )
    if not candidates:
        raise HTTPException(
            status_code=422,
            detail="No further real items are tagged with this misconception yet -- cannot honestly build a stage 2 follow-up",
        )

    session["stage2_item_ids"] = [item["item_id"] for item in candidates]
    return {
        "session_id": body.session_id,
        "target_misconception": session["target_misconception"],
        "items": [_public_item(item) for item in candidates],
    }


class SubmitStage2Request(BaseModel):
    session_id: str
    player_id: str
    answers: list[AnswerIn] = Field(min_length=1)


@router.post("/stage2/submit")
async def submit_stage2(
    body: SubmitStage2Request,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)
    session = _session_or_404(body.session_id)
    if session["player_id"] != body.player_id:
        raise HTTPException(status_code=403, detail="This diagnostic session belongs to a different player")
    if session["stage2_item_ids"] is None:
        raise HTTPException(status_code=422, detail="Stage 2 has not been started for this session")
    if session["stage2_submitted"]:
        raise HTTPException(status_code=422, detail="Stage 2 has already been submitted for this session")

    submitted_ids = {a.item_id for a in body.answers}
    if submitted_ids != set(session["stage2_item_ids"]):
        raise HTTPException(status_code=422, detail="Submit exactly the items issued for stage 2")

    pool = engine.curriculum_item_pool(session["curriculum_slug"])
    result = engine.grade_stage(session, 2, [a.model_dump() for a in body.answers], pool)
    session["stage2_submitted"] = True
    session["stage2_results"] = result

    evidence_record_ids = _record_evidence(db, body.player_id, result["graded"], "adaptive-diagnostic-stage2")
    record_audit_event(
        db,
        actor=body.player_id,
        action="adaptive_diagnostic.stage2_submit",
        entity_type="player",
        entity_id=body.player_id,
        details={"session_id": body.session_id, "target_misconception": session["target_misconception"]},
        commit=True,
    )

    return {
        "session_id": body.session_id,
        "target_misconception": session["target_misconception"],
        "correct": result["correct"],
        "total": result["total"],
        "graded": result["graded"],
        "evidence_record_ids": evidence_record_ids,
        "combined_summary": {
            "stage1_correct": session["stage1_results"]["correct"],
            "stage1_total": session["stage1_results"]["total"],
            "stage2_correct": result["correct"],
            "stage2_total": result["total"],
        },
    }


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    player_id: str,
    principal: BoundPrincipal = Depends(require_principal),
):
    require_own_player(principal, player_id)
    session = _session_or_404(session_id)
    if session["player_id"] != player_id:
        raise HTTPException(status_code=403, detail="This diagnostic session belongs to a different player")
    return {
        "session_id": session_id,
        "curriculum_slug": session["curriculum_slug"],
        "stage1_submitted": session["stage1_submitted"],
        "stage1_results": session["stage1_results"],
        "target_misconception": session["target_misconception"],
        "stage2_started": session["stage2_item_ids"] is not None,
        "stage2_submitted": session["stage2_submitted"],
        "stage2_results": session["stage2_results"],
    }
