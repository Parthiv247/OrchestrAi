"""
LearningAgent — ChromaDB RAG for pipeline fixes and NL queries.

Uses sentence-transformers/all-MiniLM-L6-v2 (local, no API) for embeddings.
Collections:
  - pipeline_fixes : stores every deployed pipeline fix
  - nl_queries     : stores every successful NL→SQL pair
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", 8001))
SIMILARITY_THRESHOLD = 0.35   # cosine distance < 0.35 → used for auto-heal candidates; final confidence check uses distance


class LearningAgent:
    """RAG store for pipeline fixes and NL queries using ChromaDB + local embeddings."""

    def __init__(self):
        self._chroma = None
        self._embed_fn = None
        self._init()

    def _init(self):
        """Initialize ChromaDB client with local sentence-transformer embedding function."""
        try:
            import chromadb
            from chromadb.config import Settings
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            from pathlib import Path

            self._embed_fn = SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )

            # Try HTTP client first, then local persistent client
            try:
                client = chromadb.HttpClient(
                    host=CHROMA_HOST, port=CHROMA_PORT,
                    settings=Settings(anonymized_telemetry=False),
                )
                client.heartbeat()
                self._chroma = client
                logger.info("LearningAgent: connected to ChromaDB server")
            except Exception:
                # Use on-disk persistent client — survives between Python processes
                persist_dir = Path(__file__).parent.parent.parent.parent / "ml" / "chromadb"
                persist_dir.mkdir(parents=True, exist_ok=True)
                self._chroma = chromadb.PersistentClient(
                    path=str(persist_dir),
                    settings=Settings(anonymized_telemetry=False),
                )
                logger.info("LearningAgent: using persistent ChromaDB at %s", persist_dir)

        except Exception as e:
            logger.error("LearningAgent init failed: %s", e)

    def _collection(self, name: str):
        return self._chroma.get_or_create_collection(
            name=name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Pipeline Fixes ─────────────────────────────────────────────────────────

    def store_fix(self, incident_state: Dict[str, Any]) -> str:
        """Embed and store a deployed pipeline fix. Returns the stored doc ID."""
        if self._chroma is None:
            return ""
        doc_id = incident_state.get("incident_id") or str(uuid.uuid4())
        doc = (
            f"{incident_state.get('pipeline_name','')} | "
            f"{incident_state.get('anomaly_type','')} | "
            f"{incident_state.get('root_cause','')} | "
            f"{incident_state.get('fix_code','')[:500]}"
        )
        metadata = {
            "pipeline_name":    str(incident_state.get("pipeline_name") or ""),
            "anomaly_type":     str(incident_state.get("anomaly_type") or ""),
            "confidence_score": str(incident_state.get("confidence_score") or 0),
            "fix_language":     str(incident_state.get("fix_language") or "python"),
            "tests_passed":     str(incident_state.get("tests_passed") or 0),
            "deployed_at":      datetime.utcnow().isoformat(),
        }
        try:
            col = self._collection("pipeline_fixes")
            col.upsert(ids=[doc_id], documents=[doc], metadatas=[metadata])
            logger.info("LearningAgent: stored fix %s", doc_id[:8])
        except Exception as e:
            logger.warning("store_fix failed: %s", e)
        return doc_id

    def retrieve_similar_fix(
        self,
        anomaly_type: str,
        root_cause: str,
        pipeline_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Find the most similar past fix.
        Returns fix dict if cosine distance < SIMILARITY_THRESHOLD (>90%), else None.
        """
        if self._chroma is None:
            return None
        query = f"{pipeline_name} | {anomaly_type} | {root_cause}"
        try:
            col = self._collection("pipeline_fixes")
            if col.count() == 0:
                return None
            results = col.query(query_texts=[query], n_results=1)
            distances = (results.get("distances") or [[]])[0]
            docs      = (results.get("documents") or [[]])[0]
            metas     = (results.get("metadatas") or [[]])[0]
            if distances and docs and distances[0] < SIMILARITY_THRESHOLD:
                parts = docs[0].split(" | ")
                return {
                    "fix_code":     parts[3] if len(parts) > 3 else docs[0],
                    "distance":     distances[0],
                    "confidence":   round(1.0 - distances[0], 3),
                    "metadata":     metas[0] if metas else {},
                }
        except Exception as e:
            logger.warning("retrieve_similar_fix failed: %s", e)
        return None

    # ── NL Queries ─────────────────────────────────────────────────────────────

    def store_query(self, question: str, sql: str, metadata: Optional[Dict] = None) -> str:
        """Embed and store a successful NL→SQL pair."""
        if self._chroma is None:
            return ""
        doc_id = str(uuid.uuid4())
        tables = self._extract_tables(sql)
        doc = f"{question} | {sql[:400]} | {', '.join(tables)}"
        meta = {
            "question":          question[:200],
            "sql":               sql[:500],
            "execution_time_ms": str((metadata or {}).get("execution_time_ms", 0)),
            "rows_returned":     str((metadata or {}).get("rows_returned", 0)),
            "chart_type":        str((metadata or {}).get("chart_type", "table")),
            "stored_at":         datetime.utcnow().isoformat(),
        }
        try:
            col = self._collection("nl_queries")
            col.upsert(ids=[doc_id], documents=[doc], metadatas=[meta])
            logger.info("LearningAgent: stored query %s", doc_id[:8])
        except Exception as e:
            logger.warning("store_query failed: %s", e)
        return doc_id

    def retrieve_similar_query(self, question: str) -> Optional[Dict[str, Any]]:
        """Find a similar past NL question and return its SQL if confident."""
        if self._chroma is None:
            return None
        try:
            col = self._collection("nl_queries")
            if col.count() == 0:
                return None
            results = col.query(query_texts=[question], n_results=1)
            distances = (results.get("distances") or [[]])[0]
            metas     = (results.get("metadatas") or [[]])[0]
            if distances and metas and distances[0] < 0.20:   # looser threshold for queries
                return {
                    "suggested_sql": metas[0].get("sql", ""),
                    "past_question": metas[0].get("question", ""),
                    "distance":      distances[0],
                    "confidence":    round(1.0 - distances[0], 3),
                }
        except Exception as e:
            logger.warning("retrieve_similar_query failed: %s", e)
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Return ChromaDB collection statistics."""
        if self._chroma is None:
            return {"error": "ChromaDB not initialized", "total_fixes_stored": 0,
                    "total_queries_stored": 0, "auto_healed_count": 0}
        try:
            fixes   = self._collection("pipeline_fixes")
            queries = self._collection("nl_queries")
            fix_count   = fixes.count()
            query_count = queries.count()

            # Count high-confidence auto-heal candidates
            auto_heal = 0
            if fix_count > 0:
                try:
                    all_metas = fixes.get(include=["metadatas"])["metadatas"]
                    auto_heal = sum(
                        1 for m in all_metas
                        if float(m.get("confidence_score", 0)) >= 0.75
                    )
                except Exception:
                    pass

            top_anomalies: Dict[str, int] = {}
            if fix_count > 0:
                try:
                    all_metas = fixes.get(include=["metadatas"])["metadatas"]
                    for m in all_metas:
                        at = m.get("anomaly_type", "unknown")
                        top_anomalies[at] = top_anomalies.get(at, 0) + 1
                except Exception:
                    pass

            return {
                "total_fixes_stored":   fix_count,
                "total_queries_stored": query_count,
                "auto_healed_count":    auto_heal,
                "top_anomaly_types":    sorted(top_anomalies.items(), key=lambda x: -x[1])[:5],
                "backend":              "server" if not getattr(self._chroma, "_is_persistent", False) else "persistent",
            }
        except Exception as e:
            return {"error": str(e)}

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _extract_tables(self, sql: str) -> List[str]:
        import re
        return list(set(re.findall(r"\b(?:raw|staging|marts)\.\w+", sql, re.IGNORECASE)))
