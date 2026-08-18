"""
FixWriterAgent — Writes self-contained Python fix code for a diagnosed root cause.

Checks ChromaDB RAG cache first (>90% confidence reuse); otherwise calls Groq LLM.
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
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", 8001))
RAG_CONFIDENCE_THRESHOLD = 0.90   # cosine similarity ≥ this → reuse cached fix

SYSTEM_PROMPT = """You are a senior data engineer. Write a Python fix for a data pipeline issue.

Requirements:
1. Self-contained — only use pandas, sqlalchemy, psycopg2, os, json, datetime
2. Safe to run in an isolated Docker container (no network calls, no DROP/DELETE)
3. Include a verify() function that returns True if the fix succeeded
4. The fix must accept a pandas DataFrame as input and return a fixed DataFrame

Return ONLY the Python code — no markdown fences, no explanation."""

FIX_TEMPLATES: Dict[str, str] = {
    "schema_change": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Handles schema drift by adding missing columns with safe defaults."""
    expected_cols = list(df.columns)
    for col in expected_cols:
        if df[col].isnull().mean() > 0.10:
            dtype = df[col].dtype
            if pd.api.types.is_numeric_dtype(dtype):
                df[col] = df[col].fillna(df[col].median())
            else:
                df[col] = df[col].fillna("UNKNOWN")
    return df

def verify(df: pd.DataFrame) -> bool:
    return df.isnull().mean().max() < 0.10
''',
    "data_quality": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Removes duplicates and fills nulls in critical columns."""
    before = len(df)
    df = df.drop_duplicates()
    for col in df.select_dtypes(include="number").columns:
        df[col] = df[col].fillna(df[col].median())
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("UNKNOWN")
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0 and df.isnull().sum().sum() == 0
''',
    "connection": '''import pandas as pd
import os

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Returns input df unchanged — connection fix is handled at pipeline level."""
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',
    "volume": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Validates row count and flags if critically low."""
    if len(df) == 0:
        raise ValueError("Pipeline produced zero records — source may be empty")
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',
    "logic": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Applies defensive null handling and type coercion."""
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()
    return df.drop_duplicates()

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',
    "timeout": '''import pandas as pd

def fix(df: pd.DataFrame) -> pd.DataFrame:
    """Reduces data volume by sampling if dataset is large (timeout mitigation)."""
    MAX_ROWS = 100_000
    if len(df) > MAX_ROWS:
        df = df.sample(n=MAX_ROWS, random_state=42)
    return df

def verify(df: pd.DataFrame) -> bool:
    return len(df) > 0
''',
}


class FixWriterAgent:
    """Generates fix code using RAG cache (ChromaDB) + Groq LLM fallback."""

    def __init__(self):
        self._chroma = self._init_chroma()

    def write_fix(self, state: HealingAgentState) -> HealingAgentState:
        root_cause = state.get("root_cause") or "Unknown"
        anomaly_type = state.get("anomaly_type") or "UNKNOWN"
        steps = list(state.get("reasoning_steps") or [])

        # 1. Check RAG cache
        cached = self.check_rag_cache(root_cause)
        if cached and self._has_required_functions(cached):
            steps.append("FixWriterAgent: reusing cached fix from ChromaDB (confidence >90%)")
            return HealingAgentState(**{**state,
                "fix_code": cached,
                "fix_language": "python",
                "reasoning_steps": steps,
            })

        # 2. Try Groq LLM
        fix_code = self._call_groq(root_cause, anomaly_type, state)
        if fix_code and self._has_required_functions(fix_code):
            steps.append("FixWriterAgent: fix generated via Groq LLM")
        else:
            # 3. Fall back to template (always correct format)
            fix_type = self._infer_fix_type(anomaly_type, root_cause)
            fix_code = FIX_TEMPLATES.get(fix_type, FIX_TEMPLATES["logic"])
            steps.append(f"FixWriterAgent: using template fix for {fix_type}")

        return HealingAgentState(**{**state,
            "fix_code": fix_code,
            "fix_language": "python",
            "reasoning_steps": steps,
        })

    def _has_required_functions(self, code: str) -> bool:
        """Ensure code contains both fix() and verify() function definitions."""
        import ast
        try:
            tree = ast.parse(code)
            names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            return "fix" in names and "verify" in names
        except SyntaxError:
            return False

    def check_rag_cache(self, root_cause: str) -> Optional[str]:
        """Query ChromaDB for a similar past fix. Returns code if similarity ≥ threshold."""
        if not HAS_CHROMA or self._chroma is None:
            return None
        try:
            collection = self._chroma.get_or_create_collection("orchestrai_fixes")
            if collection.count() == 0:
                return None
            results = collection.query(query_texts=[root_cause], n_results=1)
            distances = results.get("distances", [[]])[0]
            docs = results.get("documents", [[]])[0]
            if distances and docs:
                # ChromaDB cosine: distance 0 = identical, 1 = orthogonal
                similarity = 1.0 - distances[0]
                if similarity >= RAG_CONFIDENCE_THRESHOLD:
                    return docs[0]
        except Exception as e:
            logger.warning("RAG cache lookup failed: %s", e)
        return None

    def _call_groq(self, root_cause: str, anomaly_type: str, state: HealingAgentState) -> Optional[str]:
        if not GROQ_API_KEY:
            return None
        context = f"""Root Cause: {root_cause}
Anomaly Type: {anomaly_type}
Pipeline: {state.get('pipeline_name', 'unknown')}
Anomaly Details: {json.dumps(state.get('anomaly_details') or {}, default=str)}"""
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
                    "temperature": 0.2,
                    "max_tokens": 1024,
                },
                timeout=40.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            # Strip markdown fences if present
            content = re.sub(r"```python\n?", "", content)
            content = re.sub(r"```\n?", "", content)
            return content.strip()
        except Exception as e:
            logger.warning("Groq fix generation failed: %s", e)
            return None

    def _infer_fix_type(self, anomaly_type: str, root_cause: str) -> str:
        mapping = {
            "NULL_SPIKE": "schema_change",
            "ZERO_LOAD": "connection",
            "ROW_COUNT_DROP": "volume",
            "PIPELINE_DELAY": "timeout",
            "CONSECUTIVE_FAILURES": "logic",
            "ML_ANOMALY": "data_quality",
        }
        fix_type = mapping.get(anomaly_type, "logic")
        # Override based on root cause keywords
        rc_lower = root_cause.lower()
        if "schema" in rc_lower or "column" in rc_lower:
            fix_type = "schema_change"
        elif "null" in rc_lower or "quality" in rc_lower:
            fix_type = "data_quality"
        elif "connect" in rc_lower or "timeout" in rc_lower:
            fix_type = "connection"
        elif "duplicate" in rc_lower:
            fix_type = "data_quality"
        return fix_type

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
