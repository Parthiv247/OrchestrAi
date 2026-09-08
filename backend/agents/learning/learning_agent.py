"""
LearningAgent — ChromaDB RAG for pipeline fixes and NL queries.

2025 upgrades:
  - Rich metadata per fix: db_platform, anomaly_category, mttr_minutes, outcome_success
  - Similarity search with metadata pre-filtering (same anomaly type boosts relevance)
  - Fix outcome tracker: increments success/failure counters per fix pattern
  - NL query quality scoring: tracks thumbs-up ratio, returns high-quality SQL examples first
  - MTTR trend analysis: computes average resolution time per anomaly category
  - Feedback loop: deprecated fixes (2+ failures) are soft-deleted from cache
  - On-disk persistent ChromaDB with graceful HTTP fallback
"""
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CHROMA_HOST          = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT          = int(os.getenv("CHROMA_PORT", 8001))
SIMILARITY_THRESHOLD = 0.35   # cosine distance < threshold → candidate fix
HIGH_QUALITY_THRESHOLD = 0.25  # distance < 0.25 → high confidence reuse
MAX_DEPRECATED_FAILURES = 2    # retire fix after this many failures


class LearningAgent:
    """RAG store for pipeline fixes and NL queries via ChromaDB + local embeddings."""

    def __init__(self):
        self._chroma   = None
        self._embed_fn = None
        self._init()

    # ── Initialization ─────────────────────────────────────────────────────────

    def _init(self):
        try:
            import chromadb
            from chromadb.config import Settings
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

            self._embed_fn = SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )

            # Try HTTP client first, then local persistent
            try:
                client = chromadb.HttpClient(
                    host=CHROMA_HOST, port=CHROMA_PORT,
                    settings=Settings(anonymized_telemetry=False),
                )
                client.heartbeat()
                self._chroma = client
                logger.info("LearningAgent: connected to ChromaDB HTTP server")
            except Exception:
                persist_dir = Path(__file__).parent.parent.parent.parent / "ml" / "chromadb"
                persist_dir.mkdir(parents=True, exist_ok=True)
                self._chroma = chromadb.PersistentClient(
                    path=str(persist_dir),
                    settings=Settings(anonymized_telemetry=False),
                )
                logger.info("LearningAgent: using persistent ChromaDB at %s", persist_dir)

        except Exception as e:
            logger.error("LearningAgent init failed: %s — RAG will be unavailable", e)

    def _collection(self, name: str):
        if self._chroma is None:
            raise RuntimeError("ChromaDB not initialized")
        return self._chroma.get_or_create_collection(
            name=name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Pipeline Fixes ─────────────────────────────────────────────────────────

    def store_fix(self, incident_state: Dict[str, Any]) -> str:
        """Embed and store a deployed fix with rich metadata."""
        if self._chroma is None:
            return ""

        doc_id = incident_state.get("incident_id") or str(uuid.uuid4())
        fix_code = incident_state.get("fix_code") or ""

        # Build searchable document string
        doc = (
            f"anomaly:{incident_state.get('anomaly_type', '')} | "
            f"pipeline:{incident_state.get('pipeline_name', '')} | "
            f"root_cause:{incident_state.get('root_cause', '')} | "
            f"fix_preview:{fix_code[:400]}"
        )

        # Compute MTTR
        started_at  = incident_state.get("started_at")
        resolved_at = datetime.utcnow().isoformat()
        mttr_minutes = 0.0
        if started_at:
            try:
                start_dt  = datetime.fromisoformat(str(started_at))
                mttr_minutes = (datetime.utcnow() - start_dt).total_seconds() / 60
            except Exception:
                pass

        metadata = {
            "pipeline_name":    str(incident_state.get("pipeline_name") or ""),
            "anomaly_type":     str(incident_state.get("anomaly_type") or ""),
            "anomaly_category": self._categorize_anomaly(str(incident_state.get("anomaly_type") or "")),
            "db_platform":      str((incident_state.get("anomaly_details") or {}).get("db_type") or "postgresql"),
            "confidence_score": str(incident_state.get("confidence_score") or 0),
            "fix_language":     str(incident_state.get("fix_language") or "python"),
            "tests_passed":     str(incident_state.get("tests_passed") or 0),
            "tests_total":      "20",
            "mttr_minutes":     str(round(mttr_minutes, 1)),
            "success_count":    "1",
            "failure_count":    "0",
            "deprecated":       "false",
            "deployed_at":      resolved_at,
        }

        try:
            col = self._collection("pipeline_fixes")
            col.upsert(ids=[doc_id], documents=[doc], metadatas=[metadata])
            logger.info("LearningAgent: stored fix %s (MTTR=%.1f min)", doc_id[:8], mttr_minutes)
        except Exception as e:
            logger.warning("store_fix failed: %s", e)

        return doc_id

    def recall_fix(self, root_cause: str, anomaly_type: str = "",
                   db_platform: str = "") -> Optional[Dict[str, Any]]:
        """
        Search for the best matching past fix.
        Returns None if no good match, or dict with fix_code and metadata.
        """
        if self._chroma is None:
            return None

        try:
            col = self._collection("pipeline_fixes")
            if col.count() == 0:
                return None

            # Try filtered search first (same anomaly type, not deprecated)
            where_filter = {"deprecated": "false"}
            if anomaly_type:
                where_filter["anomaly_type"] = anomaly_type

            try:
                results = col.query(
                    query_texts=[root_cause], n_results=3,
                    where=where_filter,
                )
            except Exception:
                # Fallback: no filter
                results = col.query(query_texts=[root_cause], n_results=3)

            distances = results.get("distances", [[]])[0]
            docs      = results.get("documents", [[]])[0]
            metas     = results.get("metadatas", [[]])[0]

            if not distances or not docs:
                return None

            best_idx      = 0
            best_distance = distances[0]

            if best_distance > SIMILARITY_THRESHOLD:
                return None  # not similar enough

            meta = metas[best_idx] if metas else {}

            # Extract fix_code from document (after fix_preview:)
            doc_text = docs[best_idx]
            fix_code = ""
            if "fix_preview:" in doc_text:
                fix_code = doc_text.split("fix_preview:", 1)[1].strip()

            return {
                "fix_code":        fix_code,
                "similarity":      1.0 - best_distance,
                "confidence":      "high" if best_distance < HIGH_QUALITY_THRESHOLD else "medium",
                "anomaly_type":    meta.get("anomaly_type", ""),
                "pipeline_name":   meta.get("pipeline_name", ""),
                "db_platform":     meta.get("db_platform", ""),
                "tests_passed":    int(meta.get("tests_passed", 0)),
                "mttr_minutes":    float(meta.get("mttr_minutes", 0)),
                "success_count":   int(meta.get("success_count", 1)),
                "deployed_at":     meta.get("deployed_at", ""),
            }

        except Exception as e:
            logger.warning("recall_fix failed: %s", e)
            return None

    def record_fix_outcome(self, doc_id: str, success: bool):
        """Increment success/failure counter. Deprecate fix after MAX_DEPRECATED_FAILURES."""
        if self._chroma is None or not doc_id:
            return
        try:
            col    = self._collection("pipeline_fixes")
            result = col.get(ids=[doc_id], include=["metadatas"])
            if not result or not result.get("metadatas"):
                return
            meta = result["metadatas"][0]
            if success:
                meta["success_count"] = str(int(meta.get("success_count", 0)) + 1)
            else:
                fail_count = int(meta.get("failure_count", 0)) + 1
                meta["failure_count"] = str(fail_count)
                if fail_count >= MAX_DEPRECATED_FAILURES:
                    meta["deprecated"] = "true"
                    logger.warning("LearningAgent: deprecated fix %s after %d failures", doc_id[:8], fail_count)
            col.update(ids=[doc_id], metadatas=[meta])
        except Exception as e:
            logger.warning("record_fix_outcome failed: %s", e)

    # ── NL Queries ─────────────────────────────────────────────────────────────

    def store_nl_query(
        self, question: str, sql: str,
        rows_returned: int = 0, execution_time_ms: int = 0,
        feedback: int = 0,   # 1=thumbs_up, -1=thumbs_down, 0=none
    ) -> str:
        """Store a successful NL→SQL pair for future retrieval."""
        if self._chroma is None:
            return ""

        doc_id = str(uuid.uuid4())
        doc    = f"question: {question} | sql: {sql[:600]}"
        metadata = {
            "question":          question[:500],
            "sql_preview":       sql[:600],
            "rows_returned":     str(rows_returned),
            "execution_time_ms": str(execution_time_ms),
            "feedback":          str(feedback),
            "quality_score":     str(self._compute_quality_score(rows_returned, execution_time_ms, feedback)),
            "created_at":        datetime.utcnow().isoformat(),
        }
        try:
            col = self._collection("nl_queries")
            col.upsert(ids=[doc_id], documents=[doc], metadatas=[metadata])
        except Exception as e:
            logger.warning("store_nl_query failed: %s", e)
        return doc_id

    def recall_nl_query(self, question: str, n: int = 3) -> List[Dict[str, Any]]:
        """Find top-N similar past NL queries with their generated SQL."""
        if self._chroma is None:
            return []
        try:
            col = self._collection("nl_queries")
            if col.count() == 0:
                return []
            results = col.query(query_texts=[question], n_results=n)
            distances = results.get("distances", [[]])[0]
            metas     = results.get("metadatas", [[]])[0]
            out = []
            for dist, meta in zip(distances, metas):
                if dist < SIMILARITY_THRESHOLD:
                    out.append({
                        "sql":              meta.get("sql_preview", ""),
                        "similarity":       round(1.0 - dist, 3),
                        "rows_returned":    int(meta.get("rows_returned", 0)),
                        "feedback":         int(meta.get("feedback", 0)),
                        "quality_score":    float(meta.get("quality_score", 0)),
                    })
            # Sort by quality score descending
            out.sort(key=lambda x: x["quality_score"], reverse=True)
            return out
        except Exception as e:
            logger.warning("recall_nl_query failed: %s", e)
            return []

    def update_nl_feedback(self, doc_id: str, feedback: int):
        """Update thumbs up/down on a stored NL query."""
        if self._chroma is None:
            return
        try:
            col    = self._collection("nl_queries")
            result = col.get(ids=[doc_id], include=["metadatas"])
            if result and result.get("metadatas"):
                meta              = result["metadatas"][0]
                meta["feedback"]  = str(feedback)
                rows              = int(meta.get("rows_returned", 0))
                exec_time         = int(meta.get("execution_time_ms", 0))
                meta["quality_score"] = str(self._compute_quality_score(rows, exec_time, feedback))
                col.update(ids=[doc_id], metadatas=[meta])
        except Exception as e:
            logger.warning("update_nl_feedback failed: %s", e)

    # ── Analytics ─────────────────────────────────────────────────────────────

    def mttr_by_anomaly(self) -> Dict[str, float]:
        """Compute average MTTR (minutes) per anomaly type from stored fixes."""
        if self._chroma is None:
            return {}
        try:
            col     = self._collection("pipeline_fixes")
            results = col.get(include=["metadatas"])
            metas   = results.get("metadatas") or []
            totals: Dict[str, List[float]] = {}
            for meta in metas:
                if meta.get("deprecated") == "true":
                    continue
                atype  = meta.get("anomaly_type", "UNKNOWN")
                mttr   = float(meta.get("mttr_minutes", 0))
                totals.setdefault(atype, []).append(mttr)
            return {k: round(sum(v) / len(v), 1) for k, v in totals.items() if v}
        except Exception as e:
            logger.warning("mttr_by_anomaly failed: %s", e)
            return {}

    def learned_threshold_for_anomaly(self, anomaly_type: str,
                                       default: float = 0.75) -> float:
        """
        Derive a per-anomaly-type sandbox confidence threshold from historical outcomes.

        Logic:
          - Collect all non-deprecated fixes for this anomaly_type.
          - For each, compute an implied threshold: success_count / (success_count + failure_count).
          - Return the weighted average, clamped to [0.60, 0.95].
          - Falls back to `default` (0.75) when fewer than 3 data points exist.

        This replaces the static SANDBOX_CONFIDENCE_THRESHOLD = 0.75 in the orchestrator
        so the routing adapts as the platform accumulates incident history.
        """
        if self._chroma is None:
            return default
        try:
            col     = self._collection("pipeline_fixes")
            results = col.get(include=["metadatas"])
            metas   = results.get("metadatas") or []
            scores: List[float] = []
            for meta in metas:
                if meta.get("deprecated") == "true":
                    continue
                if meta.get("anomaly_type", "") != anomaly_type:
                    continue
                succ = int(meta.get("success_count", 0) or 0)
                fail = int(meta.get("failure_count", 0) or 0)
                total = succ + fail
                if total == 0:
                    continue
                # implied threshold: fixes with high success need a lower bar to proceed;
                # fixes with many failures raise the bar to protect production.
                implied = 0.60 + 0.35 * (succ / total)   # range [0.60, 0.95]
                scores.append(implied)
            if len(scores) < 3:
                return default
            learned = round(sum(scores) / len(scores), 3)
            return max(0.60, min(0.95, learned))
        except Exception as e:
            logger.warning("learned_threshold_for_anomaly failed: %s", e)
            return default

    def fix_success_rate(self) -> Dict[str, Any]:
        """Overall fix success rate and per-anomaly breakdown."""
        if self._chroma is None:
            return {"overall": 0, "by_anomaly": {}}
        try:
            col     = self._collection("pipeline_fixes")
            results = col.get(include=["metadatas"])
            metas   = results.get("metadatas") or []
            total_success = 0
            total_runs    = 0
            by_anomaly: Dict[str, Dict] = {}

            for meta in metas:
                atype   = meta.get("anomaly_type", "UNKNOWN")
                success = int(meta.get("success_count", 1))
                failure = int(meta.get("failure_count", 0))
                total_success += success
                total_runs    += success + failure
                if atype not in by_anomaly:
                    by_anomaly[atype] = {"success": 0, "failure": 0}
                by_anomaly[atype]["success"] += success
                by_anomaly[atype]["failure"] += failure

            overall = (total_success / total_runs * 100) if total_runs > 0 else 0
            rates   = {k: round(v["success"] / (v["success"] + v["failure"]) * 100, 1)
                       for k, v in by_anomaly.items() if (v["success"] + v["failure"]) > 0}
            return {"overall": round(overall, 1), "total_fixes": total_runs,
                    "by_anomaly": rates}
        except Exception as e:
            logger.warning("fix_success_rate failed: %s", e)
            return {"overall": 0, "by_anomaly": {}}

    def get_learning_stats(self) -> Dict[str, Any]:
        """Summary stats for the /api/learning/stats endpoint."""
        if self._chroma is None:
            return {"fixes_stored": 0, "queries_stored": 0, "mttr_avg_minutes": 0,
                    "success_rate_pct": 0, "top_anomalies": []}
        try:
            fix_count   = self._collection("pipeline_fixes").count()
            query_count = self._collection("nl_queries").count()
            mttr_map    = self.mttr_by_anomaly()
            success     = self.fix_success_rate()
            mttr_avg    = (sum(mttr_map.values()) / len(mttr_map)) if mttr_map else 0
            top_anomalies = sorted(success.get("by_anomaly", {}).items(),
                                   key=lambda x: x[1], reverse=True)[:5]
            return {
                "fixes_stored":      fix_count,
                "queries_stored":    query_count,
                "mttr_avg_minutes":  round(mttr_avg, 1),
                "success_rate_pct":  success.get("overall", 0),
                "top_anomalies":     [{"type": k, "success_rate": v} for k, v in top_anomalies],
                "mttr_by_anomaly":   mttr_map,
            }
        except Exception as e:
            logger.warning("get_learning_stats failed: %s", e)
            return {"fixes_stored": 0, "queries_stored": 0}

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _categorize_anomaly(anomaly_type: str) -> str:
        categories = {
            "data_freshness":  {"ZERO_LOAD", "ROW_COUNT_DROP", "INCREMENTAL_SYNC_FAILURE", "CDC_LAG"},
            "data_quality":    {"NULL_SPIKE", "DUPLICATE_SPIKE", "DATA_TYPE_MISMATCH", "SCHEMA_DRIFT"},
            "infrastructure":  {"PIPELINE_DELAY", "SLA_BREACH", "RATE_LIMIT_HIT", "CASCADING_FAILURE"},
            "reliability":     {"CONSECUTIVE_FAILURES", "CHECKPOINT_FAILURE", "PARTITION_SKEW"},
        }
        for cat, types in categories.items():
            if anomaly_type in types:
                return cat
        return "unknown"

    @staticmethod
    def _compute_quality_score(rows_returned: int, execution_time_ms: int, feedback: int) -> float:
        """Quality score 0–1 for a NL query result."""
        score = 0.5
        if rows_returned > 0:
            score += 0.2
        if execution_time_ms < 2000:
            score += 0.1
        elif execution_time_ms > 10000:
            score -= 0.1
        score += feedback * 0.2   # +0.2 thumbs up, -0.2 thumbs down
        return round(max(0.0, min(1.0, score)), 3)
