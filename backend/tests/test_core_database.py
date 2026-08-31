"""Focused tests for the Lane 2 database backend selection."""

from db.database import normalize_database_url


def test_sqlite_database_url_is_unchanged():
    assert normalize_database_url("sqlite:///./app.db") == "sqlite:///./app.db"


def test_standard_postgresql_url_selects_psycopg_3():
    assert (
        normalize_database_url("postgresql://user:pass@db.example/skillquest")
        == "postgresql+psycopg://user:pass@db.example/skillquest"
    )


def test_legacy_postgres_url_selects_psycopg_3():
    assert (
        normalize_database_url("postgres://user:pass@db.example/skillquest")
        == "postgresql+psycopg://user:pass@db.example/skillquest"
    )


def test_explicit_postgresql_driver_is_preserved():
    url = "postgresql+psycopg://user:pass@db.example/skillquest"
    assert normalize_database_url(url) == url
