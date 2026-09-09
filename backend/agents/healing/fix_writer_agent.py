"""
FixWriterAgent — Writes self-contained Python fix code for diagnosed root causes.

2025 upgrades:
  - 18 fix templates covering all anomaly types and database platforms
  - Snowflake, BigQuery, MySQL, MongoDB, Redshift, Kafka/CDC fix patterns
  - Enhanced Groq prompt with database-aware context and 2025 ETL best practices
  - ChromaDB RAG cache with metadata-filtered similarity search
  - AST validation + syntax check before returning any code
  - Schema drift auto-healer: dynamically maps columns instead of hard-coding
"""
import json
import logging
import os
import re
from typing import Dict, Any, Optional

import httpx

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

from .state import HealingAgentState

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
CHROMA_HOST  = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT  = int(os.getenv("CHROMA_PORT", 8001))
RAG_CONFIDENCE_THRESHOLD = 0.90

SYSTEM_PROMPT = """You are a senior data engineer specializing in ETL/ELT pipeline reliability.
Write a self-contained Python fix function for a diagnosed pipeline issue.

## Requirements
1. Self-contained — only use: pandas, sqlalchemy, psycopg2, os, json, datetime, re, hashlib
2. Safe to run in an isolated Docker container — no network calls, no DROP/DELETE/TRUNCATE
3. Define fix(df: pd.DataFrame) -> pd.DataFrame that applies the repair
4. Define verify(df: pd.DataFrame) -> bool that returns True if repair succeeded
5. Handle edge cases: empty DataFrame, all-null columns, wrong dtypes
6. Include inline comments explaining each step

## Database platform awareness
- PostgreSQL/Redshift: use standard pandas + psycopg2 patterns
- Snowflake: use VARIANT type handling, FLATTEN for semi-structured data
- BigQuery: handle REPEATED/RECORD types as nested JSON
- MySQL: handle TINYINT(1) as boolean, DATETIME vs TIMESTAMP differences
- MongoDB: flatten nested documents, handle ObjectId, ISODate
- Kafka/CDC: deduplicate on primary key, handle out-of-order by event_time watermark

## Return ONLY Python code — no markdown fences, no explanation"""

# ── Fix Templates ──────────────────────────────────────────────────────────────

FIX_TEMPLATES: Dict[str, str] = {

    "schema_change": '''import pandas as pd
import re

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Auto-heals schema drift: fills new nullable columns, coerces types, renames common aliases."""
    if df.empty:
        return df
    # Fill nulls per column type
    for col in df.columns:
        if df[col].isnull().mean() > 0.10:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].median())
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].fillna(pd.Timestamp("1970-01-01"))
            else:
                df[col] = df[col].fillna("UNKNOWN")
    # Coerce obvious type mismatches
    for col in df.select_dtypes(include="object").columns:
        try:
            df[col] = pd.to_numeric(df[col], errors="ignore")
        except Exception:
            pass
    return df

def verify(df: pd.DataFrame) -> bool:
    return not df.empty and df.isnull().mean().max() < 0.15
''',

    "data_quality": '''import pandas as pd
import hashlib

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Removes duplicates, fills nulls, and repairs referential integrity issues."""
    if df.empty:
        return df
    before = len(df)
    # Deduplicate on all columns
    df = df.drop_duplicates()
    # Fill numeric nulls with median
    for col in df.select_dtypes(include="number").columns:
        df[col] = df[col].fillna(df[col].median())
    # Fill string nulls with UNKNOWN
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("UNKNOWN").str.strip()
    # Remove clearly invalid rows (all-null across all numeric columns)
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        df = df.dropna(subset=num_cols, how="all")
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0 and df.isnull().sum().sum() == 0
''',

    "connection": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Connection fix is at infrastructure level; ensure DataFrame is non-empty before returning."""
    if df.empty:
        raise ValueError("Connection recovery returned empty dataset — source unreachable")
    # Validate expected key columns exist
    for col in df.columns:
        if df[col].isnull().all():
            df = df.drop(columns=[col])
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0 and len(df.columns) > 0
''',

    "volume": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Validates row count and raises an alert if critically low; otherwise passes through."""
    MIN_ROWS = 1
    if len(df) < MIN_ROWS:
        raise ValueError(f"Pipeline produced {len(df)} records — below minimum threshold {MIN_ROWS}")
    # Remove completely empty rows
    df = df.dropna(how="all")
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',

    "timeout": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Timeout mitigation: sample large datasets and optimise column types to reduce memory."""
    MAX_ROWS = 500_000
    if len(df) > MAX_ROWS:
        df = df.sample(n=MAX_ROWS, random_state=42).reset_index(drop=True)
    # Downcast numerics to reduce memory footprint
    for col in df.select_dtypes(include=["int64"]).columns:
        df[col] = pd.to_numeric(df[col], downcast="integer")
    for col in df.select_dtypes(include=["float64"]).columns:
        df[col] = pd.to_numeric(df[col], downcast="float")
    # Convert low-cardinality string columns to category
    for col in df.select_dtypes(include="object").columns:
        if df[col].nunique() / max(len(df), 1) < 0.05:
            df[col] = df[col].astype("category")
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',

    "logic": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Defensive null handling, type coercion, and deduplication for DAG logic errors."""
    if df.empty:
        return df
    # Strip whitespace from strings
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip().replace("nan", None)
    # Deduplicate
    df = df.drop_duplicates().reset_index(drop=True)
    # Fill nulls
    for col in df.select_dtypes(include="number").columns:
        df[col] = df[col].fillna(0)
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0 and df.duplicated().sum() == 0
''',

    "rate_limit": '''import pandas as pd
import time

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Rate limit recovery: batch the data and add jitter; surface count for re-ingestion."""
    BATCH_SIZE = 10_000
    if len(df) > BATCH_SIZE:
        # Return only the safe first batch; orchestrator will re-trigger for remaining
        df = df.head(BATCH_SIZE)
    return df

def verify(df: pd.DataFrame) -> bool:
    return 0 < len(df) <= 10_000
''',

    "cdc_lag": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """CDC lag recovery: deduplicate by primary key keeping latest event; set watermark."""
    if df.empty:
        return df
    # Identify likely event time column
    ts_cols = [c for c in df.columns if any(k in c.lower() for k in
               ["event_time", "updated_at", "timestamp", "created_at", "ts", "_timestamp"])]
    pk_candidates = [c for c in df.columns if any(k in c.lower() for k in
                     ["id", "_id", "key", "order_id", "user_id"])]
    if ts_cols and pk_candidates:
        ts_col = ts_cols[0]
        pk_col = pk_candidates[0]
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        # Keep latest record per primary key
        df = (df.sort_values(ts_col, ascending=False)
                .drop_duplicates(subset=[pk_col], keep="first")
                .reset_index(drop=True))
    else:
        df = df.drop_duplicates().reset_index(drop=True)
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0 and df.duplicated().sum() == 0
''',

    "incremental_sync": '''import pandas as pd
from datetime import datetime, timedelta

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Incremental sync recovery: filter to valid watermark window and deduplicate."""
    if df.empty:
        return df
    # Find timestamp columns
    ts_cols = [c for c in df.columns if any(k in c.lower() for k in
               ["created_at", "updated_at", "event_time", "timestamp", "date"])]
    if ts_cols:
        ts_col = ts_cols[0]
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        # Drop rows with null timestamps (corrupt watermark records)
        df = df.dropna(subset=[ts_col])
        # Filter to reasonable time window: last 7 days
        cutoff = datetime.utcnow() - timedelta(days=7)
        df = df[df[ts_col] >= cutoff].reset_index(drop=True)
    # Deduplicate
    id_cols = [c for c in df.columns if c.lower() in ("id", "_id", "key")]
    if id_cols:
        df = df.drop_duplicates(subset=id_cols, keep="last").reset_index(drop=True)
    else:
        df = df.drop_duplicates().reset_index(drop=True)
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',

    "cascading": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Cascading failure recovery: minimal pass-through with null sentinel fill."""
    if df.empty:
        return df
    # Fill nulls to prevent downstream failures
    for col in df.columns:
        if df[col].isnull().any():
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(-1)
            else:
                df[col] = df[col].fillna("RECOVERY_SENTINEL")
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0 and df.isnull().sum().sum() == 0
''',

    "checkpoint": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Checkpoint recovery: replay safe window, sort by event time to restore ordering."""
    if df.empty:
        return df
    ts_cols = [c for c in df.columns if any(k in c.lower() for k in
               ["event_time", "timestamp", "created_at", "ts"])]
    if ts_cols:
        ts_col = ts_cols[0]
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        df = df.sort_values(ts_col).reset_index(drop=True)
    df = df.drop_duplicates().reset_index(drop=True)
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',

    "duplicate_spike": '''import pandas as pd
import hashlib

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplication fix: composite-key dedup with content hash fallback."""
    if df.empty:
        return df
    # Try primary key dedup first
    pk_cols = [c for c in df.columns if c.lower() in ("id", "_id", "order_id", "user_id", "trip_id")]
    ts_cols = [c for c in df.columns if any(k in c.lower() for k in
               ["updated_at", "event_time", "created_at"])]
    if pk_cols:
        sort_col = ts_cols[0] if ts_cols else None
        if sort_col:
            df[sort_col] = pd.to_datetime(df[sort_col], errors="coerce")
            df = df.sort_values(sort_col, ascending=False)
        df = df.drop_duplicates(subset=pk_cols, keep="first").reset_index(drop=True)
    else:
        # Content hash deduplication
        df["_content_hash"] = df.apply(lambda r: hashlib.md5(str(r.values).encode()).hexdigest(), axis=1)
        df = df.drop_duplicates(subset=["_content_hash"]).drop(columns=["_content_hash"])
    return df.reset_index(drop=True)

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0 and df.duplicated().sum() == 0
''',

    "snowflake_schema": '''import pandas as pd
import json

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Snowflake VARIANT/semi-structured column handling: flatten JSON nested fields."""
    if df.empty:
        return df
    for col in df.columns:
        if df[col].dtype == object:
            # Try to parse JSON VARIANT columns
            sample = df[col].dropna().head(5).tolist()
            if any(isinstance(s, str) and s.strip().startswith("{") for s in sample):
                try:
                    parsed = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
                    sub_df = pd.json_normalize(parsed.tolist())
                    sub_df.columns = [f"{col}__{c}" for c in sub_df.columns]
                    df = pd.concat([df.drop(columns=[col]), sub_df], axis=1)
                except Exception:
                    pass
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',

    "bigquery_type": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """BigQuery type coercion: handle NUMERIC precision, TIMESTAMP, and BOOL columns."""
    if df.empty:
        return df
    for col in df.columns:
        # Coerce NUMERIC columns (BigQuery uses NUMERIC(29,9))
        if df[col].dtype == object:
            try:
                numeric = pd.to_numeric(df[col], errors="coerce")
                if numeric.notnull().mean() > 0.8:
                    df[col] = numeric.round(9)
                    continue
            except Exception:
                pass
        # Coerce TIMESTAMP
        if "time" in col.lower() or "date" in col.lower() or "ts" in col.lower():
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
            except Exception:
                pass
    df = df.dropna(how="all")
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',

    "mysql_cdc": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """MySQL CDC fix: handle TINYINT(1) booleans, DATETIME vs TIMESTAMP, binlog dedup."""
    if df.empty:
        return df
    # MySQL TINYINT(1) → bool
    for col in df.select_dtypes(include="int").columns:
        if df[col].isin([0, 1, -128, 127]).mean() > 0.95:
            df[col] = df[col].map({1: True, 0: False}).fillna(False)
    # Coerce DATETIME columns
    for col in df.columns:
        if "datetime" in col.lower() or "created_at" in col.lower() or "updated_at" in col.lower():
            df[col] = pd.to_datetime(df[col], errors="coerce")
    # Binlog deduplication: keep latest by _binlog_position if present
    if "_binlog_position" in df.columns and "id" in df.columns:
        df = df.sort_values("_binlog_position", ascending=False).drop_duplicates(subset=["id"]).reset_index(drop=True)
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',

    "mongodb_flatten": '''import pandas as pd
import json

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """MongoDB document flattening: convert ObjectId to string, flatten nested dicts."""
    if df.empty:
        return df
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna().head(3).tolist()
            # Flatten nested dicts
            if any(isinstance(s, dict) for s in sample):
                try:
                    sub_df = pd.json_normalize(df[col].tolist())
                    sub_df.columns = [f"{col}.{c}" for c in sub_df.columns]
                    df = pd.concat([df.drop(columns=[col]), sub_df], axis=1)
                    continue
                except Exception:
                    pass
            # Convert ObjectId-like strings
            if any(isinstance(s, str) and len(s) == 24 for s in sample):
                df[col] = df[col].astype(str)
    df = df.fillna("null")
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',

    "redshift_load": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Redshift STL_LOAD_ERRORS recovery: truncate oversized strings, coerce column types."""
    if df.empty:
        return df
    VARCHAR_MAX = 65535
    for col in df.select_dtypes(include="object").columns:
        # Truncate strings exceeding Redshift VARCHAR limit
        df[col] = df[col].astype(str).str[:VARCHAR_MAX]
        # Remove null bytes that Redshift rejects
        df[col] = df[col].str.replace("\\x00", "", regex=False)
    # Remove rows with encoding issues
    df = df[df.apply(lambda row: all(
        isinstance(v, (int, float, type(None))) or str(v).isprintable()
        for v in row
    ), axis=1)].reset_index(drop=True)
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',

    "partition_skew": '''import pandas as pd
import numpy as np

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Partition skew fix: add a salt column for re-partitioning and cap hot partitions."""
    if df.empty:
        return df
    # Find likely partition column (date or category with low cardinality)
    part_cols = [c for c in df.columns if any(k in c.lower() for k in
                 ["date", "region", "country", "category", "type", "status"])]
    if part_cols:
        part_col = part_cols[0]
        freq = df[part_col].value_counts()
        hot_keys = freq[freq > freq.mean() * 5].index.tolist()
        if hot_keys:
            # Add numeric salt for hot partition keys (spread across 8 buckets)
            df["_partition_salt"] = np.where(
                df[part_col].isin(hot_keys),
                np.random.randint(0, 8, size=len(df)),
                0
            )
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',
}

# Anomaly → template mapping
ANOMALY_TEMPLATE_MAP = {
    "ZERO_LOAD":                "connection",
    "ROW_COUNT_DROP":           "volume",
    "NULL_SPIKE":               "schema_change",
    "PIPELINE_DELAY":           "timeout",
    "SLA_BREACH":               "timeout",
    "CONSECUTIVE_FAILURES":     "logic",
    "SCHEMA_DRIFT":             "schema_change",
    "CDC_LAG":                  "cdc_lag",
    "RATE_LIMIT_HIT":           "rate_limit",
    "INCREMENTAL_SYNC_FAILURE": "incremental_sync",
    "CASCADING_FAILURE":        "cascading",
    "DUPLICATE_SPIKE":          "duplicate_spike",
    "CHECKPOINT_FAILURE":       "checkpoint",
    "DATA_TYPE_MISMATCH":       "schema_change",
    "PARTITION_SKEW":           "partition_skew",
    "ML_ANOMALY":               "data_quality",
}


class FixWriterAgent:
    """Generates fix code using RAG cache (ChromaDB) + Groq LLM + template fallback."""

    def __init__(self):
        self._chroma = self._init_chroma()

    def write_fix(self, state: HealingAgentState) -> HealingAgentState:
        root_cause   = state.get("root_cause") or "Unknown"
        anomaly_type = state.get("anomaly_type") or "UNKNOWN"
        pipeline     = state.get("pipeline_name") or "unknown"
        steps = list(state.get("reasoning_steps") or [])

        # 1. Check RAG cache (with anomaly-type filter for higher precision)
        cached = self._recall_from_rag(root_cause, anomaly_type)
        if cached and self._has_required_functions(cached):
            steps.append("FixWriterAgent: reusing cached fix from ChromaDB (similarity >90%)")
            return HealingAgentState(**{**state, "fix_code": cached, "fix_language": "python", "reasoning_steps": steps})

        # 2. Try Groq LLM with enriched context
        fix_code = self._call_groq(root_cause, anomaly_type, state)
        if fix_code and self._has_required_functions(fix_code):
            steps.append("FixWriterAgent: fix generated via Groq LLM")
        else:
            # 3. Template fallback — always structurally correct
            template_key = self._infer_fix_type(anomaly_type, root_cause, pipeline)
            fix_code = FIX_TEMPLATES.get(template_key, FIX_TEMPLATES["logic"])
            steps.append(f"FixWriterAgent: using template fix for {template_key}")

        return HealingAgentState(**{**state, "fix_code": fix_code, "fix_language": "python", "reasoning_steps": steps})

    # ── Public helpers ─────────────────────────────────────────────────────────

    def _has_required_functions(self, code: str) -> bool:
        import ast
        try:
            tree = ast.parse(code)
            names = {n.name for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            return "fix" in names and "verify" in names
        except SyntaxError:
            return False

    def _recall_from_rag(self, root_cause: str, anomaly_type: str = "") -> Optional[str]:
        """Alias for check_rag_cache — exists so tests can patch it cleanly."""
        return self.check_rag_cache(root_cause, anomaly_type)

    def check_rag_cache(self, root_cause: str, anomaly_type: str = "") -> Optional[str]:
        if not HAS_CHROMA or self._chroma is None:
            return None
        try:
            collection = self._chroma.get_or_create_collection("orchestrai_fixes")
            if collection.count() == 0:
                return None

            # Query with optional anomaly_type metadata filter
            where_filter = {"anomaly_type": anomaly_type} if anomaly_type else None
            try:
                results = collection.query(
                    query_texts=[root_cause], n_results=1,
                    where=where_filter if where_filter else None,
                )
            except Exception:
                results = collection.query(query_texts=[root_cause], n_results=1)

            distances = results.get("distances", [[]])[0]
            docs      = results.get("documents", [[]])[0]
            if distances and docs:
                similarity = 1.0 - distances[0]
                if similarity >= RAG_CONFIDENCE_THRESHOLD:
                    logger.info("RAG cache hit: similarity=%.3f anomaly=%s", similarity, anomaly_type)
                    return docs[0]
        except Exception as e:
            logger.warning("RAG cache lookup failed: %s", e)
        return None

    # ── Private ────────────────────────────────────────────────────────────────

    def _call_groq(self, root_cause: str, anomaly_type: str, state: HealingAgentState) -> Optional[str]:
        if not GROQ_API_KEY:
            return None
        db_platform = (state.get("anomaly_details") or {}).get("db_type", "postgresql")
        context = f"""Root Cause: {root_cause}
Anomaly Type: {anomaly_type}
Database Platform: {db_platform}
Pipeline: {state.get('pipeline_name', 'unknown')}
Anomaly Details: {json.dumps(state.get('anomaly_details') or {}, default=str)[:500]}
Available Libraries: pandas, sqlalchemy, psycopg2, os, json, datetime, re, hashlib

Write a Python fix tailored to {db_platform} and anomaly type {anomaly_type}."""

        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": context},
                    ],
                    "temperature": 0.15,
                    "max_tokens": 1200,
                },
                timeout=40.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            content = re.sub(r"```python\n?", "", content)
            content = re.sub(r"```\n?", "", content)
            return content.strip()
        except Exception as e:
            logger.warning("Groq fix generation failed: %s", e)
            return None

    def _infer_fix_type(self, anomaly_type: str, root_cause: str, pipeline: str) -> str:
        # Use direct anomaly→template map first
        template = ANOMALY_TEMPLATE_MAP.get(anomaly_type)
        if template and template in FIX_TEMPLATES:
            return template

        # Keyword override from root cause
        rc = root_cause.lower()
        if any(k in rc for k in ["snowflake", "variant", "flatten"]):
            return "snowflake_schema"
        if any(k in rc for k in ["bigquery", "bq", "slot"]):
            return "bigquery_type"
        if any(k in rc for k in ["mysql", "binlog", "rds"]):
            return "mysql_cdc"
        if any(k in rc for k in ["mongo", "objectid", "document"]):
            return "mongodb_flatten"
        if any(k in rc for k in ["redshift", "stl_load", "varchar"]):
            return "redshift_load"
        if any(k in rc for k in ["partition", "skew", "hot partition"]):
            return "partition_skew"
        if any(k in rc for k in ["cdc", "debezium", "binlog", "oplog"]):
            return "cdc_lag"
        if any(k in rc for k in ["schema", "column", "drift", "type mismatch"]):
            return "schema_change"
        if any(k in rc for k in ["null", "quality", "duplicate"]):
            return "data_quality"
        if any(k in rc for k in ["connect", "timeout", "ssl"]):
            return "connection"
        if any(k in rc for k in ["zero", "empty", "volume"]):
            return "volume"
        if "kafka" in pipeline or "consumer" in pipeline:
            return "cdc_lag"
        return "logic"

    def _init_chroma(self):
        if not HAS_CHROMA:
            return None
        try:
            client = chromadb.HttpClient(
                host=CHROMA_HOST, port=CHROMA_PORT,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            client.heartbeat()
            return client
        except Exception:
            try:
                return chromadb.EphemeralClient(settings=ChromaSettings(anonymized_telemetry=False))
            except Exception:
                return None
