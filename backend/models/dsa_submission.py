"""DSASubmission SQLAlchemy model — records every real Judge0 code-execution
attempt a player makes in the DSA sandbox (backend/routes/dsa_sandbox.py).

Problem *content* (backend/services/dsa_problems.py) is static, curated data,
the same idiom `services/curricula.py` already uses for competency
definitions -- it doesn't need its own table since it isn't user-editable.
What genuinely needs persisting is the real, per-attempt execution result:
this is that ground-truth record, not a fabricated summary.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Index, text
from sqlalchemy.orm import relationship
from db.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class DsaSubmission(Base):
    __tablename__ = "dsa_submissions"
    __table_args__ = (Index("ix_dsa_submissions_player_id", "player_id"),)

    submission_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False)
    # problem_id/competency_id/difficulty are denormalized copies of the
    # static problem definition (services/dsa_problems.py) at submission
    # time -- the problem bank has no DB row of its own to foreign-key to,
    # and copying these three fields is what lets this table stay a
    # complete, self-contained audit record even if a problem is ever
    # edited or removed from the static bank later.
    problem_id = Column(String, nullable=False, index=True)
    competency_id = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    code = Column(String, nullable=False)
    # python | javascript | java | cpp | csharp -- see services/dsa_lang_gen.py.
    # A real server_default (not just the ORM-level one) because every
    # historical row predates multi-language support and was genuinely
    # Python-only -- backfilling "python" here is a documented fact, not a
    # fabrication, and it keeps `alembic check` from drifting against the
    # migration's own server_default forever.
    language = Column(String, nullable=False, default="python", server_default=text("'python'"))
    # accepted | wrong_answer | runtime_error | compile_error |
    # time_limit_exceeded | judge_unavailable -- see
    # services/judge_client.py's STATUS_MAP for the authoritative mapping
    # from Judge0's own status IDs.
    status = Column(String, nullable=False)
    passed_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    # {test_index, stdin, expected_output, actual_output, stderr} for the
    # first failing case, or null when status == "accepted" -- real Judge0
    # output, never fabricated, so a learner can see exactly where their
    # code diverged.
    first_failure = Column(JSON, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    player = relationship("Player")
