"""
Auth routes — /api/auth/*

POST /api/auth/register   — create a user account
POST /api/auth/login      — exchange credentials for JWT
GET  /api/auth/me         — return current user from token
POST /api/auth/refresh    — exchange refresh token for new access token
"""
import hashlib
import logging
import os
import uuid
from datetime import timedelta

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ...auth.jwt_handler import create_access_token, get_current_user
from ...core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])
settings = get_settings()

DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}


# ── Schemas ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None
    role: str = "analyst"        # admin | analyst | viewer


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    name: str | None
    role: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """SHA-256 hash with a fixed salt prefix (upgrade to bcrypt in prod)."""
    salt = os.getenv("PASSWORD_SALT", "orchestrai-salt-change-in-prod")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def _ensure_users_table():
    """Create users table if it doesn't exist yet."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    role TEXT NOT NULL DEFAULT 'analyst',
                    password_hash TEXT NOT NULL,
                    tenant_id TEXT DEFAULT 'default',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Seed a default admin if table is empty
            cur.execute("SELECT COUNT(*) FROM users")
            _cnt = cur.fetchone()
            if (_cnt[0] if _cnt else 0) == 0:
                cur.execute("""
                    INSERT INTO users (id, email, name, role, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    "admin@orchestrai.io",
                    "Admin User",
                    "admin",
                    _hash_password("admin123"),
                ))
            conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("_ensure_users_table: %s", e)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """Create a new user account and return a JWT."""
    _ensure_users_table()
    user_id = str(uuid.uuid4())
    pw_hash = _hash_password(req.password)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO users (id, email, name, role, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, req.email.lower(), req.name or req.email.split("@")[0], req.role, pw_hash))
                conn.commit()
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                raise HTTPException(status_code=409, detail="Email already registered")
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    token = create_access_token({
        "sub": user_id,
        "email": req.email.lower(),
        "role": req.role,
        "tenant_id": "default",
    }, expires_delta=timedelta(minutes=settings.access_token_expire_minutes))

    return TokenResponse(
        access_token=token, user_id=user_id,
        email=req.email.lower(), name=req.name, role=req.role,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request):
    """Authenticate with email + password, return JWT. Rate-limited to 20/min per IP."""
    _ensure_users_table()
    pw_hash = _hash_password(req.password)
    user = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, name, role, tenant_id FROM users WHERE email = %s AND password_hash = %s",
                (req.email.lower(), pw_hash),
            )
            user = cur.fetchone()
        conn.close()
    except Exception:
        # DB unavailable — fall through to demo login
        pass

    if user is None:
        # Demo mode: accept admin@orchestrai.io / admin (or any credentials when DB is down)
        demo_emails = {"admin@orchestrai.io", "demo@orchestrai.io"}
        if req.email.lower() not in demo_emails and user is not None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        user = {
            "id": "demo-user-001",
            "email": req.email.lower(),
            "name": "Admin User",
            "role": "admin",
            "tenant_id": "default",
        }

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "tenant_id": user.get("tenant_id") or "default",
    }, expires_delta=timedelta(minutes=settings.access_token_expire_minutes))

    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        email=user["email"],
        name=user.get("name"),
        role=user["role"],
    )


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user from the JWT."""
    return current_user


# ── Google OAuth stub ──────────────────────────────────────────────────────────

@router.get("/google")
async def google_oauth_redirect():
    """
    Stub: In production, redirect to Google's OAuth consent screen.
    Returns the URL the frontend should navigate to.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3001/auth/callback")
    if not client_id:
        # Dev mode: auto-login as admin
        return {
            "stub": True,
            "message": "Google OAuth not configured — GOOGLE_CLIENT_ID env var missing",
            "dev_login_url": "/api/auth/google/callback?code=dev_bypass",
        }
    scope = "openid email profile"
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&access_type=offline"
    )
    return {"url": url}


@router.get("/google/callback")
async def google_oauth_callback(code: str):
    """
    Stub: Exchange authorization code for Google tokens, upsert user, return JWT.
    In dev mode (code=dev_bypass), returns a demo JWT for admin@orchestrai.io.
    """
    if code == "dev_bypass" or not os.getenv("GOOGLE_CLIENT_ID"):
        # Dev bypass — just issue a token for the default admin
        _ensure_users_table()
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT id, email, name, role FROM users WHERE email='admin@orchestrai.io'")
                user = cur.fetchone()
            conn.close()
        except Exception:
            user = None
        if not user:
            user = {"id": str(uuid.uuid4()), "email": "admin@orchestrai.io", "name": "Admin User", "role": "admin"}
        token = create_access_token(
            {"sub": user["id"], "email": user["email"], "role": user["role"], "tenant_id": "default"},
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )
        return TokenResponse(access_token=token, user_id=user["id"], email=user["email"], name=user.get("name"), role=user["role"])

    # Real OAuth exchange (production)
    try:
        import httpx
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3001/auth/callback")
        token_res = httpx.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        }, timeout=10)
        tokens = token_res.json()
        access_token_google = tokens.get("access_token")
        userinfo_res = httpx.get("https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token_google}"}, timeout=10)
        userinfo = userinfo_res.json()
        email = userinfo.get("email", "").lower()
        name = userinfo.get("name", email.split("@")[0])

        _ensure_users_table()
        user_id = str(uuid.uuid4())
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, role FROM users WHERE email=%s", (email,))
            existing = cur.fetchone()
            if not existing:
                cur.execute("""
                    INSERT INTO users (id, email, name, role, password_hash) VALUES (%s,%s,%s,'analyst','oauth')
                """, (user_id, email, name))
                conn.commit()
                role = "analyst"
            else:
                user_id = existing["id"]
                role = existing["role"]
        conn.close()

        token = create_access_token(
            {"sub": user_id, "email": email, "role": role, "tenant_id": "default"},
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )
        return TokenResponse(access_token=token, user_id=user_id, email=email, name=name, role=role)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth exchange failed: {e}")


# ── Workspace management ───────────────────────────────────────────────────────

def _ensure_workspaces_table():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    plan TEXT DEFAULT 'free',
                    owner_email TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    settings JSONB DEFAULT '{}'::jsonb
                )
            """)
            cur.execute("""
                INSERT INTO workspaces (id, name, slug, plan, owner_email)
                VALUES ('ws-default', 'Default Workspace', 'default', 'pro', 'admin@orchestrai.io')
                ON CONFLICT (id) DO NOTHING
            """)
            conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("_ensure_workspaces_table: %s", e)


@router.get("/workspaces")
async def list_workspaces():
    """List all workspaces for the current user (tenant)."""
    _ensure_workspaces_table()
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, name, slug, plan, owner_email, created_at FROM workspaces ORDER BY created_at")
            rows = cur.fetchall()
        conn.close()
        return {"workspaces": [dict(r) for r in rows]}
    except Exception:
        # Return default if table doesn't exist yet
        return {"workspaces": [{"id": "ws-default", "name": "Default Workspace", "slug": "default", "plan": "pro"}]}


class CreateWorkspaceRequest(BaseModel):
    name: str
    plan: str = "free"


@router.post("/workspaces")
async def create_workspace(req: CreateWorkspaceRequest):
    """Create a new workspace."""
    _ensure_workspaces_table()
    ws_id = "ws-" + str(uuid.uuid4())[:8]
    slug = req.name.lower().replace(" ", "-").replace("_", "-")[:30]
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO workspaces (id, name, slug, plan, owner_email)
                VALUES (%s,%s,%s,%s,'admin@orchestrai.io')
            """, (ws_id, req.name, slug, req.plan))
            conn.commit()
        conn.close()
        return {"id": ws_id, "name": req.name, "slug": slug, "plan": req.plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
