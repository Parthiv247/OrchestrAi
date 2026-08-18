#!/bin/bash
# OrchestrAI — Resume Demo (Step 3 onwards, skipping Docker/Python setup)
# Docker + Python already running from start_demo.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'
info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
step()    { echo -e "\n${BOLD}${GREEN}══ $1 ══${NC}"; }

echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   OrchestrAI — Resuming Demo Setup        ║"
echo "  ║   Picking up from Step 3 (Seed)           ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${NC}"

PYTHON="$DIR/venv/bin/python"
[ ! -f "$PYTHON" ] && PYTHON="$(which python3)"

# ── Step 3: Seed demo data ────────────────────────────────────────
step "Step 3: Seeding real e-commerce demo data"

$PYTHON "$DIR/scripts/seed_ecommerce_demo.py"
if [ $? -ne 0 ]; then
  echo -e "${RED}[FAIL]${NC}  Seed script failed — check output above"; exit 1
fi

# ── Step 4: Start FastAPI backend ────────────────────────────────
step "Step 4: Starting FastAPI backend (port 8000)"

lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 1

export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=orchestrai
export POSTGRES_USER=admin
export POSTGRES_PASSWORD=orchestrai_secret
export CHROMA_HOST=localhost
export CHROMA_PORT=8001
export APP_ENV=development
export INTERNAL_API_URL=http://localhost:8000

[ -f "$DIR/.env" ] && export $(grep -v '^#' "$DIR/.env" | grep -v '^$' | xargs) 2>/dev/null || true

nohup "$DIR/venv/bin/uvicorn" backend.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  > /tmp/orchestrai_backend.log 2>&1 &

BACKEND_PID=$!
echo $BACKEND_PID > /tmp/orchestrai_backend.pid
info "Backend starting (PID: $BACKEND_PID)..."

for i in $(seq 1 25); do
  if curl -sf http://localhost:8000/health &>/dev/null; then
    success "Backend is up → http://localhost:8000"
    break
  fi
  [ $i -eq 25 ] && warn "Backend slow — check /tmp/orchestrai_backend.log"
  sleep 2
done

# ── Step 5: Register connectors + pipeline ────────────────────────
step "Step 5: Registering connectors and creating demo pipeline"

$PYTHON "$DIR/scripts/setup_demo_pipeline.py"

# ── Step 6: Start Next.js frontend ───────────────────────────────
step "Step 6: Starting Next.js frontend (port 3001)"

lsof -ti:3001 | xargs kill -9 2>/dev/null || true
sleep 1

cd "$DIR/frontend"
[ -d .next ] && rm -rf .next/cache 2>/dev/null || true

nohup npm run dev > /tmp/orchestrai_frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/orchestrai_frontend.pid
info "Frontend starting (PID: $FRONTEND_PID)..."

for i in $(seq 1 30); do
  if curl -sf http://localhost:3001 &>/dev/null; then
    success "Frontend is up → http://localhost:3001"
    break
  fi
  sleep 3
done

echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║  🚀 OrchestrAI is LIVE — DEMO READY!                ║"
echo "  ║                                                      ║"
echo "  ║  Frontend:  http://localhost:3001                    ║"
echo "  ║  Backend:   http://localhost:8000                    ║"
echo "  ║  API Docs:  http://localhost:8000/docs               ║"
echo "  ║                                                      ║"
echo "  ║  Stop:  ./stop_demo.sh                               ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

open http://localhost:3001
