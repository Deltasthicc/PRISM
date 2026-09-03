"""Codex-owned adversarial contract for Package W-B/W-C schema drift."""
from __future__ import annotations

import json

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from scripts import database_status as status_module
from scripts.database_status import TABLE_COUNTERS, get_table_row_counts


def _legacy_player_session():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE players ("
                "player_id VARCHAR PRIMARY KEY, username VARCHAR NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO players (player_id, username) "
                "VALUES ('legacy-1', 'private-a'), ('legacy-2', 'private-b')"
            )
        )
    return engine, sessionmaker(bind=engine)()


def test_count_uses_table_not_current_orm_columns_on_legacy_schema():
    engine, db = _legacy_player_session()
    try:
        counts, missing = get_table_row_counts(db)
        assert counts == {"players": 2}
        assert missing == sorted(set(TABLE_COUNTERS) - {"players"})
    finally:
        db.close()
        engine.dispose()


def test_cli_reports_legacy_schema_without_row_content_or_traceback(
    monkeypatch, capsys
):
    engine, db = _legacy_player_session()
    monkeypatch.setattr("db.database.SessionLocal", lambda: db)
    try:
        exit_code = status_module._main(["--json", "--check-migrations"])
        rendered = capsys.readouterr().out
        payload = json.loads(rendered)

        assert exit_code == 1
        assert payload["table_row_counts"] == {"players": 2}
        assert payload["missing_tables"] == sorted(
            set(TABLE_COUNTERS) - {"players"}
        )
        assert "private-a" not in rendered
        assert "private-b" not in rendered
    finally:
        db.close()
        engine.dispose()
