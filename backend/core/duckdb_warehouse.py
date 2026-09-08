"""
DuckDB local warehouse — serves as the destination for pipeline ETL.
Acts as a lightweight Snowflake replacement for dev/demo environments.
The warehouse file lives at: <project_root>/data/warehouse.duckdb
"""
import duckdb
import os
import logging
from pathlib import Path
from typing import List, Dict
import pandas as pd

logger = logging.getLogger(__name__)

WAREHOUSE_PATH = Path(__file__).parent.parent.parent / "data" / "warehouse.duckdb"


class DuckDBWarehouse:

    def __init__(self):
        WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None

    def connect(self, read_only: bool = False):
        self._read_only = read_only
        try:
            self._conn = duckdb.connect(str(WAREHOUSE_PATH), read_only=read_only)
        except Exception as e:
            # WAL file may be owned by another process/user in Docker mounts.
            # Retry read-only so stats endpoints still work.
            if not read_only:
                logger.warning("DuckDB connect read-write failed (%s); retrying read-only", e)
                try:
                    self._conn = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
                    self._read_only = True
                except Exception as e2:
                    raise RuntimeError(f"Cannot open DuckDB warehouse: {e2}") from e2
            else:
                raise
        if not self._read_only:
            self._init_schema()
        return self

    def _init_schema(self):
        """Create destination tables if they don't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_pipeline_data (
                id VARCHAR PRIMARY KEY,
                pipeline_name VARCHAR NOT NULL,
                source_type VARCHAR NOT NULL,
                records_count INTEGER,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                batch_id VARCHAR,
                workspace_id VARCHAR DEFAULT 'default'
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_metrics_warehouse (
                id VARCHAR PRIMARY KEY,
                pipeline_name VARCHAR NOT NULL,
                run_date DATE,
                records_loaded INTEGER,
                records_failed INTEGER,
                duration_seconds FLOAT,
                status VARCHAR,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS nyc_taxi_trips (
                trip_id VARCHAR PRIMARY KEY,
                pickup_datetime TIMESTAMP,
                dropoff_datetime TIMESTAMP,
                passenger_count INTEGER,
                trip_distance FLOAT,
                fare_amount FLOAT,
                tip_amount FLOAT,
                total_amount FLOAT,
                payment_type VARCHAR,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS ecommerce_orders (
                order_id VARCHAR PRIMARY KEY,
                customer_id VARCHAR,
                product_name VARCHAR,
                category VARCHAR,
                quantity INTEGER,
                unit_price FLOAT,
                total_amount FLOAT,
                order_date DATE,
                status VARCHAR,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Watermark table — tracks the last successfully loaded value per pipeline/table.
        # Used by incremental ETL to fetch only new/updated rows (replaces full-table reload).
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS etl_watermarks (
                pipeline_name VARCHAR NOT NULL,
                table_name    VARCHAR NOT NULL,
                watermark_col VARCHAR NOT NULL,
                watermark_val VARCHAR NOT NULL,
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (pipeline_name, table_name)
            )
        """)

    def insert_batch(self, table: str, records: List[Dict]) -> int:
        """
        Full-replace insert — used for metrics/logging tables where dedup by id is fine.
        For business data tables (nyc_taxi_trips, ecommerce_orders), prefer upsert_batch.
        """
        if not records:
            return 0
        df = pd.DataFrame(records)
        try:
            self._conn.execute(f"INSERT OR REPLACE INTO {table} SELECT * FROM df")
            return len(records)
        except Exception as e:
            logger.error("DuckDB insert_batch failed: %s", e)
            return 0

    def upsert_batch(self, table: str, records: List[Dict], unique_key: str) -> int:
        """
        Incremental upsert — only inserts new rows or updates existing ones by unique_key.

        Strategy:
          1. Load incoming records into a temp view.
          2. DELETE matching keys from target (DuckDB doesn't support MERGE directly).
          3. INSERT the new/updated rows.

        This ensures the warehouse table is always current without blowing away the whole table
        on every pipeline run. Only truly new or changed rows are written.

        Returns: number of rows upserted.
        """
        if not records:
            return 0
        df = pd.DataFrame(records)
        if unique_key not in df.columns:
            logger.warning("upsert_batch: unique_key '%s' not in records — falling back to insert_batch", unique_key)
            return self.insert_batch(table, records)
        try:
            # Register temp view for the incoming batch
            self._conn.register("_upsert_staging", df)
            # Remove any rows in target that match an incoming key (UPDATE = DELETE + INSERT)
            self._conn.execute(f"""
                DELETE FROM {table}
                WHERE {unique_key} IN (SELECT {unique_key} FROM _upsert_staging)
            """)
            # Insert all incoming rows (new + updated)
            self._conn.execute(f"INSERT INTO {table} SELECT * FROM _upsert_staging")
            self._conn.unregister("_upsert_staging")
            logger.debug("upsert_batch: %d rows → %s", len(records), table)
            return len(records)
        except Exception as e:
            logger.error("DuckDB upsert_batch failed for %s: %s", table, e)
            return 0

    # ── Watermark helpers ──────────────────────────────────────────────────────

    def get_watermark(self, pipeline_name: str, table_name: str) -> str | None:
        """
        Return the last watermark value for this pipeline+table pair.
        The watermark is typically an ISO datetime string (MAX(updated_at) of last run).
        Returns None when no previous run has been recorded.
        """
        try:
            row = self._conn.execute("""
                SELECT watermark_val FROM etl_watermarks
                WHERE pipeline_name = ? AND table_name = ?
            """, [pipeline_name, table_name]).fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.warning("get_watermark failed: %s", e)
            return None

    def set_watermark(self, pipeline_name: str, table_name: str,
                      watermark_col: str, watermark_val: str) -> None:
        """
        Persist the current high-water mark so the next run fetches only newer rows.
        watermark_val should be the MAX(watermark_col) of the records just written.
        """
        try:
            self._conn.execute("""
                INSERT INTO etl_watermarks (pipeline_name, table_name, watermark_col, watermark_val, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (pipeline_name, table_name)
                DO UPDATE SET watermark_col = excluded.watermark_col,
                              watermark_val = excluded.watermark_val,
                              updated_at    = CURRENT_TIMESTAMP
            """, [pipeline_name, table_name, watermark_col, watermark_val])
        except Exception as e:
            logger.warning("set_watermark failed: %s", e)

    def get_table_count(self, table: str) -> int:
        try:
            result = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def get_recent_loads(self, pipeline_name: str, limit: int = 10) -> List[Dict]:
        """Get recent load history for a pipeline."""
        try:
            rows = self._conn.execute("""
                SELECT run_date, records_loaded, records_failed, duration_seconds, status
                FROM pipeline_metrics_warehouse
                WHERE pipeline_name = ?
                ORDER BY loaded_at DESC
                LIMIT ?
            """, [pipeline_name, limit]).fetchall()
            return [{"run_date": str(r[0]), "records_loaded": r[1], "records_failed": r[2],
                     "duration_seconds": r[3], "status": r[4]} for r in rows]
        except Exception:
            return []

    def close(self):
        if self._conn:
            self._conn.close()
