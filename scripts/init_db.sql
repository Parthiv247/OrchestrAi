-- ─────────────────────────────────────────────────────────────────────────────
-- OrchestrAI — Postgres bootstrap (runs once on a fresh postgres_data volume)
--
-- The application's SQLAlchemy models own the table schema: backend/main.py
-- runs Base.metadata.create_all() on startup, which builds every table exactly
-- as the ORM defines it (text/varchar ids, savings_percent, all columns).
--
-- Pre-creating tables here with hand-written DDL caused column drift in earlier
-- iterations (e.g. savings_pct vs savings_percent, UUID vs text id), so this
-- script ONLY installs extensions and seeds the cumulative cost metric. Tables
-- appear as soon as the backend container boots and passes its healthcheck.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- Seed the cost-savings metric once the app has created system_metrics.
-- Wrapped in a DO block so a fresh DB (table not yet created) doesn't error;
-- the backend's create_all() + seed_data.py will (re)establish it as needed.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'system_metrics'
  ) THEN
    INSERT INTO system_metrics (id, metric_name, metric_value, updated_at)
    VALUES (gen_random_uuid()::text, 'total_cost_saved', 0, NOW())
    ON CONFLICT (metric_name) DO NOTHING;
  END IF;
END $$;
