#!/usr/bin/env bash
# OrchestrAI backend startup script
# Order: parse env → wait for DB → create tables (sync) → alembic → dbt → uvicorn
set -e

echo "=== OrchestrAI Backend Starting ==="

# ── Parse DATABASE_URL if set (Railway/Supabase production) ───────────────────
if [ -n "$DATABASE_URL" ]; then
  echo "[0/5] DATABASE_URL detected — parsing for POSTGRES_* vars..."
  _RAW_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+[^:]*://|postgresql://|')
  export POSTGRES_USER=$(echo "$_RAW_URL" | sed 's|postgresql://||' | cut -d: -f1)
  export POSTGRES_PASSWORD=$(echo "$_RAW_URL" | sed 's|.*://[^:]*:||' | cut -d@ -f1)
  export POSTGRES_HOST=$(echo "$_RAW_URL" | sed 's|.*@||' | cut -d: -f1)
  export POSTGRES_PORT=$(echo "$_RAW_URL" | sed 's|.*@[^:]*:||' | cut -d/ -f1)
  export POSTGRES_DB=$(echo "$_RAW_URL" | sed 's|.*/||' | cut -d? -f1)
  echo "  Host=$POSTGRES_HOST Port=$POSTGRES_PORT DB=$POSTGRES_DB User=$POSTGRES_USER"
fi

# ── 1. Wait for PostgreSQL ─────────────────────────────────────────────────────
echo "[1/5] Waiting for PostgreSQL..."
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
    echo "ERROR: PostgreSQL not ready after 30 attempts — aborting"
    exit 1
  fi
  echo "  Retrying in 3s... ($RETRIES left)"
  sleep 3
done
echo "  PostgreSQL ready."

# ── 2. Create all SQLAlchemy tables (sync, psycopg2 — always works) ───────────
# This runs BEFORE Alembic so tables exist when migration ALTER TABLE statements run.
echo "[2/5] Creating / verifying tables..."
cd /app
python3 backend/create_tables.py && echo "  Tables OK." || echo "  WARNING: create_tables failed — continuing"

# ── 3. Alembic migrations (adds columns / new tables on top of base schema) ───
echo "[3/5] Running Alembic migrations..."
cd /app/backend
alembic upgrade head && echo "  Migrations OK." || echo "  WARNING: Alembic migration failed — continuing"
cd /app

# ── 4. dbt run ────────────────────────────────────────────────────────────────
echo "[4/5] Running dbt transformations..."
if [ -d "/app/dbt_project" ]; then
  # Only run dbt when BOTH source tables exist with data (populated by ETL pipelines).
  # On a fresh deployment they won't exist — skip cleanly.
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
    table_count = cur.fetchone()[0]
    rows_ok = False
    if table_count >= 2:
        cur.execute(\"SELECT COUNT(*) FROM raw.ecommerce_orders\")
        rows_ok = cur.fetchone()[0] > 0
    conn.close()
    print('yes' if (table_count >= 2 and rows_ok) else 'no')
except Exception:
    print('no')
" 2>/dev/null)
  if [ "$_RAW_TABLES_EXIST" = "yes" ]; then
    echo "  Raw source tables found — running dbt..."
    cd /app/dbt_project
    dbt run --profiles-dir . --project-dir . --target dev 2>&1 | tail -20 \
      || echo "  WARNING: dbt run failed — mart tables may be missing"
    cd /app
  else
    echo "  Raw source tables not yet loaded — skipping dbt."
    echo "  (dbt will succeed automatically after the first ETL pipeline run loads data)"
  fi
else
  echo "  dbt_project not found — skipping"
fi

# ── 5. Start FastAPI ───────────────────────────────────────────────────────────
echo "[5/5] Starting FastAPI..."
exec uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WORKERS:-1}"
