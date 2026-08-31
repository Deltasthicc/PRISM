from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from db.database import Base, SQLALCHEMY_DATABASE_URL
from models import (
    accuracy_history,
    dungeon,
    governance,
    guild,
    learning,
    player,
    question,
    session,
    submission,
)

_REGISTERED_MODEL_MODULES = (
    accuracy_history,
    dungeon,
    governance,
    guild,
    learning,
    player,
    question,
    session,
    submission,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL.replace("%", "%%"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Half A landed these models before the migration scaffold. The initial
# baseline intentionally omits them so a separately reviewed follow-up
# revision can introduce the governance tables. This switch is only used by
# the one baseline-generation command documented in LANE2_SYNC.md; normal
# autogenerate runs see every registered model.
_BASELINE_EXCLUDED_TABLES = {
    "audit_events",
    "evidence_records",
    "role_targets",
    "source_versions",
}


def include_object(obj, name, type_, reflected, compare_to):
    baseline = context.get_x_argument(as_dictionary=True).get("baseline") == "true"
    if not baseline:
        return True

    table_name = (
        name
        if type_ == "table"
        else getattr(getattr(obj, "table", None), "name", None)
    )
    return table_name not in _BASELINE_EXCLUDED_TABLES


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
