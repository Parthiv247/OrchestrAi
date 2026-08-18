.PHONY: up down restart seed logs status build

up:
	docker-compose up -d
	@echo "⏳ Waiting 30s for services..."
	@sleep 30
	@$(MAKE) status

build:
	docker-compose build

down:
	docker-compose down

restart:
	docker-compose restart

seed:
	python scripts/seed_data.py

logs:
	docker-compose logs -f --tail=50

status:
	@echo "═══ OrchestrAI Service Status ═══"
	@curl -s http://localhost:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Backend:', d.get('status','?'))" 2>/dev/null || echo "❌ Backend: not ready"
	@curl -s http://localhost:8080/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Airflow:', d.get('metadatabase',{}).get('status','healthy'))" 2>/dev/null || echo "❌ Airflow: not ready"
	@curl -s http://localhost:8001/api/v1/heartbeat > /dev/null 2>&1 && echo "✅ ChromaDB: running" || echo "❌ ChromaDB: not ready"
	@curl -s http://localhost:3001 > /dev/null 2>&1 && echo "✅ Frontend: running" || echo "❌ Frontend: not ready"
	@echo "════════════════════════════════"
	@echo "  Frontend:  http://localhost:3001"
	@echo "  Backend:   http://localhost:8000"
	@echo "  Airflow:   http://localhost:8080  (admin/admin)"
	@echo "════════════════════════════════"
