#!/usr/bin/env bash
# OrchestrAI — One-command local startup + verification
# Run: bash run_local.sh
set -e
cd "$(dirname "$0")"

echo "=========================================="
echo "  OrchestrAI — Local Startup & Verify"
echo "=========================================="

# ── 1. Start infrastructure ────────────────────────────────────────────────────
echo ""
echo "[1/5] Starting Docker services..."
docker-compose up -d postgres chromadb
echo "  Waiting for postgres to be healthy..."
until docker exec orchestrai-postgres pg_isready -U admin -d orchestrai -q 2>/dev/null; do
  sleep 2; printf "."
done
echo " Ready."

# ── 2. Start backend ───────────────────────────────────────────────────────────
echo ""
echo "[2/5] Starting backend (alembic + dbt + uvicorn)..."
docker-compose up -d backend
echo "  Waiting for backend health check..."
RETRIES=30
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  RETRIES=$((RETRIES-1))
  [ $RETRIES -le 0 ] && echo "  ERROR: backend not healthy after 60s" && docker logs orchestrai-backend --tail 40 && exit 1
  sleep 2; printf "."
done
echo " Healthy."

# ── 3. Check health endpoint ───────────────────────────────────────────────────
echo ""
echo "[3/5] Health check result:"
curl -s http://localhost:8000/health | python3 -m json.tool

# ── 4. Verify Groq key ─────────────────────────────────────────────────────────
echo ""
echo "[4/5] Checking Groq API key..."
KEY=$(grep GROQ_API_KEY .env | cut -d= -f2)
GROQ_STATUS=$(python3 -c "
import urllib.request, json, ssl
ctx = ssl.create_default_context()
data = json.dumps({'model':'llama-3.3-70b-versatile','messages':[{'role':'user','content':'Reply: OK'}],'max_tokens':3}).encode()
req = urllib.request.Request('https://api.groq.com/openai/v1/chat/completions', data=data,
    headers={'Authorization': 'Bearer $KEY', 'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        d = json.loads(r.read())
        print('OK:', d['choices'][0]['message']['content'])
except Exception as e:
    print('FAIL:', e)
" 2>&1)
echo "  Groq: $GROQ_STATUS"

# ── 5. Test AI Analyst ─────────────────────────────────────────────────────────
echo ""
echo "[5/5] Testing AI Analyst (NL-to-SQL)..."
RESULT=$(curl -s -X POST http://localhost:8000/api/analyst/query \
  -H "Content-Type: application/json" \
  -H "X-Dev-Mode: true" \
  -d '{"question":"Show top 5 products by revenue","session_id":"test-001"}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
if 'data' in d and d['data']:
    print(f'SUCCESS — {len(d[\"data\"])} rows returned | SQL: {d.get(\"sql\",\"\")[:80]}')
elif 'error' in d:
    print('ERROR:', d['error'])
else:
    print('RESPONSE:', str(d)[:200])
" 2>&1)
echo "  Analyst: $RESULT"

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  Done. Open http://localhost:3000"
echo "  (Start frontend: cd frontend && npm run dev)"
echo "=========================================="
