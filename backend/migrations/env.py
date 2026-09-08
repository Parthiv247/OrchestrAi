from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.db.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url — DATABASE_URL wins (Railway/Supabase), else individual POSTGRES_* vars
_raw = os.getenv("DATABASE_URL", "")
if _raw:
    # Normalize to psycopg2 driver (asyncpg not supported by alembic)
    _db_url = _raw.replace("postgresql+asyncpg://", "postgresql+psycopg2://") \
                   .replace("postgres://", "postgresql+psycopg2://") \
                   .replace("postgresql://", "postgresql+psycopg2://")
else:
    _pg_host = os.getenv("POSTGRES_HOST", "localhost")
    _pg_port = os.getenv("POSTGRES_PORT", "5432")
    _pg_db   = os.getenv("POSTGRES_DB", "orchestrai")
    _pg_user = os.getenv("POSTGRES_USER", "admin")
    _pg_pass = os.getenv("POSTGRES_PASSWORD", "orchestrai_secret")
    _db_url = f"postgresql+psycopg2://{_pg_user}:{_pg_pass}@{_pg_host}:{_pg_port}/{_pg_db}"
config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    # Only manage tables defined in our ORM models. Ignore external tables.
    if type_ == "table" and name not in target_metadata.tables:
        return False
    return True


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        include_schemas=False,
        transaction_per_migration=True,  # each migration is isolated
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            include_schemas=False,
            transaction_per_migration=True,  # each migration gets its own transaction
            # so a failure in one migration doesn't abort all subsequent ones
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
