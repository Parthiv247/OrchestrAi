#!/bin/bash
# OrchestrAI — Stop all demo services
echo "Stopping OrchestrAI demo services..."

# Kill backend + frontend
[ -f /tmp/orchestrai_backend.pid ] && kill "$(cat /tmp/orchestrai_backend.pid)" 2>/dev/null && rm /tmp/orchestrai_backend.pid
[ -f /tmp/orchestrai_frontend.pid ] && kill "$(cat /tmp/orchestrai_frontend.pid)" 2>/dev/null && rm /tmp/orchestrai_frontend.pid

lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3001 | xargs kill -9 2>/dev/null || true

# Stop Docker services
docker compose stop postgres chromadb 2>/dev/null || true

echo "All services stopped."
