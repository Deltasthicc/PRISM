"""Real, working "QR-code live quiz session" feature -- a trainer hosts a
shared, paced session of an existing GeneratedQuiz (their own private quiz,
or any already-published one, exactly like routes/quiz_review.py's shared
Quiz Library), generates a short join_code (rendered client-side as a QR
code -- see frontend/app/host-session/page.jsx), and participants join on
their own phone or laptop to answer in lockstep with the host: every
participant sees the same question at the same time, the host controls
pacing, and everyone's real, honestly-computed score lands in a shared
leaderboard once the session ends.

Built to close a genuine competitive gap against a rival team's project,
which has this feature and this project didn't -- but implemented as a
first-class citizen of this codebase's real infrastructure, not a mockup:
it reuses GeneratedQuiz's `questions` JSON (models/learning.py) rather than
duplicating that schema, reuses services/quiz_scoring.py's exact weighted
scoring algorithm the single-player quiz flow already uses, and writes one
real GeneratedQuizAttempt row per participant on session end so this
integrates with, rather than duplicates, that existing attempt history.

Mounted at its own distinct prefix (/learning/live-sessions), not under
/learning/quiz -- see routes/learning_content.py's GET /learning/quiz/{player_id}
single-segment catch-all, which has previously and silently swallowed a
same-shape route registered after it. A distinct prefix sidesteps that
class of bug entirely rather than relying on registration-order care.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from models.learning import GeneratedQuiz, GeneratedQuizAttempt
from models.live_session import LiveQuizSession, LiveSessionParticipant
from models.player import Player
from routes.authorization import (
    require_own_player,
    require_permission_dependency,
    require_principal,
)
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission
from services.quiz_scoring import DIFFICULTY_WEIGHT, time_factor

router = APIRouter(prefix="/learning/live-sessions", tags=["Live Quiz Sessions"])

# No 0/O/1/I -- a live-classroom code is read off a projector and typed by
# hand on someone else's phone, so visual ambiguity is a real usability bug,
# not a cosmetic one. 6 chars from this 32-symbol alphabet is ~1.07e9
# possible codes -- collision-retry (below) is still good practice for a
# code space this size, not because a collision is likely, but because
# "very unlikely" isn't "impossible" for a value every participant in a
# room types by hand.
_JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_JOIN_CODE_LENGTH = 6
_MAX_JOIN_CODE_ATTEMPTS = 20


def _random_join_code() -> str:
    return "".join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(_JOIN_CODE_LENGTH))


def _generate_unique_join_code(db: Session) -> str:
    """Retry generation on a rare collision rather than trusting randomness
    blindly. Split out from `_random_join_code` so a test can monkeypatch
    just the random draw to force and verify the retry path."""
    for _ in range(_MAX_JOIN_CODE_ATTEMPTS):
        code = _random_join_code()
        exists = (
            db.query(LiveQuizSession.session_id)
            .filter(LiveQuizSession.join_code == code)
            .first()
        )
        if exists is None:
            return code
    raise RuntimeError("Could not generate a unique join code after repeated attempts")


def _session_or_404(db: Session, session_id: str) -> LiveQuizSession:
    session = db.query(LiveQuizSession).filter(LiveQuizSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found")
    return session


def _require_host(principal: BoundPrincipal, session: LiveQuizSession) -> None:
    require_own_player(principal, session.host_player_id)


def _serialize_session(db: Session, session: LiveQuizSession) -> dict:
    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == session.quiz_id).first()
    return {
        "session_id": session.session_id,
        "quiz_id": session.quiz_id,
        "quiz_title": quiz.title if quiz else None,
        "question_count": len(quiz.questions or []) if quiz else 0,
        "host_player_id": session.host_player_id,
        "join_code": session.join_code,
        "status": session.status,
        "current_question_index": session.current_question_index,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }


def _serialize_participant(participant: LiveSessionParticipant) -> dict:
    return {
        "participant_id": participant.participant_id,
        "session_id": participant.session_id,
        "player_id": participant.player_id,
        "answers": participant.answers or {},
        "score": participant.score,
        "joined_at": participant.joined_at.isoformat() if participant.joined_at else None,
    }


def _current_question_payload(quiz: GeneratedQuiz | None, index: int, reveal_answer: bool) -> dict | None:
    """The one question the room is currently on -- deliberately a narrow
    projection of GeneratedQuiz.questions[index], not the whole quiz. A
    participant device has no other route it can legitimately reach the
    quiz's own question content through: GET /learning/quiz/detail/{quiz_id}
    (routes/learning_content.py) only allows the quiz's owner or a
    PUBLISHED quiz, and a host may well be running a session from their own
    still-private quiz. `reveal_answer` withholds answer_index/explanation
    from a participant until they've actually answered this question (see
    get_session_state below) so joining a session never spoils the answer."""
    if not quiz or not quiz.questions or not (0 <= index < len(quiz.questions)):
        return None
    question = quiz.questions[index]
    payload = {
        "question": question.get("question"),
        "options": question.get("options"),
        "difficulty": question.get("difficulty", "medium"),
    }
    if reveal_answer:
        payload["answer_index"] = question.get("answer_index")
        payload["explanation"] = question.get("explanation")
    return payload


def _usernames_for(db: Session, player_ids: list[str]) -> dict[str, str]:
    if not player_ids:
        return {}
    rows = db.query(Player.player_id, Player.username).filter(Player.player_id.in_(player_ids)).all()
    return {row.player_id: row.username for row in rows}


class CreateSessionRequest(BaseModel):
    host_player_id: str
    quiz_id: str


@router.post("/")
async def create_session(
    body: CreateSessionRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_DRAFT_CREATE)
    ),
):
    """A trainer creates a live session from an existing quiz they can
    already see -- the exact same visibility rule
    routes/learning_content.py's get_quiz/submit_quiz established: their own
    quiz at any review_status, or anyone's PUBLISHED quiz."""
    require_own_player(principal, body.host_player_id)
    player_or_404(db, body.host_player_id)

    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == body.quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.player_id != body.host_player_id and quiz.review_status != "published":
        raise HTTPException(status_code=403, detail="This quiz belongs to a different player")
    if not quiz.questions:
        raise HTTPException(status_code=422, detail="This quiz has no questions to host a session with")

    session = LiveQuizSession(
        quiz_id=quiz.quiz_id,
        host_player_id=body.host_player_id,
        join_code=_generate_unique_join_code(db),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _serialize_session(db, session)


@router.get("/by-code/{join_code}")
async def resolve_join_code(
    join_code: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    """Resolve a join_code to its session -- deliberately does NOT require
    the caller to already know the host's identity, since this is exactly
    how a participant's own device finds the session after typing in the
    6-character code (or scanning the QR code that encodes a deep link to
    it). Still requires *a* valid authenticated principal, same as
    everywhere else in this app -- there is no anonymous-participant concept
    (see routes/authorization.py's require_principal)."""
    code = join_code.strip().upper()
    session = db.query(LiveQuizSession).filter(LiveQuizSession.join_code == code).first()
    if not session:
        raise HTTPException(status_code=404, detail="No live session found for that code")
    return _serialize_session(db, session)


class JoinRequest(BaseModel):
    player_id: str


@router.post("/{session_id}/join")
async def join_session(
    session_id: str,
    body: JoinRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)
    session = _session_or_404(db, session_id)
    if session.status == "ended":
        raise HTTPException(status_code=422, detail="This session has already ended")

    existing = (
        db.query(LiveSessionParticipant)
        .filter(
            LiveSessionParticipant.session_id == session_id,
            LiveSessionParticipant.player_id == body.player_id,
        )
        .first()
    )
    if existing:
        # Idempotent: rejoining (a phone refresh, a flaky connection retry)
        # just returns the same row rather than erroring or duplicating it.
        return _serialize_participant(existing)

    participant = LiveSessionParticipant(session_id=session_id, player_id=body.player_id)
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return _serialize_participant(participant)


@router.post("/{session_id}/start")
async def start_session(
    session_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    session = _session_or_404(db, session_id)
    _require_host(principal, session)
    if session.status != "waiting":
        raise HTTPException(status_code=422, detail=f"Session is '{session.status}', not 'waiting'")
    session.status = "active"
    db.commit()
    return _serialize_session(db, session)


@router.post("/{session_id}/advance")
async def advance_session(
    session_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    session = _session_or_404(db, session_id)
    _require_host(principal, session)
    if session.status != "active":
        raise HTTPException(status_code=422, detail=f"Session is '{session.status}', not 'active'")

    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == session.quiz_id).first()
    question_count = len(quiz.questions or []) if quiz else 0
    if session.current_question_index >= question_count - 1:
        raise HTTPException(
            status_code=422,
            detail="Already on the last question -- end the session instead of advancing further",
        )
    session.current_question_index += 1
    db.commit()
    return _serialize_session(db, session)


class LiveAnswerRequest(BaseModel):
    player_id: str
    question_index: int
    selected_index: int


@router.post("/{session_id}/answer")
async def submit_live_answer(
    session_id: str,
    body: LiveAnswerRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    """A participant's real-time answer while the session is active. Only
    accepted for the question the host is CURRENTLY showing -- a stale
    answer for a question the host has already moved past is rejected
    (422), not silently accepted, so a slow phone can't retroactively answer
    a question the room has moved on from."""
    require_own_player(principal, body.player_id)
    session = _session_or_404(db, session_id)
    if session.status != "active":
        raise HTTPException(status_code=422, detail=f"Session is '{session.status}', not 'active'")
    if body.question_index != session.current_question_index:
        raise HTTPException(
            status_code=422,
            detail="That question is no longer current -- the host has already moved on",
        )

    participant = (
        db.query(LiveSessionParticipant)
        .filter(
            LiveSessionParticipant.session_id == session_id,
            LiveSessionParticipant.player_id == body.player_id,
        )
        .first()
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Join this session before answering")

    # Reassign (rather than mutate in place) so SQLAlchemy's change
    # detection sees a new value on this plain JSON column.
    answers = dict(participant.answers or {})
    answers[str(body.question_index)] = body.selected_index
    participant.answers = answers
    db.commit()
    return _serialize_participant(participant)


@router.post("/{session_id}/end")
async def end_session(
    session_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    """Ends the session and computes every participant's real weighted
    score from their accumulated answers against the quiz's real
    answer_index/difficulty per question -- the same DIFFICULTY_WEIGHT
    algorithm services/quiz_scoring.py already provides for the
    single-player quiz flow (routes/learning_content.py).

    Deliberately uses a neutral (1.0, no bonus/penalty) time_factor for
    every answer: unlike the single-player flow, a live session has no
    per-question timing signal to honestly report (the host, not the
    participant, controls when a question ends), so fabricating one here
    would be exactly the kind of invented precision this project has
    repeatedly had to avoid elsewhere. Also writes one real
    GeneratedQuizAttempt row per participant, integrating with rather than
    duplicating that existing attempt history."""
    session = _session_or_404(db, session_id)
    _require_host(principal, session)
    if session.status == "ended":
        raise HTTPException(status_code=422, detail="Session has already ended")

    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == session.quiz_id).first()
    questions = (quiz.questions or []) if quiz else []
    participants = (
        db.query(LiveSessionParticipant)
        .filter(LiveSessionParticipant.session_id == session_id)
        .all()
    )

    for participant in participants:
        weighted_earned = 0.0
        weighted_possible = 0.0
        correct_count = 0
        answers = participant.answers or {}
        for index, question in enumerate(questions):
            difficulty = str(question.get("difficulty", "medium"))
            if difficulty not in DIFFICULTY_WEIGHT:
                difficulty = "medium"
            weight = DIFFICULTY_WEIGHT[difficulty]
            weighted_possible += weight

            selected = answers.get(str(index))
            if selected is None:
                continue  # unanswered (host moved on too fast) -- no credit, no fabricated guess

            # Neutral time factor -- see this endpoint's own docstring for why.
            factor = time_factor(difficulty, None)
            if selected == question.get("answer_index"):
                weighted_earned += weight * factor
                correct_count += 1

        weighted_score = (
            round((weighted_earned / weighted_possible) * 100, 1) if weighted_possible else 0.0
        )
        participant.score = weighted_score
        db.add(
            GeneratedQuizAttempt(
                quiz_id=session.quiz_id,
                player_id=participant.player_id,
                correct_count=correct_count,
                total_questions=len(questions),
                weighted_score=weighted_score,
            )
        )

    session.status = "ended"
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    return _serialize_session(db, session)


@router.get("/{session_id}")
async def get_session_state(
    session_id: str,
    player_id: str = Query(...),
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    """Cheap enough to poll every few seconds -- a handful of indexed row
    lookups, no aggregation heavier than counting keys in an already-loaded
    JSON blob. The host's view includes every participant's live progress
    (so they can see the room engaging in real time); a participant's view
    is just the shared pacing state plus their own progress."""
    require_own_player(principal, player_id)
    player_or_404(db, player_id)
    session = _session_or_404(db, session_id)
    is_host = session.host_player_id == player_id
    participant = (
        db.query(LiveSessionParticipant)
        .filter(LiveSessionParticipant.session_id == session_id, LiveSessionParticipant.player_id == player_id)
        .first()
    )
    if not is_host and participant is None:
        raise HTTPException(status_code=403, detail="Not the host and not a participant of this session")

    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == session.quiz_id).first()
    base = _serialize_session(db, session)
    has_answered_current = False
    if is_host:
        participants = (
            db.query(LiveSessionParticipant)
            .filter(LiveSessionParticipant.session_id == session_id)
            .order_by(LiveSessionParticipant.joined_at.asc())
            .all()
        )
        usernames = _usernames_for(db, [p.player_id for p in participants])
        base["participants"] = [
            {
                "player_id": p.player_id,
                "username": usernames.get(p.player_id, p.player_id),
                "answered_count": len(p.answers or {}),
                "score": p.score,
            }
            for p in participants
        ]
    else:
        has_answered_current = str(session.current_question_index) in (participant.answers or {})
        base["answered_count"] = len(participant.answers or {})
        base["has_answered_current_question"] = has_answered_current
        base["score"] = participant.score

    # The host set up the quiz (or it's published), so they already have
    # legitimate access to every answer; a participant only gets to see this
    # question's answer_index/explanation once they've actually answered it.
    base["current_question"] = _current_question_payload(
        quiz, session.current_question_index, reveal_answer=is_host or has_answered_current
    )
    return base


@router.get("/{session_id}/results")
async def get_session_results(
    session_id: str,
    player_id: str = Query(...),
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    """A real, honest leaderboard for this one live session -- every
    participant's final score, sorted descending. Only available once the
    session has actually ended, so it can never show a partial/in-progress
    ranking as if it were final."""
    require_own_player(principal, player_id)
    player_or_404(db, player_id)
    session = _session_or_404(db, session_id)
    is_host = session.host_player_id == player_id
    is_participant = (
        db.query(LiveSessionParticipant.participant_id)
        .filter(LiveSessionParticipant.session_id == session_id, LiveSessionParticipant.player_id == player_id)
        .first()
        is not None
    )
    if not is_host and not is_participant:
        raise HTTPException(status_code=403, detail="Not the host and not a participant of this session")
    if session.status != "ended":
        raise HTTPException(status_code=422, detail="Session hasn't ended yet")

    participants = (
        db.query(LiveSessionParticipant)
        .filter(LiveSessionParticipant.session_id == session_id)
        .order_by(LiveSessionParticipant.score.desc())
        .all()
    )
    usernames = _usernames_for(db, [p.player_id for p in participants])
    return {
        "session_id": session.session_id,
        "leaderboard": [
            {
                "player_id": p.player_id,
                "username": usernames.get(p.player_id, p.player_id),
                "score": p.score,
                "answered_count": len(p.answers or {}),
            }
            for p in participants
        ],
    }
