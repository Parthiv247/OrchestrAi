#!/bin/bash
# OrchestrAI — One-click demo startup
# Starts: Docker (postgres + chromadb) → FastAPI backend → Next.js frontend
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'; BOLD='\033[1m'

echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   OrchestrAI — Full Demo Startup             ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Kill any existing backend / frontend ────────────────────────────────────
echo -e "${YELLOW}► Stopping old processes...${NC}"
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3001 | xargs kill -9 2>/dev/null || true
pkill -f "uvicorn backend.main" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
sleep 1

# ── 2. Start Docker containers ─────────────────────────────────────────────────
echo -e "${YELLOW}► Starting Docker containers (postgres + chromadb)...${NC}"
docker compose up -d postgres chromadb

# ── 3. Wait for postgres ───────────────────────────────────────────────────────
echo "Waiting for postgres..."
for i in $(seq 1 30); do
  if docker exec orchestrai-postgres pg_isready -U admin -d orchestrai >/dev/null 2>&1; then
    echo -e "${GREEN}  ✅ Postgres ready${NC}"
    break
  fi
  if [ $i -eq 30 ]; then
    echo -e "${YELLOW}  ⚠️  Postgres slow to start — continuing anyway${NC}"
  fi
  sleep 2
done

# ── 4. Set env vars ────────────────────────────────────────────────────────────
[ -f "$DIR/backend/.env" ] && export $(grep -v '^#' "$DIR/backend/.env" | grep -v '^$' | xargs) 2>/dev/null || true
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=orchestrai
export POSTGRES_USER=admin
export POSTGRES_PASSWORD=orchestrai_secret
export APP_ENV=development
export INTERNAL_API_URL=http://localhost:8000

# ── 5. Start FastAPI backend ───────────────────────────────────────────────────
echo -e "${YELLOW}► Starting FastAPI backend...${NC}"
nohup "$DIR/venv/bin/uvicorn" backend.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  > /tmp/orchestrai_backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/orchestrai_backend.pid

# Wait for backend — accept both 200 (ok) and 503 (degraded but alive)
for i in $(seq 1 30); do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8000/health 2>/dev/null || echo "000")
  if [ "$HTTP" = "200" ] || [ "$HTTP" = "503" ]; then
    echo -e "${GREEN}  ✅ Backend up (HTTP $HTTP) → http://localhost:8000${NC}"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "Backend not responding — check /tmp/orchestrai_backend.log"
    tail -20 /tmp/orchestrai_backend.log
  fi
  sleep 2
done

# Full health status
echo ""
HEALTH=$(curl -s --max-time 3 http://localhost:8000/health 2>/dev/null || echo "{}")
echo "Health: $HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"

# ── 6. Start Next.js frontend ──────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}► Starting Next.js frontend...${NC}"
cd "$DIR/frontend"
[ -d .next/cache ] && rm -rf .next/cache 2>/dev/null || true

nohup npm run dev -- --port 3001 > /tmp/orchestrai_frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/orchestrai_frontend.pid

for i in $(seq 1 30); do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:3001 2>/dev/null || echo "000")
  if [ "$HTTP" = "200" ] || [ "$HTTP" = "307" ]; then
    echo -e "${GREEN}  ✅ Frontend up → http://localhost:3001${NC}"
    break
  fi
  sleep 3
done

# ── 7. Done ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║  🚀 OrchestrAI LIVE — DEMO READY!           ║"
echo "  ║  Frontend:  http://localhost:3001            ║"
echo "  ║  Backend:   http://localhost:8000            ║"
echo "  ║  API Docs:  http://localhost:8000/docs       ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

open http://localhost:3001
