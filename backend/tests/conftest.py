"""
pytest configuration for OrchestrAI backend tests.

Strategy:
  - Use FastAPI TestClient (sync WSGI-style).
  - Patch psycopg2.connect so tests never need a live PostgreSQL.
  - Set X-Dev-Mode header to bypass JWT middleware.
  - Tests verify HTTP status codes and response shapes — not DB state.
"""
import os
import sys
import types
import pytest
from unittest.mock import MagicMock, patch

# ── Make backend importable without installing the package ─────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ── Stub out heavy dependencies before they're imported ───────────────────────

def _stub_module(name: str, **attrs):
    """Create a minimal stub module so imports don't crash."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# SQLAlchemy async engine (not needed in tests)
_stub_module(
    "sqlalchemy.ext.asyncio",
    create_async_engine=MagicMock(),
    AsyncSession=MagicMock(),
    async_sessionmaker=MagicMock(),
)

# Stub chromadb
_chroma = _stub_module("chromadb", Client=MagicMock(), HttpClient=MagicMock())
_stub_module("chromadb.utils", embedding_functions=MagicMock())
_stub_module("chromadb.utils.embedding_functions", SentenceTransformerEmbeddingFunction=MagicMock())

# Stub langchain / langgraph
_stub_module("langchain_core", messages=MagicMock())
_stub_module("langchain_core.messages", HumanMessage=MagicMock(), AIMessage=MagicMock(), SystemMessage=MagicMock())
_stub_module("langchain_groq", ChatGroq=MagicMock())
_stub_module("langgraph.graph", StateGraph=MagicMock(), END="__end__")
_stub_module("langgraph.graph.state", StateGraph=MagicMock())
_stub_module("langgraph.checkpoint.memory", MemorySaver=MagicMock())
_stub_module("langsmith", traceable=lambda f: f)

# Stub scikit-learn
_stub_module("sklearn.ensemble", IsolationForest=MagicMock())
_stub_module("sklearn", ensemble=MagicMock())

# Stub snowflake
_stub_module("snowflake.connector", connect=MagicMock())
_stub_module("snowflake", connector=MagicMock())

# Stub docker
_stub_module("docker", from_env=MagicMock())

# Stub sentence_transformers
_stub_module("sentence_transformers", SentenceTransformer=MagicMock())

# Stub dbt
_stub_module("dbt.cli.main", dbtRunner=MagicMock(), dbtRunnerResult=MagicMock())

# Stub sqlglot
import unittest.mock as _um
_glot = _stub_module("sqlglot")
_glot.parse_one = _um.MagicMock(return_value=MagicMock())
_glot.errors = _stub_module("sqlglot.errors", SqlglotError=Exception)

# Stub slowapi (may not be installed in test env)
try:
    import slowapi  # noqa
except ImportError:
    # RateLimitExceeded must be its OWN exception class — using Exception would register
    # the MagicMock handler for ALL exceptions and break Starlette error handling in tests.
    class _RateLimitExceeded(Exception):
        pass
    _stub_module("slowapi", Limiter=MagicMock(), _rate_limit_exceeded_handler=MagicMock())
    _stub_module("slowapi.util", get_remote_address=MagicMock())
    _stub_module("slowapi.errors", RateLimitExceeded=_RateLimitExceeded)


# ── Patch psycopg2.connect everywhere ─────────────────────────────────────────

class _FlexRow:
    """
    Fake DB row that supports both dict-style access (row["count"]) used by
    RealDictCursor-based queries and positional access (row[0]) used by plain
    cursors — so a single mock works for all query patterns.
    """
    def __init__(self, positional_value=0, dict_data: dict | None = None):
        self._val = positional_value
        self._data = dict_data or {}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._val
        return self._data.get(key, self._val)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __iter__(self):
        return iter(self._data.values() if self._data else [self._val])


def _make_mock_conn(rows=None):
    """Return a mock psycopg2 connection that yields `rows` from fetchall()."""
    rows = rows or []
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchall.return_value = rows
    # None = no row found; endpoints must guard against None before using the row
    mock_cursor.fetchone.return_value = rows[0] if rows else None
    mock_cursor.description = [(f"col{i}",) for i in range(len(rows[0]) if rows else 1)]
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    """Auto-patch psycopg2.connect for every test."""
    mock_conn = _make_mock_conn()
    monkeypatch.setattr("psycopg2.connect", lambda **kw: mock_conn)
    # Also patch via direct import paths used in route files
    for mod_path in [
        "backend.api.routes.healing",
        "backend.api.routes.pipelines",
        "backend.api.routes.analytics",
        "backend.api.routes.auth",
        "backend.api.routes.lineage",
        "backend.api.routes.quality",
        "backend.api.routes.reports",
        "backend.api.routes.notifications",
        "backend.api.routes.settings",
        "backend.api.routes.transformation",
    ]:
        try:
            mod = sys.modules.get(mod_path)
            if mod and hasattr(mod, "psycopg2"):
                monkeypatch.setattr(mod.psycopg2, "connect", lambda **kw: mock_conn)
        except Exception:
            pass
    return mock_conn


@pytest.fixture(scope="session")
def client():
    """Return a TestClient for the FastAPI app with dev mode header."""
    from fastapi.testclient import TestClient
    # async_engine is already stubbed via _stub_module("sqlalchemy.ext.asyncio", ...)
    # and backend.db.session imports from that stub, so no extra patch needed.
    from backend.main import app
    # raise_server_exceptions=False: Pydantic/LLM errors from mocked deps return 500 instead of re-raising
    with TestClient(app, headers={"X-Dev-Mode": "true"}, raise_server_exceptions=False) as c:
        yield c
