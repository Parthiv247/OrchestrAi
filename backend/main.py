import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# Load backend/.env with override=True (reload trigger) so its values win over Docker-injected vars
# (e.g. POSTGRES_HOST=postgres from docker-compose → host.docker.internal from .env)
# In Docker:  __file__ = /app/backend/main.py  →  .parent / ".env" = /app/backend/.env  ✓
# Natively:   __file__ = .../backend/main.py   →  .parent / ".env" = backend/.env       ✓
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ── Rate limiting ──────────────────────────────────────────────────────────────
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from .core.limiter import RATE_LIMIT_AVAILABLE as _RATE_LIMIT_AVAILABLE
    from .core.limiter import limiter as _limiter
except ImportError:
    _limiter = None
    _RATE_LIMIT_AVAILABLE = False
    _rate_limit_exceeded_handler = None
    RateLimitExceeded = Exception

# ── Structured logging (must be first, before any module imports) ──────────────
from .core.logging_config import configure_logging

configure_logging()

# Phase 1 — ETL Pipelines
# pipeline.py (old Phase-1 router) is retained for reference but no longer registered.
# All endpoints are now served by pipelines.py and healing.py.
# ML Metrics — anomaly detection model metrics + retraining
from .api.ml_metrics import router as ml_metrics_router

# Phase 4 — Analytics + Insights
from .api.routes.analytics import router as analytics_router

# Auth
from .api.routes.auth import router as auth_router
from .api.routes.connectors import router as connectors_router

# Phase 2 — Self-Healing Agents
from .api.routes.healing import router as healing_router

# Learning Agent — outcome tracking, MTTR trend, strategy performance
from .api.routes.learning_stats import router as learning_stats_router

# Lineage — dbt manifest parsing, column-level lineage
from .api.routes.lineage import router as lineage_router

# Notifications — alert rules engine, dispatch, history
from .api.routes.notifications import router as notifications_router
from .api.routes.pipelines import router as pipelines_router

# Data Quality — schema registry, drift detection, quality rules
from .api.routes.quality import router as quality_router

# Scheduled Reports — email digests, pipeline summaries
from .api.routes.reports import router as reports_router

# Platform Settings — team, API tokens, notifications, audit log
from .api.routes.settings import router as settings_router

# Phase 3 — Transformation + Optimization
from .api.routes.transformation import router as transformation_router
from .core.config import get_settings
from .core.ws_manager import ws_manager
from .db.models import Base
from .db.session import async_engine

settings = get_settings()


def _validate_startup_config() -> None:
    """Fail fast in production if critical env vars are missing or still at insecure defaults."""
    _env = os.getenv("APP_ENV", "development")
    if _env != "production":
        return
    errors: list[str] = []
    if not os.getenv("GROQ_API_KEY"):
        errors.append("GROQ_API_KEY is not set")
    if os.getenv("JWT_SECRET_KEY", "change_me_in_production") == "change_me_in_production":
        errors.append("JWT_SECRET_KEY is still the insecure default — set a strong secret")
    if not os.getenv("ENCRYPTION_KEY"):
        errors.append("ENCRYPTION_KEY is not set — connector credentials cannot be encrypted")
    if not os.getenv("CORS_ORIGINS"):
        errors.append("CORS_ORIGINS is not set — CORS will be restricted to localhost:3000 in production")
    if errors:
        msg = "OrchestrAI startup validation failed:\n" + "\n".join(f"  • {e}" for e in errors)
        raise RuntimeError(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_startup_config()
    # DB startup — hard 5-second timeout so a hung TCP connection doesn't block startup
    async def _init_db() -> None:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            _safety = [
                "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS approval_status TEXT DEFAULT 'pending'",
                "ALTER TABLE query_optimizations ADD COLUMN IF NOT EXISTS context TEXT DEFAULT 'manual'",
                """CREATE TABLE IF NOT EXISTS connector_configs (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    encrypted_creds TEXT NOT NULL,
                    status TEXT DEFAULT 'untested',
                    notes TEXT DEFAULT '',
                    last_tested_at TIMESTAMP,
                    test_message TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )""",
            ]
            for sql in _safety:
                try:
                    await conn.execute(__import__('sqlalchemy').text(sql))
                except Exception:
                    pass

    try:
        await asyncio.wait_for(_init_db(), timeout=15.0)
    except (asyncio.TimeoutError, Exception) as e:
        import logging
        logging.getLogger("orchestrai").warning(
            "DB not available at startup (will retry per-request): %s", e
        )
    # ML models — train if pkl files are missing (e.g. fresh Railway deploy)
    async def _ensure_ml_models() -> None:
        import subprocess
        import sys
        from pathlib import Path
        _ml_dir = Path(__file__).parent.parent / "ml"
        _model_path = _ml_dir / "isolation_forest.pkl"
        if not _model_path.exists():
            _train_script = _ml_dir / "train_models.py"
            if _train_script.exists():
                logging.getLogger("orchestrai").info(
                    "ML models not found — running train_models.py (first-time setup)"
                )
                try:
                    result = subprocess.run(
                        [sys.executable, str(_train_script)],
                        capture_output=True, text=True, timeout=120,
                    )
                    if result.returncode == 0:
                        logging.getLogger("orchestrai").info("ML models trained successfully.")
                    else:
                        logging.getLogger("orchestrai").warning(
                            "train_models.py exited with code %d: %s",
                            result.returncode, result.stderr[-500:]
                        )
                except Exception as e:
                    logging.getLogger("orchestrai").warning("ML training failed: %s", e)

    try:
        await asyncio.wait_for(_ensure_ml_models(), timeout=180.0)
    except asyncio.TimeoutError:
        logging.getLogger("orchestrai").warning("ML training timed out — continuing without models")
    except Exception as e:
        logging.getLogger("orchestrai").warning("ML startup check failed: %s", e)

    # Groq API key validation — fail loudly so the problem is obvious in logs
    async def _validate_groq_key() -> None:
        key = os.getenv("GROQ_API_KEY", "")
        if not key or key.startswith("gsk_") is False:
            logging.getLogger("orchestrai").error(
                "GROQ_API_KEY is missing or looks invalid. "
                "NL-to-SQL and cost optimizer will use fallback mode. "
                "Get a key at https://console.groq.com"
            )
            return
        try:
            import httpx
            r = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=10,
            )
            if r.status_code == 200:
                logging.getLogger("orchestrai").info("Groq API key validated OK.")
            elif r.status_code == 401:
                logging.getLogger("orchestrai").error(
                    "GROQ_API_KEY is EXPIRED or INVALID (HTTP 401). "
                    "NL-to-SQL will not work. Renew at https://console.groq.com"
                )
            else:
                logging.getLogger("orchestrai").warning("Groq API key check returned HTTP %d.", r.status_code)
        except Exception as e:
            logging.getLogger("orchestrai").warning("Could not validate Groq key (network): %s", e)

    try:
        await asyncio.wait_for(_validate_groq_key(), timeout=15.0)
    except Exception:
        pass

    # Seed demo data on first boot (only if tables are empty)
    async def _seed_demo_data() -> None:
        try:
            from .core.seed_demo import seed_if_empty
            await asyncio.get_event_loop().run_in_executor(None, seed_if_empty)
        except Exception as e:
            logging.getLogger("orchestrai").warning("Demo data seeding failed: %s", e)

    try:
        await asyncio.wait_for(_seed_demo_data(), timeout=60.0)
    except (asyncio.TimeoutError, Exception) as e:
        logging.getLogger("orchestrai").warning("Demo seeding skipped: %s", e)

    # Start the per-pipeline ingestion scheduler (auto-runs pipelines on their interval)
    try:
        from .scheduler import start as _start_scheduler
        _start_scheduler()
    except Exception as e:
        import logging
        logging.getLogger("orchestrai").warning("Scheduler failed to start: %s", e)
    # Capture the running loop so background threads can broadcast WS events
    ws_manager.set_loop(asyncio.get_event_loop())
    yield
    try:
        from .scheduler import stop as _stop_scheduler
        _stop_scheduler()
    except Exception:
        pass
    try:
        await async_engine.dispose()
    except Exception:
        pass
    try:
        from .db.pool import close_pool
        close_pool()
    except Exception:
        pass


app = FastAPI(
    title="OrchestrAI",
    description=(
        "**OrchestrAI** — Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines.\n\n"
        "Orchestrates 10 specialized LangGraph agents across 5 phases:\n"
        "1. **ETL Pipelines** — connector-driven ingestion with DuckDB + Snowflake\n"
        "2. **Self-Healing** — IsolationForest anomaly detection → LLM diagnosis → fix generation → Docker sandbox → HITL approval → deployment\n"
        "3. **Transformation** — dbt model generation, cost optimisation via Groq\n"
        "4. **Analytics** — NL-to-SQL with ChromaDB RAG, schema-aware query builder\n"
        "5. **Learning** — ChromaDB fix store, MTTR trend tracking, strategy selection\n\n"
        "All endpoints require `Authorization: Bearer <token>` in production "
        "(set `APP_ENV=production`). In development, pass `X-Dev-Mode: true` to bypass auth."
    ),
    version="2.0.0",
    contact={"name": "OrchestrAI Team", "email": "admin@orchestrai.ai"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "Health",                  "description": "Liveness and readiness probes"},
        {"name": "Phase 1 — Pipelines",     "description": "ETL pipeline CRUD, execution, run history"},
        {"name": "Phase 1 — Connectors",    "description": "Connector catalog, saved connections, test"},
        {"name": "Phase 2 — Self-Healing",  "description": "Healing trigger, incident list/detail, approve/reject"},
        {"name": "Phase 3 — Transformation","description": "dbt model generation, query cost optimiser"},
        {"name": "Phase 4 — Analytics",     "description": "NL-to-SQL, schema browser, query execution"},
        {"name": "Data Quality",            "description": "Schema registry, drift detection, quality rules"},
        {"name": "Lineage",                 "description": "Column-level lineage from dbt manifest"},
        {"name": "Learning",                "description": "MTTR trend, strategy performance, RAG stats"},
        {"name": "ML — Anomaly Detection",  "description": "IsolationForest metrics, model retraining"},
        {"name": "Notifications",           "description": "Alert rules engine, Slack dispatch, history"},
        {"name": "Reports",                 "description": "Scheduled email digests"},
        {"name": "Settings",                "description": "Team, API tokens, notifications config, audit log"},
        {"name": "Auth",                    "description": "JWT login / token refresh"},
    ],
    lifespan=lifespan,
)

# Attach rate limiter
if _RATE_LIMIT_AVAILABLE:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_APP_ENV = os.getenv("APP_ENV", "development")   # set APP_ENV=production in prod deployments

# CORS — allow_origins=["*"] is incompatible with allow_credentials=True (browsers reject it).
# Read allowed origins from env; fall back to localhost:3000 in dev.
# In production, set CORS_ORIGINS="https://app.example.com,https://www.example.com"
_raw_origins = os.getenv("CORS_ORIGINS", "")
_CORS_ORIGINS: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else (["*"] if _APP_ENV != "production" else ["http://localhost:3000"])
)
# credentials=True requires explicit origins — never combine with wildcard
_CORS_CREDENTIALS = "*" not in _CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=_CORS_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compress responses ≥ 1 KB — reduces bandwidth ~70% for JSON-heavy endpoints
app.add_middleware(GZipMiddleware, minimum_size=1024)

@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Enforce a 60-second hard timeout on all HTTP requests."""
    try:
        return await asyncio.wait_for(call_next(request), timeout=60.0)
    except asyncio.TimeoutError:
        return JSONResponse(
            {"detail": "Request timed out after 60 seconds"},
            status_code=504,
        )


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    JWT authentication middleware.

    BYPASS conditions (no token required):
      - Path starts with /api/auth/   (login / register)
      - Path is /health, /docs, /openapi.json, /redoc, or /ws
      - APP_ENV != production AND header X-Dev-Mode: true  (dev/staging only)

    In production (APP_ENV=production) the X-Dev-Mode bypass is disabled and
    every protected route requires a valid Bearer token.
    """
    # Always pass through CORS preflight so the CORS middleware can respond correctly
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    _PUBLIC = ("/api/auth/", "/health", "/docs", "/openapi.json", "/redoc", "/ws")

    if any(path.startswith(p) for p in _PUBLIC):
        return await call_next(request)

    # Dev/staging bypass — disabled in production
    if _APP_ENV != "production" and request.headers.get("X-Dev-Mode") == "true":
        return await call_next(request)

    # Validate Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            from .auth.jwt_handler import verify_token
            verify_token(token)
            return await call_next(request)
        except Exception:
            pass

    # Production: reject; development: allow through (dev frontend has no auth yet)
    if _APP_ENV == "production":
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return await call_next(request)


# ── Auth ──────────────────────────────────────────────────────────────────────
app.include_router(auth_router)

# ── Phase 1: ETL Pipelines ─────────────────────────────────────────────────────
app.include_router(pipelines_router,                        tags=["Phase 1 — Pipelines"])
app.include_router(connectors_router, prefix="/api",        tags=["Phase 1 — Connectors"])

# ── Phase 2: Self-Healing Agents ──────────────────────────────────────────────
app.include_router(healing_router, tags=["Phase 2 — Self-Healing"])

# ── Phase 3: Transformation + Optimization ───────────────────────────────────
app.include_router(transformation_router, tags=["Phase 3 — Transformation"])

# ── Phase 4: Analytics + Insights ────────────────────────────────────────────
app.include_router(analytics_router, tags=["Phase 4 — Analytics"])

# ── Platform Settings ─────────────────────────────────────────────────────────
app.include_router(settings_router, tags=["Settings"])

# ── Data Quality ──────────────────────────────────────────────────────────────
app.include_router(quality_router, tags=["Data Quality"])

# ── Notifications ─────────────────────────────────────────────────────────────
app.include_router(notifications_router, tags=["Notifications"])

# ── Lineage ───────────────────────────────────────────────────────────────────
app.include_router(lineage_router, tags=["Lineage"])

# ── Scheduled Reports ─────────────────────────────────────────────────────────
app.include_router(reports_router, tags=["Reports"])

# ── ML Metrics ────────────────────────────────────────────────────────────────
app.include_router(ml_metrics_router, tags=["ML — Anomaly Detection"])

# ── Learning Agent — Outcome Tracking + MTTR ──────────────────────────────────
app.include_router(learning_stats_router, tags=["Learning"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Deep health check — pings PostgreSQL and reports component status."""
    result: dict = {
        "status": "ok",
        "service": "OrchestrAI",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {},
    }
    overall_ok = True

    # PostgreSQL
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "orchestrai"),
            user=os.getenv("POSTGRES_USER", "admin"),
            password=os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
            connect_timeout=3,
        )
        conn.cursor().execute("SELECT 1")
        conn.close()
        result["components"]["postgres"] = "ok"
    except Exception as e:
        result["components"]["postgres"] = f"error: {e}"
        overall_ok = False

    # ChromaDB
    try:
        import httpx
        r = httpx.get(
            f"http://{os.getenv('CHROMA_HOST','localhost')}:{os.getenv('CHROMA_PORT','8001')}/api/v1/heartbeat",
            timeout=2,
        )
        result["components"]["chromadb"] = "ok" if r.status_code == 200 else f"http {r.status_code}"
    except Exception as e:
        result["components"]["chromadb"] = f"unreachable: {e}"
        # ChromaDB is optional — don't fail overall

    if not overall_ok:
        result["status"] = "degraded"
        return JSONResponse(content=result, status_code=503)
    return result


# ── WebSocket connection manager ───────────────────────────────────────────────
# ws_manager is the shared singleton imported from core.ws_manager above.
# Re-exported here for backwards compatibility with any code that imports from main.


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send welcome + current server time
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {"message": "OrchestrAI live feed connected", "ts": datetime.utcnow().isoformat()},
        }))
        while True:
            # Keep connection alive with ping every 30s
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping", "data": {"ts": datetime.utcnow().isoformat()}}))
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        ws_manager.disconnect(websocket)


# ── Request ID + structured logging middleware ─────────────────────────────────

_log = logging.getLogger("orchestrai.http")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 1)
    _log.info(
        '{"request_id":"%s","method":"%s","path":"%s","status":%d,"duration_ms":%.1f}',
        request_id, request.method, request.url.path, response.status_code, duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
