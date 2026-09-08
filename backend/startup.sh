#!/usr/bin/env bash
# OrchestrAI backend startup script
# Runs: alembic migrations → dbt run → uvicorn
set -e

echo "=== OrchestrAI Backend Starting ==="

# ── Parse DATABASE_URL if set (Railway/Supabase production) ───────────────────
if [ -n "$DATABASE_URL" ]; then
  echo "[0/4] DATABASE_URL detected — parsing for POSTGRES_* vars..."
  # Strip driver prefix (postgresql+asyncpg:// → postgresql://)
  _RAW_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+[^:]*://|postgresql://|')
  export POSTGRES_USER=$(echo "$_RAW_URL" | sed 's|postgresql://||' | cut -d: -f1)
  export POSTGRES_PASSWORD=$(echo "$_RAW_URL" | sed 's|.*://[^:]*:||' | cut -d@ -f1)
  export POSTGRES_HOST=$(echo "$_RAW_URL" | sed 's|.*@||' | cut -d: -f1)
  export POSTGRES_PORT=$(echo "$_RAW_URL" | sed 's|.*@[^:]*:||' | cut -d/ -f1)
  export POSTGRES_DB=$(echo "$_RAW_URL" | sed 's|.*/||' | cut -d? -f1)
  echo "  Host=$POSTGRES_HOST Port=$POSTGRES_PORT DB=$POSTGRES_DB User=$POSTGRES_USER"
fi

# ── 1. Wait for PostgreSQL ─────────────────────────────────────────────────────
echo "[1/4] Waiting for PostgreSQL..."
RETRIES=30
until python3 -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        host=os.getenv('POSTGRES_HOST','localhost'),
        port=int(os.getenv('POSTGRES_PORT',5432)),
        dbname=os.getenv('POSTGRES_DB','orchestrai'),
        user=os.getenv('POSTGRES_USER','admin'),
        password=os.getenv('POSTGRES_PASSWORD','orchestrai_secret'),
        connect_timeout=5
    ).close()
    sys.exit(0)
except Exception as e:
    print(f'  DB not ready: {e}', flush=True)
    sys.exit(1)
" 2>&1; do
  RETRIES=$((RETRIES - 1))
  if [ $RETRIES -le 0 ]; then
    echo "ERROR: PostgreSQL not ready after 30 attempts — starting anyway"
    break
  fi
  echo "  Retrying in 3s... ($RETRIES left)"
  sleep 3
done
echo "  PostgreSQL ready."

# ── 2. Alembic migrations ──────────────────────────────────────────────────────
echo "[2/4] Running Alembic migrations..."
cd /app/backend
alembic upgrade head || echo "WARNING: Alembic migration failed — continuing"
cd /app

# ── 3. dbt run ────────────────────────────────────────────────────────────────
echo "[3/4] Running dbt transformations..."
if [ -d "/app/dbt_project" ]; then
  # Only run dbt if the raw source tables exist (they're loaded by ETL pipelines).
  # On a fresh DB they won't exist yet — skip gracefully rather than printing 17 errors.
  _RAW_TABLES_EXIST=$(python3 -c "
import psycopg2, os
try:
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST','localhost'),
        port=int(os.getenv('POSTGRES_PORT',5432)),
        dbname=os.getenv('POSTGRES_DB','postgres'),
        user=os.getenv('POSTGRES_USER','admin'),
        password=os.getenv('POSTGRES_PASSWORD',''),
        connect_timeout=5
    )
    cur = conn.cursor()
    cur.execute(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='raw' AND table_name IN ('ecommerce_orders','nyc_taxi_trips')\")
    count = cur.fetchone()[0]
    conn.close()
    print('yes' if count >= 1 else 'no')
except Exception as e:
    print('no')
" 2>/dev/null)
  if [ "$_RAW_TABLES_EXIST" = "yes" ]; then
    echo "  Raw source tables found — running dbt..."
    cd /app/dbt_project
    dbt run --profiles-dir . --project-dir . --target dev 2>&1 | tail -20 || echo "WARNING: dbt run failed — mart tables may be missing"
    cd /app
  else
    echo "  Raw source tables not yet loaded — skipping dbt (will run automatically after first ETL pipeline executes)"
  fi
else
  echo "  dbt_project not found — skipping"
fi

# ── 4. Start FastAPI ───────────────────────────────────────────────────────────
echo "[4/4] Starting FastAPI..."
exec uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WORKERS:-2}"
