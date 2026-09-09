"""DSA sandbox routes — real problems, real Judge0 execution, real evidence.

Gated to DSA-fundamentals learners on the frontend (a learner who hasn't
selected that curriculum never sees the nav entry or page); the backend
itself doesn't hard-block other players from calling these endpoints, the
same way /learning/competency-quiz doesn't hard-block a player from
requesting a topic outside their chosen curriculum -- selection is a UX
concern, not an authorization boundary.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.accuracy_history import AccuracyHistory
from models.dsa_submission import DsaSubmission
from models.player import Player
from routes.authorization import require_own_player, require_permission_dependency
from schemas.dsa_sandbox import DsaProblemsResponse, DsaSubmitRequest, DsaSubmitResponse
from security.rbac import BoundPrincipal, Permission
from services import dsa_lang_gen
from services.dsa_problems import PROBLEMS, PROBLEMS_BY_ID, public_problem
from services.game_logic import update_accuracy_history
from services.judge_client import JudgeUnavailableError, run_test_case

router = APIRouter(prefix="/learning/dsa-sandbox", tags=["DSA Sandbox"])

_TERMINAL_STATUSES = {"wrong_answer", "runtime_error", "compile_error", "time_limit_exceeded"}


@router.get("/problems", response_model=DsaProblemsResponse)
async def list_problems():
    """Public catalogue -- same convention as GET /learning/curricula."""
    return {
        "problems": [public_problem(p) for p in PROBLEMS],
        "languages": {key: meta["label"] for key, meta in dsa_lang_gen.LANGUAGES.items()},
    }


@router.post("/submit", response_model=DsaSubmitResponse)
async def submit_solution(
    body: DsaSubmitRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    """Run real code against a problem's real test cases via Judge0, persist
    the real result, and -- on any terminal (non-judge-error) outcome --
    record real accuracy evidence for that DSA topic, the same table the
    dungeon map's room-unlock logic and the competency pathway both already
    read from. Solving problems here genuinely moves the same numbers
    /stats and /dungeon show, not a parallel, disconnected score."""
    require_own_player(principal, body.player_id)
    player = db.query(Player).filter(Player.player_id == body.player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    problem = PROBLEMS_BY_ID.get(body.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    language = body.language if body.language in dsa_lang_gen.LANGUAGES else dsa_lang_gen.DEFAULT_LANGUAGE
    full_source = dsa_lang_gen.full_source(language, body.code, problem)
    passed_count = 0
    first_failure = None
    final_status = "accepted"

    for index, test_case in enumerate(problem["test_cases"]):
        try:
            result = await run_test_case(
                full_source, test_case["stdin"], test_case["expected_output"], language=language
            )
        except JudgeUnavailableError:
            raise HTTPException(
                status_code=503, detail="The judge is unreachable. Try again."
            )

        if result["passed"]:
            passed_count += 1
            continue

        # Stop at the first failing case, same as a real online judge --
        # running every remaining case after the verdict is already decided
        # would just burn judge quota without telling the learner anything
        # new.
        final_status = result["status"] if result["status"] != "judge_unavailable" else "runtime_error"
        first_failure = {
            "test_index": index,
            "args": test_case["args"],
            "expected_output": test_case["expected_output"],
            "actual_output": result["stdout"],
            "stderr": result["stderr"],
            "compile_output": result["compile_output"],
        }
        break

    total_count = len(problem["test_cases"])
    accepted = passed_count == total_count and first_failure is None

    submission = DsaSubmission(
        submission_id=str(uuid.uuid4()),
        player_id=body.player_id,
        problem_id=problem["id"],
        competency_id=problem["competency_id"],
        difficulty=problem["difficulty"],
        code=body.code,
        language=language,
        status=final_status,
        passed_count=passed_count,
        total_count=total_count,
        first_failure=first_failure,
    )
    db.add(submission)

    # Every terminal verdict (accepted or not) is real practice evidence for
    # this DSA topic -- exactly the same AccuracyHistory row
    # _is_room_unlocked_for_player (routes/game.py) and analyse_competencies
    # (services/learning_engine.py, via measured_scores) already read.
    acc = db.query(AccuracyHistory).filter(
        AccuracyHistory.player_id == body.player_id,
        AccuracyHistory.topic == problem["competency_id"],
    ).first()
    if not acc:
        acc = AccuracyHistory(player_id=body.player_id, topic=problem["competency_id"])
        db.add(acc)
        db.flush()

    verdict = "correct" if accepted else "incorrect"
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

    return DsaSubmitResponse(
        submission_id=submission.submission_id,
        status=final_status,
        passed_count=passed_count,
        total_count=total_count,
        first_failure=first_failure,
        accuracy_history_updated=True,
    )
