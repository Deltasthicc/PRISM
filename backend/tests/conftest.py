"""Shared pytest fixtures for backend/tests — owned by Lane 6 (Quality, Security, Release &
Evidence; see docs/internal/SIH26101_TEAM_ORCHESTRATION.md section 2). Add cross-lane fixtures here;
lane-specific fixtures belong in that lane's own test_<lane>_*.py file instead.

No shared fixtures exist yet, but this file is NOT an empty scaffold anymore -- see the
DISABLE_AUTH guard immediately below, which every test in this directory depends on whether it
knows it or not. The three flat legacy test files (test_progression.py, test_combat_model.py,
test_learning_platform.py) predate the per-lane filename convention (test_core_*.py,
test_competency_*.py, test_content_ai_*.py, test_api_integration_*.py, test_release_*.py) and
remain read-only regression baselines unless Lane 6 explicitly reassigns one
(docs/internal/SIH26101_TEAM_ORCHESTRATION.md section 2).
"""
import os

# A real independent audit found running this suite with a developer's own local backend/.env
# present (DISABLE_AUTH=true, the normal setting for running the app locally) produced 40 false
# failures -- every auth-enforcement test silently started exercising the demo bypass instead of
# real OIDC/RBAC verification, because routes/authorization.py's _DEMO_AUTH_DISABLED is computed
# ONCE from os.environ at import time and then frozen for the rest of the process. Test outcomes
# must not depend on whichever .env a given machine happens to have for running the app locally --
# CI has no .env at all, which is exactly why this only ever showed up locally.
#
# Setting this here, as the first thing this conftest module does, runs before pytest imports any
# test file in this directory (and therefore before any test file's own `from routes.authorization
# import ...` chain, which is what would otherwise freeze the contaminated value) -- and since
# db/database.py's load_dotenv() call does not override an already-set environment variable, this
# wins over a real backend/.env unconditionally, in either import order.
#
# A test that specifically wants to exercise the demo-bypass path itself still can, the same way
# test_content_ai_voice.py already does: `monkeypatch.setattr("routes.ai_voice._DEMO_AUTH_DISABLED",
# True)` (or the routes.authorization equivalent) inside that one test, rather than relying on
# ambient environment state for the whole session.
os.environ["DISABLE_AUTH"] = "false"
