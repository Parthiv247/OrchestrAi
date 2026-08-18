#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# OrchestrAI — One-click startup
# Double-click this file to start the full stack.
#
# What this does:
#   1. Kills any old processes on ports 3000, 3001, 8000
#   2. Starts postgres + chromadb + backend via docker-compose
#      (backend runs alembic migrations + seeds data on first boot)
#   3. Waits for backend health at http://localhost:8000
#   4. Opens http://localhost:3000 in Chrome
#   5. Starts Next.js dev server on port 3000
# ─────────────────────────────────────────────────────────────────────────────
cd /Users/parthivpatel/OrchetraAI

echo "======================================"
echo "   OrchestrAI — Starting Up"
echo "======================================"

# ── Kill stale port occupants ───────────────────────────────────────────────
echo ""
echo "Clearing ports 3000, 3001, 8000..."
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:3001 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 1

# ── 1. Start infrastructure + backend via Docker ────────────────────────────
echo ""
echo "[1/3] Starting postgres, chromadb, backend via Docker..."
echo "      (First run builds Docker images — may take 5-10 min)"
docker-compose up -d postgres chromadb backend

# Wait for postgres
echo "  Waiting for PostgreSQL..."
for i in $(seq 1 30); do
  docker exec orchestrai-postgres pg_isready -U admin -d orchestrai -q 2>/dev/null && break
  sleep 2; printf "."
done
echo " PostgreSQL ready."

# Wait for backend
echo "  Waiting for backend (runs migrations + seeds data)..."
for i in $(seq 1 45); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo " Backend ready!"
    break
  fi
  sleep 3; printf "."
done

# ── 2. Show health + backend status ─────────────────────────────────────────
echo ""
echo "Backend health:"
curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool 2>/dev/null \
  || echo "(backend not responding yet — check: docker logs orchestrai-backend --tail 30)"

# ── 3. Start Next.js frontend on port 3000 ──────────────────────────────────
echo ""
echo "[2/3] Starting Next.js frontend on port 3000..."
cd /Users/parthivpatel/OrchetraAI/frontend

echo ""
echo "[3/3] Opening browser..."
sleep 2
open "http://localhost:3000" 2>/dev/null || true

echo ""
echo "======================================"
echo "  OrchestrAI is running!"
echo "  Frontend: http://localhost:3000"
echo "  API docs: http://localhost:8000/docs"
echo "  Backend logs: docker logs orchestrai-backend -f"
echo "======================================"

npm run dev
