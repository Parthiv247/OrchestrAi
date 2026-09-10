"""
Data Lineage API — dbt manifest parsing for table + column-level lineage.

GET /api/lineage/graph           — full lineage graph (nodes + edges)
GET /api/lineage/node/{name}     — single node detail with column lineage
GET /api/lineage/columns/{name}  — column-level upstream/downstream for a model
"""
import json
import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lineage")

# ── Manifest loader ────────────────────────────────────────────────────────────

MANIFEST_PATHS = [
    Path(__file__).parent.parent.parent.parent / "dbt_project" / "target" / "manifest.json",
    Path("/app/dbt_project/target/manifest.json"),
    Path(os.getenv("DBT_MANIFEST_PATH", "")),
]


def _load_manifest() -> dict | None:
    for p in MANIFEST_PATHS:
        try:
            if p.exists():
                with open(p) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load manifest from {p}: {e}")
    return None


def _short_name(unique_id: str) -> str:
    """model.orchestrai.stg_orders → stg_orders"""
    return unique_id.split(".")[-1]


def _node_layer(name: str, resource_type: str, schema: str = "") -> str:
    """Infer layer from name prefix / schema."""
    if resource_type == "source":
        return "source"
    n = name.lower()
    s = schema.lower()
    if n.startswith("stg_") or s == "staging":
        return "staging"
    if n.startswith("fct_") or n.startswith("dim_") or s == "marts":
        return "mart"
    if n.startswith("raw_") or s == "raw":
        return "raw"
    # Default: if it's a base model it's raw
    return "raw"


# ── Infer column-level lineage from SQL (simple regex) ────────────────────────

def _infer_column_lineage(raw_code: str, source_columns: list[str], dest_columns: list[str]) -> list[dict]:
    """
    Very simple heuristic: look for SELECT <col> or <alias> AS <col> patterns.
    Returns list of {source_col, dest_col} mappings.
    """
    mappings = []
    if not raw_code:
        # Fallback: assume same-name passthrough for matched columns
        matched = set(source_columns) & set(dest_columns)
        return [{"source_col": c, "dest_col": c, "transform": "passthrough"} for c in matched]

    # Find AS aliases: `source_col AS dest_col` or `source_col as dest_col`
    alias_pattern = re.compile(r'\b(\w+)\s+[Aa][Ss]\s+(\w+)\b')
    for m in alias_pattern.finditer(raw_code):
        src, dst = m.group(1), m.group(2)
        if src in source_columns and dst in dest_columns:
            mappings.append({"source_col": src, "dest_col": dst, "transform": "alias"})

    # Direct passthrough: source col appears in SELECT and exists in dest
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', raw_code, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_clause = select_match.group(1)
        # Remove already-aliased
        aliased_src = {m["source_col"] for m in mappings}
        aliased_dst = {m["dest_col"] for m in mappings}
        for col in source_columns:
            if col in select_clause and col not in aliased_src and col in dest_columns and col not in aliased_dst:
                mappings.append({"source_col": col, "dest_col": col, "transform": "passthrough"})

    # If no mappings found at all, do best-effort name matching
    if not mappings:
        for col in dest_columns:
            # Look for the column name anywhere in raw_code
            if col in raw_code and col in source_columns:
                mappings.append({"source_col": col, "dest_col": col, "transform": "inferred"})

    return mappings


# ── Graph builder from manifest ────────────────────────────────────────────────

def _build_graph_from_manifest(manifest: dict) -> dict:
    nodes_out = []
    edges_out = []
    seen_ids = set()

    raw_nodes = manifest.get("nodes", {})
    raw_sources = manifest.get("sources", {})

    # Process sources
    for uid, src in raw_sources.items():
        name = src.get("name", _short_name(uid))
        layer = "source"
        columns = list(src.get("columns", {}).keys())
        node = {
            "id": uid,
            "name": name,
            "label": name,
            "layer": layer,
            "resource_type": "source",
            "schema": src.get("schema", ""),
            "description": src.get("description", ""),
            "columns": columns,
            "column_details": [
                {"name": k, "description": v.get("description", ""), "data_type": v.get("data_type", "")}
                for k, v in src.get("columns", {}).items()
            ],
        }
        nodes_out.append(node)
        seen_ids.add(uid)

    # Process model nodes
    for uid, node in raw_nodes.items():
        if node.get("resource_type") not in ("model", "seed", "snapshot"):
            continue
        name = node.get("name", _short_name(uid))
        schema = node.get("schema", "")
        layer = _node_layer(name, node.get("resource_type", "model"), schema)
        columns = list(node.get("columns", {}).keys())
        n = {
            "id": uid,
            "name": name,
            "label": name,
            "layer": layer,
            "resource_type": node.get("resource_type", "model"),
            "schema": schema,
            "description": node.get("description", ""),
            "columns": columns,
            "column_details": [
                {
                    "name": k,
                    "description": v.get("description", "") if isinstance(v, dict) else "",
                    "data_type": v.get("data_type", "") if isinstance(v, dict) else "",
                }
                for k, v in node.get("columns", {}).items()
            ],
            "raw_code": node.get("raw_code", ""),
            "compiled_code": node.get("compiled_code", ""),
            "path": node.get("path", ""),
        }
        nodes_out.append(n)
        seen_ids.add(uid)

        # Edges from depends_on
        for dep_uid in node.get("depends_on", {}).get("nodes", []):
            edges_out.append({"from": dep_uid, "to": uid, "column_mappings": []})

    # Remove edges where source/target not in graph
    edges_out = [e for e in edges_out if e["from"] in seen_ids and e["to"] in seen_ids]

    return {"nodes": nodes_out, "edges": edges_out, "source": "manifest"}


def _build_demo_graph() -> dict:
    """Fallback demo graph when no manifest is available."""
    nodes = [
        {"id": "src_postgres", "name": "PostgreSQL", "label": "PostgreSQL", "layer": "source",
         "columns": ["id", "created_at", "customer_id", "total_amount", "status"],
         "column_details": [
             {"name": "id", "description": "Primary key", "data_type": "integer"},
             {"name": "created_at", "description": "Order creation time", "data_type": "timestamp"},
             {"name": "customer_id", "description": "FK to customers", "data_type": "integer"},
             {"name": "total_amount", "description": "Order total in USD", "data_type": "numeric"},
             {"name": "status", "description": "Order status", "data_type": "text"},
         ]},
        {"id": "raw_orders", "name": "raw_orders", "label": "raw_orders", "layer": "raw",
         "schema": "raw", "columns": ["id", "created_at", "customer_id", "total_amount", "status"],
         "column_details": [{"name": c, "description": "", "data_type": ""} for c in ["id", "created_at", "customer_id", "total_amount", "status"]]},
        {"id": "stg_orders", "name": "stg_orders", "label": "stg_orders", "layer": "staging",
         "schema": "staging", "columns": ["order_key", "customer_id", "total_amount", "status", "order_date"],
         "column_details": [{"name": c, "description": "", "data_type": ""} for c in ["order_key", "customer_id", "total_amount", "status", "order_date"]]},
        {"id": "fct_orders", "name": "fct_orders", "label": "fct_orders", "layer": "mart",
         "schema": "marts", "columns": ["order_date", "total_revenue", "order_count"],
         "column_details": [{"name": c, "description": "", "data_type": ""} for c in ["order_date", "total_revenue", "order_count"]]},
    ]
    edges = [
        {"from": "src_postgres", "to": "raw_orders",  "column_mappings": []},
        {"from": "raw_orders",   "to": "stg_orders",  "column_mappings": [
            {"source_col": "id",           "dest_col": "order_key",     "transform": "alias"},
            {"source_col": "customer_id",  "dest_col": "customer_id",   "transform": "passthrough"},
            {"source_col": "total_amount", "dest_col": "total_amount",  "transform": "passthrough"},
        ]},
        {"from": "stg_orders",   "to": "fct_orders",  "column_mappings": [
            {"source_col": "total_amount", "dest_col": "total_revenue",  "transform": "SUM()"},
            {"source_col": "order_date",   "dest_col": "order_date",     "transform": "passthrough"},
        ]},
    ]
    return {"nodes": nodes, "edges": edges, "source": "demo"}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/graph")
def get_lineage_graph():
    manifest = _load_manifest()
    if manifest:
        graph = _build_graph_from_manifest(manifest)
    else:
        # Return an empty graph with guidance — not fake demo data
        graph = {"nodes": [], "edges": [], "source": "empty",
                 "message": "No dbt manifest.json found. Run 'dbt docs generate' to populate lineage."}

    # Enrich edges with column mappings where we have the data
    if manifest:
        raw_nodes = manifest.get("nodes", {})
        node_map = {n["id"]: n for n in graph["nodes"]}
        for edge in graph["edges"]:
            src_node = node_map.get(edge["from"])
            dst_uid = edge["to"]
            dst_manifest_node = raw_nodes.get(dst_uid)
            if src_node and dst_manifest_node:
                src_cols = src_node.get("columns", [])
                dst_cols = list(dst_manifest_node.get("columns", {}).keys())
                raw_code = dst_manifest_node.get("raw_code", "")
                edge["column_mappings"] = _infer_column_lineage(raw_code, src_cols, dst_cols)

    return graph


@router.get("/node/{node_name}")
def get_node_detail(node_name: str):
    """Get detailed info for a single node by short name."""
    manifest = _load_manifest()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not available")

    # Search nodes + sources
    all_entries = {**manifest.get("nodes", {}), **manifest.get("sources", {})}
    for uid, node in all_entries.items():
        if node.get("name") == node_name or _short_name(uid) == node_name:
            columns = node.get("columns", {})
            deps = node.get("depends_on", {}).get("nodes", [])
            # child_map for downstream
            child_map = manifest.get("child_map", {})
            downstream = [_short_name(c) for c in child_map.get(uid, []) if c.startswith("model.")]
            return {
                "id": uid,
                "name": node.get("name", node_name),
                "layer": _node_layer(node.get("name", ""), node.get("resource_type", "model"), node.get("schema", "")),
                "schema": node.get("schema", ""),
                "description": node.get("description", ""),
                "raw_code": node.get("raw_code", ""),
                "path": node.get("path", ""),
                "columns": [
                    {
                        "name": k,
                        "description": v.get("description", "") if isinstance(v, dict) else "",
                        "data_type": v.get("data_type", "") if isinstance(v, dict) else "",
                        "constraints": v.get("constraints", []) if isinstance(v, dict) else [],
                    }
                    for k, v in columns.items()
                ],
                "upstream": [_short_name(d) for d in deps],
                "downstream": downstream,
            }
    raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found in manifest")


@router.get("/columns/{node_name}")
def get_column_lineage(node_name: str):
    """Return column-level upstream lineage for a model."""
    manifest = _load_manifest()
    if not manifest:
        return {"node": node_name, "column_lineage": [], "source": "no_manifest",
                "message": "Run 'dbt docs generate' to enable column-level lineage."}

    raw_nodes = manifest.get("nodes", {})
    all_entries = {**raw_nodes, **manifest.get("sources", {})}

    # Find target node
    target_uid = None
    target_node = None
    for uid, node in all_entries.items():
        if node.get("name") == node_name or _short_name(uid) == node_name:
            target_uid = uid
            target_node = node
            break

    if not target_node:
        return {"node": node_name, "column_lineage": [], "source": "not_found"}

    dest_cols = list(target_node.get("columns", {}).keys())
    raw_code = target_node.get("raw_code", "")

    # Build column lineage from each upstream dependency
    column_lineage = []
    for dep_uid in target_node.get("depends_on", {}).get("nodes", []):
        src_node = all_entries.get(dep_uid)
        if not src_node:
            continue
        src_cols = list(src_node.get("columns", {}).keys())
        mappings = _infer_column_lineage(raw_code, src_cols, dest_cols)
        if mappings:
            column_lineage.append({
                "from_node": src_node.get("name", _short_name(dep_uid)),
                "to_node": node_name,
                "mappings": mappings,
            })

    return {
        "node": node_name,
        "column_lineage": column_lineage,
        "dest_columns": dest_cols,
        "source": "manifest",
    }
