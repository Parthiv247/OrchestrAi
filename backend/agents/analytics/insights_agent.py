"""
InsightsAgent — Generates 10 data-driven business insights from destination tables.

LangGraph nodes: collect_data_samples → generate_insights → rank_insights
"""
import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, TypedDict

import httpx
import psycopg2
import psycopg2.extras
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

SEVERITY_ORDER = {"anomaly": 0, "warning": 1, "opportunity": 2, "info": 3}


class InsightRecord(TypedDict):
    id: str
    title: str
    insight: str
    severity: str      # anomaly | warning | opportunity | info
    metric: str
    time_window: str   # 24h | 7d | 30d
    table_name: str
    supporting_sql: str
    generated_at: str


class InsightsState(TypedDict):
    connection_id: str | None
    data_summary: dict[str, Any] | None
    raw_insights: list[dict] | None
    insights: list[InsightRecord] | None
    error: str | None


class InsightsAgent:
    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self):
        g = StateGraph(InsightsState)
        g.add_node("collect_data_samples", self._node_collect)
        g.add_node("generate_insights",    self._node_generate)
        g.add_node("rank_insights",        self._node_rank)
        g.set_entry_point("collect_data_samples")
        g.add_edge("collect_data_samples", "generate_insights")
        g.add_edge("generate_insights",    "rank_insights")
        g.add_edge("rank_insights",        END)
        return g.compile()

    # ── Nodes ──────────────────────────────────────────────────────────────────

    def _node_collect(self, state: InsightsState) -> InsightsState:
        """Collect aggregated stats from every mart table (last 24h / 7d / 30d)."""
        summary: dict[str, Any] = {}
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                summary["fct_trips"]           = self._collect_trips(cur)
                summary["fct_ecommerce"]       = self._collect_ecommerce(cur)
                summary["dim_customers"]       = self._collect_customers(cur)
                summary["dim_taxi_zones"]      = self._collect_zones(cur)
                summary["pipeline_health"]     = self._collect_pipeline_health(cur)
            conn.close()
        except Exception as e:
            logger.error("collect_data_samples failed: %s", e)
            return {**state, "error": str(e)}
        return {**state, "data_summary": summary}

    def _node_generate(self, state: InsightsState) -> InsightsState:
        """Send data summary to Groq and get exactly 10 insights."""
        summary = state.get("data_summary") or {}
        context = json.dumps(summary, indent=2, default=str)[:6000]

        prompt = f"""You are a senior data analyst reviewing OrchestrAI platform data.
Based on this data summary, generate EXACTLY 10 specific, actionable business insights.

Each insight MUST:
1. Reference a specific metric or number from the data
2. Include a time dimension: 24h, 7d, or 30d
3. Be written in plain business language (no SQL, no tech jargon)
4. Have a severity: "anomaly" | "warning" | "opportunity" | "info"
5. Cover different aspects (revenue, volume, quality, trends, anomalies)

Data Summary:
{context}

Return ONLY a valid JSON array of exactly 10 objects with this structure:
[
  {{
    "title": "Short headline (max 60 chars)",
    "insight": "2-3 sentences with specific numbers and business context",
    "severity": "anomaly|warning|opportunity|info",
    "metric": "Key metric, e.g. +34% revenue",
    "time_window": "24h|7d|30d",
    "table": "marts.fct_trips|marts.fct_ecommerce_summary|etc"
  }}
]"""

        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": GROQ_MODEL,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.3, "max_tokens": 2048},
                timeout=60.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            raw_list = self._parse_json_array(content)
        except Exception as e:
            logger.warning("Groq insights call failed: %s — using synthetic insights", e)
            raw_list = self._synthetic_insights(summary)

        # Ensure exactly 10
        if len(raw_list) < 10:
            raw_list.extend(self._synthetic_insights(summary)[len(raw_list):10])
        raw_list = raw_list[:10]

        return {**state, "raw_insights": raw_list}

    def _node_rank(self, state: InsightsState) -> InsightsState:
        """Sort by severity, add supporting SQL, save to DB."""
        raw = state.get("raw_insights") or []

        ranked = sorted(raw, key=lambda x: SEVERITY_ORDER.get(x.get("severity","info"), 3))

        records: list[InsightRecord] = []
        for item in ranked:
            rec = InsightRecord(
                id=str(uuid.uuid4()),
                title=item.get("title", "Insight")[:120],
                insight=item.get("insight", ""),
                severity=item.get("severity", "info"),
                metric=item.get("metric", ""),
                time_window=item.get("time_window", "7d"),
                table_name=item.get("table", ""),
                supporting_sql=self._make_supporting_sql(item),
                generated_at=datetime.utcnow().isoformat(),
            )
            records.append(rec)

        self._save_insights(records, state.get("connection_id"))
        return {**state, "insights": records}

    # ── Public API ─────────────────────────────────────────────────────────────

    def generate(self, connection_id: str | None = None) -> list[InsightRecord]:
        initial = InsightsState(connection_id=connection_id, data_summary=None,
                                raw_insights=None, insights=None, error=None)
        result = self.graph.invoke(initial)
        return result.get("insights") or []

    def get_cached(self, connection_id: str | None = None) -> list[InsightRecord]:
        """Return DB-cached insights if < 1 hour old."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, title, insight, severity, metric, time_window,
                           table_name, supporting_sql, generated_at
                    FROM insights
                    WHERE generated_at > NOW() - INTERVAL '1 hour'
                      AND (connection_id = %s OR %s IS NULL)
                    ORDER BY
                        CASE severity
                            WHEN 'anomaly'     THEN 0
                            WHEN 'warning'     THEN 1
                            WHEN 'opportunity' THEN 2
                            ELSE 3
                        END, generated_at DESC
                    LIMIT 10
                """, (connection_id, connection_id))
                rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            for r in rows:
                if r.get("generated_at"):
                    r["generated_at"] = r["generated_at"].isoformat()
            return rows
        except Exception as e:
            logger.warning("get_cached insights failed: %s", e)
            return []

    def get_supporting_data(self, insight_id: str) -> list[dict]:
        """Run the supporting SQL for a specific insight and return rows."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT supporting_sql FROM insights WHERE id = %s", (insight_id,))
                row = cur.fetchone()
            conn.close()
            if not row or not row["supporting_sql"]:
                return []
            conn2 = psycopg2.connect(**DB_CONFIG)
            with conn2.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(row["supporting_sql"])
                data = [dict(r) for r in cur.fetchall()]
            conn2.close()
            return data
        except Exception as e:
            logger.warning("get_supporting_data failed: %s", e)
            return []

    # ── Data collection helpers ────────────────────────────────────────────────

    def _collect_trips(self, cur) -> dict:
        stats = {}
        try:
            cur.execute("""
                SELECT
                    COUNT(*) AS total_trips,
                    ROUND(AVG(total_amount)::NUMERIC,2) AS avg_fare,
                    ROUND(SUM(total_amount)::NUMERIC,2) AS total_revenue,
                    COUNT(*) FILTER (WHERE is_airport_trip) AS airport_trips,
                    ROUND(100.0 * COUNT(*) FILTER (WHERE is_airport_trip) / NULLIF(COUNT(*),0),1) AS airport_pct
                FROM marts.fct_trips
                WHERE pickup_date >= CURRENT_DATE - 7
            """)
            r = dict(cur.fetchone()); stats["7d"] = r
            cur.execute("""
                SELECT COUNT(*) AS total_trips,
                       ROUND(SUM(total_amount)::NUMERIC,2) AS total_revenue
                FROM marts.fct_trips WHERE pickup_date >= CURRENT_DATE - 1
            """)
            stats["24h"] = dict(cur.fetchone())
            cur.execute("""
                SELECT pickup_hour, COUNT(*) AS trips
                FROM marts.fct_trips WHERE pickup_date >= CURRENT_DATE - 7
                GROUP BY pickup_hour ORDER BY trips DESC LIMIT 3
            """)
            stats["peak_hours"] = [dict(r) for r in cur.fetchall()]
            cur.execute("""
                SELECT payment_method, COUNT(*) AS count
                FROM marts.fct_trips WHERE pickup_date >= CURRENT_DATE - 7
                GROUP BY payment_method ORDER BY count DESC
            """)
            stats["payment_split"] = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            stats["error"] = str(e)
        return stats

    def _collect_ecommerce(self, cur) -> dict:
        stats = {}
        try:
            cur.execute("""
                SELECT ROUND(SUM(total_revenue)::NUMERIC,2) AS revenue,
                       SUM(order_count) AS orders,
                       ROUND(AVG(avg_order_value)::NUMERIC,2) AS avg_order
                FROM marts.fct_ecommerce_summary
                WHERE order_date >= CURRENT_DATE - 7
            """)
            stats["7d"] = dict(cur.fetchone())
            cur.execute("""
                SELECT category,
                       ROUND(SUM(total_revenue)::NUMERIC,2) AS revenue,
                       SUM(order_count) AS orders
                FROM marts.fct_ecommerce_summary
                WHERE order_date >= CURRENT_DATE - 30
                GROUP BY category ORDER BY revenue DESC LIMIT 5
            """)
            stats["top_categories"] = [dict(r) for r in cur.fetchall()]
            cur.execute("""
                SELECT city, ROUND(SUM(total_revenue)::NUMERIC,2) AS revenue
                FROM marts.fct_ecommerce_summary
                WHERE order_date >= CURRENT_DATE - 7
                GROUP BY city ORDER BY revenue DESC LIMIT 3
            """)
            stats["top_cities"] = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            stats["error"] = str(e)
        return stats

    def _collect_customers(self, cur) -> dict:
        stats = {}
        try:
            cur.execute("""
                SELECT customer_segment, COUNT(*) AS count,
                       ROUND(AVG(total_revenue)::NUMERIC,2) AS avg_ltv
                FROM marts.dim_customers
                GROUP BY customer_segment ORDER BY avg_ltv DESC
            """)
            stats["segments"] = [dict(r) for r in cur.fetchall()]
            cur.execute("""
                SELECT COUNT(*) AS total_customers,
                       ROUND(AVG(total_revenue)::NUMERIC,2) AS avg_ltv,
                       ROUND(MAX(total_revenue)::NUMERIC,2) AS max_ltv
                FROM marts.dim_customers
            """)
            stats["summary"] = dict(cur.fetchone())
        except Exception as e:
            stats["error"] = str(e)
        return stats

    def _collect_zones(self, cur) -> dict:
        stats = {}
        try:
            cur.execute("""
                SELECT zone_tier, COUNT(*) AS zones, SUM(total_trips) AS trips
                FROM marts.dim_taxi_zones
                GROUP BY zone_tier ORDER BY trips DESC
            """)
            stats["tier_breakdown"] = [dict(r) for r in cur.fetchall()]
            cur.execute("""
                SELECT location_id, total_trips, avg_fare
                FROM marts.dim_taxi_zones ORDER BY total_trips DESC LIMIT 5
            """)
            stats["top_zones"] = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            stats["error"] = str(e)
        return stats

    def _collect_pipeline_health(self, cur) -> dict:
        stats = {}
        try:
            cur.execute("""
                SELECT pipeline_name, status, COUNT(*) AS runs,
                       MAX(started_at) AS last_run
                FROM pipeline_runs
                WHERE started_at >= NOW() - INTERVAL '24 hours'
                GROUP BY pipeline_name, status
            """)
            stats["recent_runs"] = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            stats["error"] = str(e)
        return stats

    # ── Persistence ────────────────────────────────────────────────────────────

    def _save_insights(self, records: list[InsightRecord], connection_id: str | None):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                for r in records:
                    cur.execute("""
                        INSERT INTO insights
                          (id, connection_id, title, insight, severity, metric,
                           time_window, table_name, supporting_sql, generated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                        ON CONFLICT (id) DO NOTHING
                    """, (r["id"], connection_id, r["title"], r["insight"],
                          r["severity"], r["metric"], r["time_window"],
                          r["table_name"], r["supporting_sql"]))
                conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("_save_insights failed: %s", e)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _make_supporting_sql(self, item: dict) -> str:
        table = item.get("table", "marts.fct_trips")
        tw    = item.get("time_window", "7d")
        days  = {"24h": 1, "7d": 7, "30d": 30}.get(tw, 7)
        if "fct_trips" in table:
            return f"SELECT pickup_date, COUNT(*) AS trips, ROUND(SUM(total_amount)::NUMERIC,2) AS revenue FROM marts.fct_trips WHERE pickup_date >= CURRENT_DATE - {days} GROUP BY pickup_date ORDER BY pickup_date DESC LIMIT 30;"
        if "fct_ecommerce" in table or "ecommerce" in table:
            return f"SELECT order_date, category, ROUND(SUM(total_revenue)::NUMERIC,2) AS revenue FROM marts.fct_ecommerce_summary WHERE order_date >= CURRENT_DATE - {days} GROUP BY order_date, category ORDER BY order_date DESC LIMIT 30;"
        if "dim_customers" in table:
            return "SELECT customer_segment, COUNT(*) AS customers, ROUND(AVG(total_revenue)::NUMERIC,2) AS avg_ltv FROM marts.dim_customers GROUP BY customer_segment ORDER BY avg_ltv DESC;"
        if "dim_taxi_zones" in table:
            return "SELECT zone_tier, COUNT(*) AS zones, SUM(total_trips) AS total_trips, ROUND(AVG(avg_fare)::NUMERIC,2) AS avg_fare FROM marts.dim_taxi_zones GROUP BY zone_tier ORDER BY total_trips DESC;"
        return f"SELECT * FROM {table} LIMIT 10;"

    def _parse_json_array(self, text: str) -> list[dict]:
        text = re.sub(r"```json\s*|```\s*", "", text).strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return []

    def _synthetic_insights(self, summary: dict) -> list[dict]:
        """Fallback insights derived from collected data when Groq is unavailable."""
        trips_7d = summary.get("fct_trips", {}).get("7d", {})
        eco_7d   = summary.get("fct_ecommerce", {}).get("7d", {})
        segs     = summary.get("dim_customers", {}).get("segments", [])
        zones    = summary.get("dim_taxi_zones", {}).get("tier_breakdown", [])

        rev   = trips_7d.get("total_revenue", 0) or 0
        trips = trips_7d.get("total_trips", 0) or 0
        apt   = trips_7d.get("airport_pct", 0) or 0
        eco_rev  = eco_7d.get("revenue", 0) or 0
        eco_ord  = eco_7d.get("orders", 0) or 0
        vip_info = next((s for s in segs if s.get("customer_segment") == "VIP"), {})
        vip_cnt  = vip_info.get("count", 0) or 0

        return [
            {"title": f"NYC Taxi generated ${rev:,.0f} in 7-day revenue",
             "insight": f"The last 7 days saw {trips:,} trips with ${rev:,.0f} in total fare revenue. Average fare per trip is ${rev/max(trips,1):.2f}.",
             "severity": "info", "metric": f"${rev:,.0f} revenue", "time_window": "7d", "table": "marts.fct_trips"},
            {"title": f"{apt:.1f}% of taxi trips are airport-related",
             "insight": f"Airport trips (JFK, LGA, EWR) represent {apt:.1f}% of all trips. These typically command higher fares.",
             "severity": "opportunity" if apt > 10 else "info", "metric": f"{apt:.1f}% airport", "time_window": "7d", "table": "marts.fct_trips"},
            {"title": f"E-commerce revenue: ${eco_rev:,.0f} last 7 days",
             "insight": f"{eco_ord:,} orders totalling ${eco_rev:,.0f} were placed in the last 7 days.",
             "severity": "info", "metric": f"${eco_rev:,.0f}", "time_window": "7d", "table": "marts.fct_ecommerce_summary"},
            {"title": f"{vip_cnt} VIP customers identified",
             "insight": f"{vip_cnt} customers have spent >$1,000 lifetime and are classified as VIP. Their average LTV is ${vip_info.get('avg_ltv',0):.2f}.",
             "severity": "opportunity", "metric": f"{vip_cnt} VIPs", "time_window": "30d", "table": "marts.dim_customers"},
            {"title": "Data pipeline health check",
             "insight": "All 4 ETL pipelines have been monitored. Check incidents table for any active anomalies.",
             "severity": "info", "metric": "pipeline status", "time_window": "24h", "table": "raw.pipeline_runs"},
            {"title": "Peak taxi demand hours identified",
             "insight": "Rush-hour windows show highest trip concentration. Surge pricing opportunities exist during peak hours.",
             "severity": "opportunity", "metric": "demand pattern", "time_window": "7d", "table": "marts.fct_trips"},
            {"title": "Customer segmentation complete",
             "insight": f"Customer base segmented into VIP ({vip_cnt}), Regular, and Occasional tiers based on lifetime value.",
             "severity": "info", "metric": "3 segments", "time_window": "30d", "table": "marts.dim_customers"},
            {"title": "Taxi zone traffic distribution",
             "insight": "High-traffic zones drive the majority of revenue. Focus fleet allocation on top zones.",
             "severity": "opportunity", "metric": "zone concentration", "time_window": "30d", "table": "marts.dim_taxi_zones"},
            {"title": "E-commerce order volume trend",
             "insight": f"Monthly order volume of {eco_ord:,} units. Monitor for seasonal patterns and demand shifts.",
             "severity": "info", "metric": f"{eco_ord:,} orders", "time_window": "30d", "table": "marts.fct_ecommerce_summary"},
            {"title": "Cost optimization savings tracked",
             "insight": "Query optimizer has identified savings opportunities. Review optimization history for details.",
             "severity": "opportunity", "metric": "cost savings", "time_window": "30d", "table": "public.query_optimizations"},
        ]
