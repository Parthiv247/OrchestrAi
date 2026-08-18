#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
#  OrchestrAI — One-Command Demo Startup
#  Usage: chmod +x start_demo.sh && ./start_demo.sh
# ═══════════════════════════════════════════════════════════════════════

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $1"; exit 1; }
step()    { echo -e "\n${BOLD}${GREEN}══ $1 ══${NC}"; }

echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   OrchestrAI — Demo Startup Script        ║"
echo "  ║   Autonomous Self-Healing Data Pipelines  ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# ── Step 1: Docker ────────────────────────────────────────────────────
step "Step 1: Starting Docker services (postgres + chromadb)"

if ! docker info &>/dev/null; then
  warn "Docker not running — opening Docker Desktop..."
  open -a Docker
  info "Waiting 20s for Docker to start..."
  sleep 20
fi

# Start only postgres + chromadb (skip airflow — heavy, not needed for demo)
docker compose up -d postgres chromadb 2>&1 | grep -E "Starting|Creating|Pulling|done|error" || true

info "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
  if docker exec orchestrai-postgres pg_isready -U admin -d orchestrai &>/dev/null 2>&1; then
    success "PostgreSQL is ready"
    break
  fi
  [ $i -eq 30 ] && fail "PostgreSQL never became ready after 30 attempts"
  sleep 2
done

info "Waiting for ChromaDB to be ready..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:8001/api/v1/heartbeat &>/dev/null; then
    success "ChromaDB is ready"
    break
  fi
  sleep 2
done

# ── Step 2: Python environment ────────────────────────────────────────
step "Step 2: Checking Python environment"

PYTHON="$DIR/venv/bin/python"
if [ ! -f "$PYTHON" ]; then
  warn "venv not found — trying system python3"
  PYTHON="$(which python3)"
fi

PIP="$DIR/venv/bin/pip"
if [ ! -f "$PIP" ]; then PIP="$(which pip3)"; fi

# Install any missing deps silently
$PIP install psycopg2-binary requests faker 2>/dev/null | grep -E "Installing|already" || true
success "Python deps OK"

# ── Step 3: Seed demo data ────────────────────────────────────────────
step "Step 3: Seeding real e-commerce demo data"

$PYTHON "$DIR/scripts/seed_ecommerce_demo.py"

# ── Step 4: Start FastAPI backend ────────────────────────────────────
step "Step 4: Starting FastAPI backend (port 8000)"

# Kill any stale backend
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 1

cd "$DIR"
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=orchestrai
export POSTGRES_USER=admin
export POSTGRES_PASSWORD=orchestrai_secret
export CHROMA_HOST=localhost
export CHROMA_PORT=8001
export APP_ENV=development
export INTERNAL_API_URL=http://localhost:8000

# Load .env if present
[ -f .env ] && export $(grep -v '^#' .env | grep -v '^$' | xargs)

nohup "$DIR/venv/bin/uvicorn" backend.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  > /tmp/orchestrai_backend.log 2>&1 &

BACKEND_PID=$!
echo $BACKEND_PID > /tmp/orchestrai_backend.pid

info "Backend starting (PID: $BACKEND_PID)..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:8000/health &>/dev/null; then
    success "Backend is up → http://localhost:8000"
    break
  fi
  [ $i -eq 20 ] && { warn "Backend slow — check /tmp/orchestrai_backend.log"; }
  sleep 2
done

# ── Step 5: Register connectors + pipeline ────────────────────────────
step "Step 5: Registering connectors and creating demo pipeline"

$PYTHON "$DIR/scripts/setup_demo_pipeline.py"

# ── Step 6: Start Next.js frontend ───────────────────────────────────
step "Step 6: Starting Next.js frontend (port 3001)"

lsof -ti:3001 | xargs kill -9 2>/dev/null || true
sleep 1

cd "$DIR/frontend"
# Clear stale Next.js cache
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

# ── Done ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║  🚀 OrchestrAI is LIVE — DEMO READY!                ║"
echo "  ║                                                      ║"
echo "  ║  Frontend:  http://localhost:3001                    ║"
echo "  ║  Backend:   http://localhost:8000                    ║"
echo "  ║  API Docs:  http://localhost:8000/docs               ║"
echo "  ║                                                      ║"
echo "  ║  Logs:  tail -f /tmp/orchestrai_backend.log          ║"
echo "  ║         tail -f /tmp/orchestrai_frontend.log         ║"
echo "  ║                                                      ║"
echo "  ║  Stop:  ./stop_demo.sh                               ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

open http://localhost:3001
