# OrchestrAI — Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines

> MTech Dissertation Project | Multi-Agent Systems | Self-Healing Infrastructure | LangGraph + Groq LLM

[![Python](https://img.shields.io/badge/Python-3.10-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.4.8-purple)](https://langchain-ai.github.io/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## Overview

OrchestrAI is an autonomous multi-agent platform that monitors data pipelines, detects anomalies using ML, generates LLM-powered self-healing fixes, routes them through human-in-the-loop approval, and learns from outcomes to continuously improve — all in a production-grade B2B SaaS interface.

## Key Results

| Metric | Value |
|---|---|
| MTTR vs Manual Baseline | **94.4% reduction** (2,378s → 134s) |
| MTTR vs Rule-Based Systems | **77.7% reduction** (601s → 134s) |
| Statistical Significance | p < 0.001, Cohen's d = 3.76 |
| Anomaly Classifier F1 | **0.980** (6-class RandomForest) |
| IsolationForest ROC-AUC | **0.896** |
| NL-to-SQL Accuracy | **80%** (30-question benchmark) |
| Learning Curve | Success rate: 78% → 92% over 20 scenarios |

## Architecture

[See docs/architecture.svg for the full multi-agent architecture diagram]

### Multi-Agent Pipeline

```
Data Sources → Connector Layer → Pipeline Engine
                                      │
                              ┌───────┴────────┐
                              │  Monitoring    │  IsolationForest + RandomForest
                              │  Agent         │  Anomaly Detection
                              └───────┬────────┘
                                      │ anomaly detected
                              ┌───────┴────────┐
                              │  Diagnosis     │  Groq LLM (llama-3.3-70b)
                              │  Agent         │  Root cause analysis
                              └───────┬────────┘
                                      │
                              ┌───────┴────────┐
                              │  Fix Writer    │  LLM-generated healing code
                              │  Agent         │
                              └───────┬────────┘
                                      │
                              ┌───────┴────────┐
                              │  Human-in-Loop │  Approval Panel
                              │  Approval      │  Approve / Reject / Auto-heal
                              └───────┬────────┘
                                      │
                              ┌───────┴────────┐
                              │  Deployment    │  Sandbox execution
                              │  Agent         │
                              └───────┬────────┘
                                      │
                              ┌───────┴────────┐
                              │  Learning      │  ChromaDB RAG + Outcome Tracking
                              │  Agent         │  MTTR trending, strategy selection
                              └────────────────┘
```

## Tech Stack

### Backend
- **FastAPI** 0.111 — async REST API with 15 route modules
- **LangGraph** 0.4.8 — multi-agent state machine orchestration
- **Groq LLM** (llama-3.3-70b-versatile) — diagnosis + fix generation
- **scikit-learn** — IsolationForest (unsupervised) + RandomForest (multi-class)
- **ChromaDB** — RAG vector store for fix pattern learning
- **PostgreSQL** — primary DB (pipeline runs, incidents, healing outcomes)
- **DuckDB** — local warehouse (4,120+ records: NYC taxi + e-commerce)
- **Snowflake** — cloud data warehouse destination
- **Alembic** — database migrations

### Frontend
- **Next.js 14** (App Router) — TypeScript, server components
- **TanStack Query v5** — data fetching + caching
- **Framer Motion** — page transitions + micro-animations
- **Recharts** — time-series charts, bar charts, area charts
- **shadcn/ui** — component primitives

## Features

### Core Pipeline Platform
- 4 source connectors: PostgreSQL, REST API, CSV/S3, Google Sheets
- 3 destination connectors: Snowflake, PostgreSQL, DuckDB
- Real ETL execution with actual record counts
- Pipeline scheduling + run history

### Self-Healing System
- **5 anomaly types detected**: ZERO_LOAD, ROW_COUNT_DROP, NULL_SPIKE, PIPELINE_DELAY, CONSECUTIVE_FAILURES
- **ML detection**: IsolationForest (unsupervised) + RandomForest classifier (98% F1)
- **LLM healing**: Groq generates context-aware Python fix scripts
- **Human-in-loop**: Approve/reject with full fix code preview
- **Auto-healing**: Confidence-threshold-based automatic deployment
- **Outcome tracking**: Every decision recorded with MTTR

### Learning & Intelligence
- ChromaDB RAG stores successful fix patterns
- `healing_outcomes` table tracks strategy success rates per anomaly type
- MTTR trend shows 69% improvement over 30 days (seeded demo data)
- Strategy selection weighted by historical success rates

### Analytics Layer
- **AI Analyst**: Natural language → SQL (80% accuracy on 30-question benchmark)
- **Data Lineage**: Visual DAG of pipeline dependencies
- **Cost Optimizer**: Query cost analysis + recommendations
- **dbt Assistant**: LLM-powered dbt model generation

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Groq API key (get free at console.groq.com)

### 1. Clone and configure
```bash
git clone <repo>
cd OrchetraAI
cp backend/.env.example backend/.env
# Edit .env: add GROQ_API_KEY
```

### 2. Start all services
```bash
docker compose up -d
```

This starts: PostgreSQL, OrchestrAI backend (FastAPI), Next.js frontend.

### 3. Run database migrations
```bash
docker exec orchestrai-backend alembic upgrade heads
```

### 4. Seed demo data
```bash
docker exec orchestrai-backend python3 core/seed_outcomes.py
```

### 5. Train ML models (optional — pre-trained pkl files included)
```bash
docker exec orchestrai-backend python3 /opt/orchestrai/ml/train_models.py
```

### 6. Open the app
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

## API Reference

| Endpoint | Description |
|---|---|
| `GET /api/pipelines` | List all pipelines |
| `POST /api/pipelines/{id}/trigger` | Trigger pipeline run |
| `GET /api/incidents` | List healing incidents |
| `POST /api/incidents/{id}/approve` | Approve healing fix |
| `GET /api/ml/metrics` | ML model evaluation metrics |
| `POST /api/ml/train` | Retrain anomaly detection models |
| `GET /api/learning/stats` | Learning agent statistics |
| `GET /api/learning/mttr-trend` | 30-day MTTR trend data |
| `GET /api/warehouse/stats` | DuckDB warehouse record counts |
| `POST /api/analytics/query` | Natural language → SQL |

## Experimental Evaluation

See `experiments/` directory:
- `ablation_study.py` — 3-way comparison across 20 failure scenarios
- `ablation_analysis.ipynb` — Jupyter notebook with statistical analysis + charts
- `nlsql_accuracy_extended.py` — 30-question NL-to-SQL benchmark
- `results/ablation_results.json` — Full statistical results
- `results/fig1_mttr_comparison.png` — MTTR bar chart
- `results/fig2_learning_curve.png` — Learning progression chart

### Ablation Study Results

| Config | Mean MTTR | vs OrchestrAI | p-value |
|---|---|---|---|
| A: Manual Baseline | 2,378s (39.6 min) | 17.7× slower | < 0.001 |
| B: Rule-Based Only | 601s (10.0 min) | 4.5× slower | 0.0027 |
| **C: Full OrchestrAI** | **134s (2.2 min)** | **baseline** | — |

## Project Structure

```
OrchetraAI/
├── backend/
│   ├── agents/
│   │   ├── healing/          # MonitoringAgent, DiagnosisAgent, FixWriterAgent
│   │   ├── learning/         # LearningAgent (ChromaDB RAG)
│   │   ├── analytics/        # QueryAgent, InsightsAgent
│   │   ├── optimization/     # CostOptimizerAgent
│   │   └── transformation/   # DbtModelingAgent
│   ├── api/routes/           # 15 FastAPI route modules
│   ├── connectors/           # Source + destination connectors
│   ├── core/                 # DuckDB warehouse, ETL runner, outcome tracker
│   ├── ml/                   # Pre-trained pkl models + training script
│   ├── migrations/           # Alembic migrations (5 versions)
│   └── tests/                # 65+ pytest tests
├── frontend/
│   └── src/app/              # 13 Next.js pages
├── experiments/              # Ablation study + NL-SQL benchmark
├── docs/                     # Architecture diagram
└── data/                     # DuckDB warehouse + seed scripts
```

## Testing

```bash
cd backend
pytest tests/ -v
# Expected: 65+ tests passing
```

## License

MIT
