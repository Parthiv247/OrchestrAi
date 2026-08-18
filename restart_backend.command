#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

echo -e "${BOLD}${CYAN}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   OrchestrAI — Backend Restart            ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# Kill existing backend + connector setup
echo "Killing any existing processes on port 8000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
pkill -f "uvicorn backend.main" 2>/dev/null || true
pkill -f "setup_demo_pipeline" 2>/dev/null || true
sleep 2

# Set env vars
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

echo "Starting FastAPI backend..."
nohup "$DIR/venv/bin/uvicorn" backend.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  > /tmp/orchestrai_backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/orchestrai_backend.pid
echo "Backend PID: $BACKEND_PID"

echo "Waiting for backend to be ready..."
for i in $(seq 1 30); do
  if curl -sf --max-time 2 http://localhost:8000/health &>/dev/null; then
    echo -e "${GREEN}✅ Backend is up → http://localhost:8000${NC}"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "Backend didn't respond — showing last 30 lines of log:"
    tail -30 /tmp/orchestrai_backend.log
    exit 1
  fi
  echo "  Waiting ($i/30)..."
  sleep 2
done

echo ""
echo "Running connector + pipeline setup..."
"$DIR/venv/bin/python" "$DIR/scripts/setup_demo_pipeline.py"

echo ""
echo "Starting Next.js frontend..."
lsof -ti:3001 | xargs kill -9 2>/dev/null || true
sleep 1

cd "$DIR/frontend"
[ -d .next ] && rm -rf .next/cache 2>/dev/null || true

nohup npm run dev > /tmp/orchestrai_frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/orchestrai_frontend.pid
echo "Frontend PID: $FRONTEND_PID"

echo "Waiting for frontend..."
for i in $(seq 1 30); do
  if curl -sf --max-time 2 http://localhost:3001 &>/dev/null; then
    echo -e "${GREEN}✅ Frontend is up → http://localhost:3001${NC}"
    break
  fi
  sleep 3
done

echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║  🚀 OrchestrAI LIVE — DEMO READY!       ║"
echo "  ║  Frontend:  http://localhost:3001        ║"
echo "  ║  Backend:   http://localhost:8000        ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${NC}"

open http://localhost:3001
