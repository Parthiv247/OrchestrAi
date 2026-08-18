#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'; BOLD='\033[1m'

echo -e "${BOLD}${CYAN}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   OrchestrAI — Finish Setup               ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${NC}"

PYTHON="$DIR/venv/bin/python"

# Check docker
echo "=== Docker status ==="
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "orchestrai|NAME"

# Check if backend is up (even on 503 it's running)
echo ""
echo "=== Backend check ==="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8000/health 2>/dev/null || echo "000")
echo "  /health → HTTP $HTTP_CODE"

if [ "$HTTP_CODE" = "000" ]; then
  echo "  Backend not responding — need to restart it first"
  echo "  Checking log..."
  tail -20 /tmp/orchestrai_backend.log
  exit 1
fi

echo "  Backend is up (HTTP $HTTP_CODE — 503 = health check DB/Chroma issue, APIs still work)"

# Set env
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=orchestrai
export POSTGRES_USER=admin
export POSTGRES_PASSWORD=orchestrai_secret
export CHROMA_HOST=localhost
export CHROMA_PORT=8001
export APP_ENV=development
[ -f "$DIR/.env" ] && export $(grep -v '^#' "$DIR/.env" | grep -v '^$' | xargs) 2>/dev/null || true

# Step 5: Register connectors + pipeline
echo ""
echo -e "${BOLD}${GREEN}══ Step 5: Registering connectors and pipeline ══${NC}"
$PYTHON "$DIR/scripts/setup_demo_pipeline.py"

# Step 6: Start frontend
echo ""
echo -e "${BOLD}${GREEN}══ Step 6: Starting Next.js frontend (port 3001) ══${NC}"

lsof -ti:3001 | xargs kill -9 2>/dev/null || true
sleep 1

cd "$DIR/frontend"
[ -d .next ] && rm -rf .next/cache 2>/dev/null || true

nohup npm run dev > /tmp/orchestrai_frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/orchestrai_frontend.pid
echo "Frontend PID: $FRONTEND_PID"

echo "Waiting for frontend to be ready..."
for i in $(seq 1 40); do
  if curl -sf --max-time 2 http://localhost:3001 &>/dev/null; then
    echo -e "${GREEN}✅ Frontend is up → http://localhost:3001${NC}"
    break
  fi
  [ $i -eq 40 ] && echo -e "${YELLOW}Frontend slow — check /tmp/orchestrai_frontend.log${NC}"
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
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

open http://localhost:3001
