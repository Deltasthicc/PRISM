"""Shared, Lane 2-owned enum types for cross-cutting learner-scoped columns.

`LearningMode` is a presentation/audience discriminator only -- it says
which surface a learner is using, never an authorization decision.
`security.rbac`'s allowlisted roles and the deployment-database tenant
boundary (`docs/contracts/identity-authorization.md`) remain the only real
access-control axes; nothing may gate a permission or a route on this value.

Stored as a plain `String` (with a database-level `CHECK` constraint
restricting it to known values, not a native PostgreSQL `ENUM` type) so a
future mode can be added with a simple, cheap migration -- widening a
`CHECK` constraint's allowed set does not require the expensive
`ALTER TYPE ... ADD VALUE` machinery a native enum would.
"""
from __future__ import annotations

from enum import Enum


class LearningMode(str, Enum):
    """Which experience surface a learner is currently associated with.

    `PROFESSIONAL` is the base/default: the non-gamified, KCM/Mission
    Karmayogi-oriented professional workspace (Academy) -- competency
    assessment, gap analysis and recommendations run identically in both
    modes, this only ever changes which UI a learner is presented.
    `QUEST` is the existing optional dungeon/combat/XP layer, preserved as
    an explicit opt-in per the team's own recorded decision (see
    `SIH26101_MASTER_CHECKLIST.md`/`SIH26101_WINNING_PLAYBOOK.md`) rather
    than the default, so it stays a deliberate choice and never becomes
    the thing a government-official learner is defaulted into.

    This is intentionally the whole set for now. Lane 3 owns deciding which
    curricula/competencies are offered per mode (`services/curricula.py`);
    Lane 2 only stores which mode a learner is in.
    """

    PROFESSIONAL = "professional"
    QUEST = "quest"


LEARNING_MODE_VALUES: tuple[str, ...] = tuple(mode.value for mode in LearningMode)
DEFAULT_LEARNING_MODE: str = LearningMode.PROFESSIONAL.value
