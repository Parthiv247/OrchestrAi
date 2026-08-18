#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

echo -e "${BOLD}${CYAN}=== Starting Postgres + ChromaDB ===${NC}"

# Start containers
docker-compose up -d postgres chromadb

echo "Waiting for postgres to be ready..."
for i in $(seq 1 20); do
  if docker exec orchestrai-postgres pg_isready -U admin -d orchestrai >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Postgres ready${NC}"
    break
  fi
  echo "  Waiting ($i/20)..."
  sleep 2
done

echo "Waiting for chromadb..."
for i in $(seq 1 10); do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://localhost:8001/api/v1/heartbeat 2>/dev/null || echo "000")
  if [ "$HTTP" = "200" ]; then
    echo -e "${GREEN}✅ ChromaDB ready${NC}"
    break
  fi
  echo "  Waiting ($i/10)..."
  sleep 2
done

echo ""
echo "Testing backend health..."
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/health

echo ""
echo -e "${GREEN}✅ Done!${NC}"
