"""Static checks for the versioned Lane 5 OpenAPI path inventory."""

import json
from pathlib import Path


EXPECTED_PATHS = {
    "/",
    "/health",
    "/game/player/create",
    "/game/player/{player_id}",
    "/game/player/by-username/{username}",
    "/game/player/{player_id}/hero",
    "/game/powerup/use",
    "/game/dungeons",
    "/game/dungeon/{dungeon_id}",
    "/game/session/start",
    "/game/room/enter",
    "/game/answer/submit",
    "/game/dungeon/{dungeon_id}/next-topic",
    "/game/hint/use",
    "/game/leaderboard",
    "/game/leaderboard/guild",
    "/game/guild/create",
    "/game/guild/join",
    "/game/guild/raid/join",
    "/game/guild/raid/submit",
    "/game/guild/raid/status",
    "/game/guild/{guild_id}",
    "/ai/question/generate",
    "/ai/answer/judge",
    "/ai/difficulty/next",
    "/ai/graph/next-topic",
    "/ai/dashboard/{player_id}",
    "/learning/curricula",
    "/learning/integrations/status",
    "/learning/profile/{player_id}",
    "/learning/assessment/{player_id}",
    "/learning/assessment/{player_id}/latest",
    "/learning/pathway/{player_id}",
    "/learning/quiz/generate",
    "/learning/quiz/{player_id}",
    "/learning/quiz/detail/{quiz_id}",
    "/learning/quiz/{quiz_id}/submit",
    "/learning/admin/overview",
}


def test_versioned_openapi_lists_current_public_paths():
    contract_path = Path(__file__).parents[2] / "docs" / "contracts" / "openapi.json"
    document = json.loads(contract_path.read_text(encoding="utf-8"))

    # The contract is now generated from the running app (see
    # tests/test_openapi_contract.py for the exact-match drift check), so it
    # may legitimately contain more paths than this core list; what must never
    # happen is a documented core path disappearing.
    assert document["openapi"].startswith("3.")
    assert document["info"]["title"] == "PRISM API"
    assert EXPECTED_PATHS <= set(document["paths"])


def test_protected_learning_paths_declare_bearer_security():
    contract_path = Path(__file__).parents[2] / "docs" / "contracts" / "openapi.json"
    paths = json.loads(contract_path.read_text(encoding="utf-8"))["paths"]
    protected_paths = {
        "/learning/profile/{player_id}",
        "/learning/assessment/{player_id}",
        "/learning/assessment/{player_id}/latest",
        "/learning/pathway/{player_id}",
        "/learning/quiz/generate",
        "/learning/quiz/{player_id}",
        "/learning/quiz/detail/{quiz_id}",
        "/learning/quiz/{quiz_id}/submit",
        "/learning/admin/overview",
    }

    for path in protected_paths:
        for operation in paths[path].values():
            assert operation["security"] == [{"bearerAuth": []}]
