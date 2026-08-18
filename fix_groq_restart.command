#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

echo -e "${BOLD}${CYAN}=== Restarting backend with correct env vars ===${NC}"

# Kill existing backend
echo "Killing existing backend on port 8000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
pkill -f "uvicorn backend.main" 2>/dev/null || true
sleep 2

# Load .env
set -a
source "$DIR/.env"
set +a

# Also set explicit vars
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=orchestrai
export POSTGRES_USER=admin
export POSTGRES_PASSWORD=orchestrai_secret
export CHROMA_HOST=localhost
export CHROMA_PORT=8001
export APP_ENV=development
export INTERNAL_API_URL=http://localhost:8000

echo "GROQ_API_KEY set: ${GROQ_API_KEY:0:10}..."
echo "GROQ_MODEL: $GROQ_MODEL"

echo "Starting backend..."
nohup "$DIR/venv/bin/uvicorn" backend.main:app \
  --host 0.0.0.0 --port 8000 \
  > /tmp/orchestrai_backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/orchestrai_backend.pid
echo "Backend PID: $BACKEND_PID"

echo "Waiting for backend..."
for i in $(seq 1 20); do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8000/health 2>/dev/null || echo "000")
  if [ "$HTTP" != "000" ]; then
    echo -e "${GREEN}✅ Backend up (HTTP $HTTP)${NC}"
    break
  fi
  echo "  Waiting ($i/20)..."
  sleep 2
done

echo ""
echo "Testing Groq via analyst query..."
RESULT=$(curl -s -X POST http://localhost:8000/api/analyst/query \
  -H 'Content-Type: application/json' \
  -H 'X-Dev-Mode: true' \
  -d '{"question": "How many orders are in the database?"}' 2>/dev/null)

echo "Result: $RESULT" | head -c 500
echo ""
echo -e "${GREEN}✅ Done! Backend restarted with Groq key.${NC}"
