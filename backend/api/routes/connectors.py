"""Connector management endpoints — catalog, saved connections, test, upload."""
import os
import re
import uuid
import json
import shutil
import psycopg2
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from ...core.limiter import limiter
from pydantic import BaseModel
from ...connectors.registry import get_source, get_destination, list_sources, list_destinations
from ...core.encryption import encrypt, decrypt, mask_dict
from ...core.db_utils import get_sync_conn

router = APIRouter()


# ── File upload (for CSV / file-upload connectors) ──────────────────────────────

# Persisted on a mounted volume so the backend container can read it back at run time.
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "data/uploads")


@router.post("/connectors/upload")
async def upload_connector_file(file: UploadFile = File(...)):
    """Save an uploaded data file and return a path the CSV connector can read."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # Sanitize the filename and prefix a short uuid to avoid collisions.
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(file.filename or "upload.csv"))
    stored = "{}_{}".format(uuid.uuid4().hex[:8], safe)
    dest = os.path.join(UPLOAD_DIR, stored)
    try:
        with open(dest, "wb") as out:
            shutil.copyfileobj(file.file, out)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Upload failed: {}".format(e))
    finally:
        await file.close()
    size = os.path.getsize(dest)
    fmt = "parquet" if safe.lower().endswith((".parquet", ".pq")) else \
          ("excel" if safe.lower().endswith((".xlsx", ".xls")) else "csv")
    return {
        "filename": safe,
        "file_path": dest,          # relative path; resolves in container (CWD /app) and locally
        "file_format": fmt,
        "size_bytes": size,
    }


# ── Connector Catalog ──────────────────────────────────────────────────────────

CONNECTOR_CATALOG = [
    # ── Databases
    {
        "id": "postgresql", "name": "PostgreSQL", "category": "Databases",
        "description": "Open-source relational database — production workloads, analytics.",
        "color": "#336791", "logo": "🐘",
        "fields": [
            {"key": "host",     "label": "Host",     "type": "text",     "placeholder": "localhost"},
            {"key": "port",     "label": "Port",     "type": "number",   "placeholder": "5432"},
            {"key": "database", "label": "Database", "type": "text",     "placeholder": "mydb"},
            {"key": "user",     "label": "Username", "type": "text",     "placeholder": "postgres"},
            {"key": "password", "label": "Password", "type": "password", "placeholder": "••••••"},
        ],
        "popular": True,
    },
    {
        "id": "mysql", "name": "MySQL", "category": "Databases",
        "description": "World's most popular open-source database.",
        "color": "#4479A1", "logo": "🐬",
        "fields": [
            {"key": "host",     "label": "Host",     "type": "text",     "placeholder": "localhost"},
            {"key": "port",     "label": "Port",     "type": "number",   "placeholder": "3306"},
            {"key": "database", "label": "Database", "type": "text",     "placeholder": "mydb"},
            {"key": "user",     "label": "Username", "type": "text",     "placeholder": "root"},
            {"key": "password", "label": "Password", "type": "password", "placeholder": "••••••"},
        ],
        "popular": True,
    },
    {
        "id": "mongodb", "name": "MongoDB", "category": "Databases",
        "description": "Document database for modern apps.",
        "color": "#47A248", "logo": "🍃",
        "fields": [
            {"key": "connection_string", "label": "Connection String", "type": "text", "placeholder": "mongodb://localhost:27017"},
            {"key": "database",          "label": "Database",          "type": "text", "placeholder": "mydb"},
        ],
    },
    {
        "id": "mssql", "name": "MS SQL Server", "category": "Databases",
        "description": "Microsoft's enterprise relational database.",
        "color": "#CC2927", "logo": "🪟",
        "fields": [
            {"key": "host",     "label": "Host",     "type": "text",     "placeholder": "localhost"},
            {"key": "port",     "label": "Port",     "type": "number",   "placeholder": "1433"},
            {"key": "database", "label": "Database", "type": "text",     "placeholder": "mydb"},
            {"key": "user",     "label": "Username", "type": "text",     "placeholder": "sa"},
            {"key": "password", "label": "Password", "type": "password", "placeholder": "••••••"},
        ],
    },
    {
        "id": "sqlite", "name": "SQLite", "category": "Databases",
        "description": "Lightweight embedded SQL database.",
        "color": "#0F80CC", "logo": "📦",
        "fields": [
            {"key": "file_path", "label": "File Path", "type": "text", "placeholder": "/data/mydb.sqlite"},
        ],
    },
    # ── Cloud Warehouses
    {
        "id": "snowflake", "name": "Snowflake", "category": "Cloud Warehouses",
        "description": "Cloud data platform — scalable warehouse built for analytics.",
        "color": "#29B5E8", "logo": "❄️",
        "fields": [
            {"key": "account",   "label": "Account",   "type": "text",     "placeholder": "xy12345.us-east-1"},
            {"key": "user",      "label": "Username",  "type": "text",     "placeholder": "MYUSER"},
            {"key": "password",  "label": "Password",  "type": "password", "placeholder": "••••••"},
            {"key": "warehouse", "label": "Warehouse", "type": "text",     "placeholder": "COMPUTE_WH"},
            {"key": "database",  "label": "Database",  "type": "text",     "placeholder": "MY_DB"},
            {"key": "schema",    "label": "Schema",    "type": "text",     "placeholder": "PUBLIC"},
        ],
        "popular": True,
    },
    {
        "id": "bigquery", "name": "BigQuery", "category": "Cloud Warehouses",
        "description": "Google's serverless, highly scalable data warehouse.",
        "color": "#4285F4", "logo": "🔷",
        "fields": [
            {"key": "project_id",       "label": "Project ID",     "type": "text",     "placeholder": "my-gcp-project"},
            {"key": "dataset_id",       "label": "Dataset",        "type": "text",     "placeholder": "my_dataset"},
            {"key": "credentials_json", "label": "Service Account JSON", "type": "textarea", "placeholder": "{\"type\": \"service_account\", ...}"},
        ],
        "popular": True,
    },
    {
        "id": "redshift", "name": "Amazon Redshift", "category": "Cloud Warehouses",
        "description": "Fully managed petabyte-scale data warehouse from AWS.",
        "color": "#8C4FFF", "logo": "🔴",
        "fields": [
            {"key": "host",     "label": "Cluster Endpoint", "type": "text",     "placeholder": "cluster.xxxx.us-east-1.redshift.amazonaws.com"},
            {"key": "port",     "label": "Port",             "type": "number",   "placeholder": "5439"},
            {"key": "database", "label": "Database",         "type": "text",     "placeholder": "dev"},
            {"key": "user",     "label": "Username",         "type": "text",     "placeholder": "awsuser"},
            {"key": "password", "label": "Password",         "type": "password", "placeholder": "••••••"},
        ],
    },
    {
        "id": "databricks", "name": "Databricks", "category": "Cloud Warehouses",
        "description": "Unified analytics platform built on Apache Spark.",
        "color": "#FF3621", "logo": "🧱",
        "fields": [
            {"key": "host",         "label": "Workspace Host", "type": "text",     "placeholder": "xxx.azuredatabricks.net"},
            {"key": "http_path",    "label": "HTTP Path",      "type": "text",     "placeholder": "/sql/1.0/warehouses/xxx"},
            {"key": "access_token", "label": "Access Token",   "type": "password", "placeholder": "dapi••••••"},
            {"key": "catalog",      "label": "Catalog",        "type": "text",     "placeholder": "hive_metastore"},
        ],
    },
    # ── Cloud Storage
    {
        "id": "s3", "name": "Amazon S3", "category": "Cloud Storage",
        "description": "Scalable object storage for data lakes and archives.",
        "color": "#FF9900", "logo": "🪣",
        "fields": [
            {"key": "bucket",            "label": "Bucket Name",        "type": "text",     "placeholder": "my-data-lake"},
            {"key": "region",            "label": "Region",             "type": "text",     "placeholder": "us-east-1"},
            {"key": "aws_access_key_id", "label": "Access Key ID",      "type": "text",     "placeholder": "AKIAIOSFODNN7EXAMPLE"},
            {"key": "aws_secret_key",    "label": "Secret Access Key",  "type": "password", "placeholder": "••••••"},
            {"key": "prefix",            "label": "Path Prefix",        "type": "text",     "placeholder": "data/raw/"},
        ],
        "popular": True,
    },
    {
        "id": "gcs", "name": "Google Cloud Storage", "category": "Cloud Storage",
        "description": "Unified object storage for developers and enterprises.",
        "color": "#34A853", "logo": "☁️",
        "fields": [
            {"key": "bucket",           "label": "Bucket",             "type": "text", "placeholder": "my-gcs-bucket"},
            {"key": "credentials_json", "label": "Service Account JSON", "type": "textarea", "placeholder": "{...}"},
        ],
    },
    {
        "id": "azure_blob", "name": "Azure Blob Storage", "category": "Cloud Storage",
        "description": "Microsoft's massively scalable object storage.",
        "color": "#0078D4", "logo": "💠",
        "fields": [
            {"key": "account_name",   "label": "Account Name",        "type": "text",     "placeholder": "mystorageaccount"},
            {"key": "account_key",    "label": "Account Key",         "type": "password", "placeholder": "••••••"},
            {"key": "container_name", "label": "Container",           "type": "text",     "placeholder": "mycontainer"},
        ],
    },
    # ── SaaS / APIs
    {
        "id": "rest_api", "name": "REST API", "category": "APIs & SaaS",
        "description": "Fetch data from any HTTP/REST endpoint with auth support.",
        "color": "#6366F1", "logo": "🔌",
        "fields": [
            {"key": "base_url",  "label": "Base URL",     "type": "text",     "placeholder": "https://api.example.com"},
            {"key": "auth_type", "label": "Auth Type",    "type": "select",   "options": ["None", "Bearer Token", "API Key", "Basic Auth"]},
            {"key": "token",     "label": "Token / Key",  "type": "password", "placeholder": "••••••"},
            {"key": "headers",   "label": "Extra Headers", "type": "textarea", "placeholder": "{\"X-Custom\": \"value\"}"},
        ],
        "popular": True,
    },
    {
        "id": "google_sheets", "name": "Google Sheets", "category": "APIs & SaaS",
        "description": "Sync data from Google Sheets spreadsheets.",
        "color": "#0F9D58", "logo": "📊",
        "fields": [
            {"key": "spreadsheet_id",   "label": "Spreadsheet ID",    "type": "text",     "placeholder": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"},
            {"key": "credentials_json", "label": "Service Account JSON", "type": "textarea", "placeholder": "{...}"},
        ],
        "popular": True,
    },
    {
        "id": "salesforce", "name": "Salesforce", "category": "APIs & SaaS",
        "description": "Sync CRM objects, leads, opportunities from Salesforce.",
        "color": "#00A1E0", "logo": "☁️",
        "fields": [
            {"key": "username",       "label": "Username",     "type": "text",     "placeholder": "user@company.com"},
            {"key": "password",       "label": "Password",     "type": "password", "placeholder": "••••••"},
            {"key": "security_token", "label": "Security Token", "type": "password", "placeholder": "••••••"},
            {"key": "domain",         "label": "Domain",       "type": "text",     "placeholder": "login (or test)"},
        ],
    },
    {
        "id": "stripe", "name": "Stripe", "category": "APIs & SaaS",
        "description": "Sync payments, subscriptions, invoices from Stripe.",
        "color": "#635BFF", "logo": "💳",
        "fields": [
            {"key": "secret_key", "label": "Secret Key", "type": "password", "placeholder": "sk_live_••••••"},
        ],
    },
    {
        "id": "hubspot", "name": "HubSpot", "category": "APIs & SaaS",
        "description": "Sync contacts, deals, and marketing data from HubSpot.",
        "color": "#FF7A59", "logo": "🔶",
        "fields": [
            {"key": "access_token", "label": "Private App Token", "type": "password", "placeholder": "pat-••••••"},
        ],
    },
    # ── Streaming / ETL
    {
        "id": "airflow", "name": "Apache Airflow", "category": "Pipeline & ETL",
        "description": "Trigger and monitor DAGs in your Airflow instance.",
        "color": "#017CEE", "logo": "🌀",
        "fields": [
            {"key": "base_url",  "label": "Airflow URL",  "type": "text",     "placeholder": "http://localhost:8080"},
            {"key": "username",  "label": "Username",     "type": "text",     "placeholder": "airflow"},
            {"key": "password",  "label": "Password",     "type": "password", "placeholder": "••••••"},
        ],
        "popular": True,
    },
    {
        "id": "kafka", "name": "Apache Kafka", "category": "Pipeline & ETL",
        "description": "Ingest real-time event streams from Kafka topics.",
        "color": "#231F20", "logo": "⚡",
        "fields": [
            {"key": "bootstrap_servers", "label": "Bootstrap Servers", "type": "text",     "placeholder": "localhost:9092"},
            {"key": "topic",             "label": "Topic",             "type": "text",     "placeholder": "my-topic"},
            {"key": "group_id",          "label": "Consumer Group",    "type": "text",     "placeholder": "orchestrai-group"},
        ],
    },
    {
        "id": "csv", "name": "CSV / File Upload", "category": "Files",
        "description": "Load data from local CSV or TSV files.",
        "color": "#10B981", "logo": "📄",
        "fields": [
            {"key": "file_path", "label": "File Path", "type": "text", "placeholder": "/data/customers.csv"},
            {"key": "delimiter", "label": "Delimiter", "type": "text", "placeholder": ","},
        ],
    },
]

CATALOG_BY_ID = {c["id"]: c for c in CONNECTOR_CATALOG}

# Brand domains for Brandfetch logo lookup (cdn.brandfetch.io/<domain>).
# Connectors with no single brand (rest_api, csv) intentionally omitted -> emoji fallback.
CONNECTOR_DOMAINS = {
    "postgresql":  "postgresql.org",
    "mysql":       "mysql.com",
    "mongodb":     "mongodb.com",
    "mssql":       "microsoft.com",
    "sqlite":      "sqlite.org",
    "snowflake":   "snowflake.com",
    "bigquery":    "cloud.google.com",
    "redshift":    "aws.amazon.com",
    "databricks":  "databricks.com",
    "s3":          "aws.amazon.com",
    "gcs":         "cloud.google.com",
    "azure_blob":  "azure.microsoft.com",
    "google_sheets": "google.com",
    "salesforce":  "salesforce.com",
    "stripe":      "stripe.com",
    "hubspot":     "hubspot.com",
    "airflow":     "airflow.apache.org",
    "kafka":       "kafka.apache.org",
}

# Explicit logo URLs that override the Brandfetch domain lookup for specific connectors.
CONNECTOR_LOGO_OVERRIDES = {
    "postgresql": "https://www.postgresql.org/media/img/about/press/elephant.png",
    "airflow":    "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/apache-airflow.png",
    "kafka":      "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/kafka.png",
    "csv":        "https://img.icons8.com/?size=100&id=rRfRwtbb6gFt&format=png&color=000000",
}


@router.get("/connectors/catalog")
def get_catalog():
    """Return the full connector catalog grouped by category."""
    grouped: Dict[str, List] = {}
    for c in CONNECTOR_CATALOG:
        cat = c["category"]
        if cat not in grouped:
            grouped[cat] = []
        # Don't expose internal field details in catalog listing
        grouped[cat].append({
            "id": c["id"],
            "name": c["name"],
            "category": c["category"],
            "description": c["description"],
            "color": c["color"],
            "logo": c["logo"],
            "domain": CONNECTOR_DOMAINS.get(c["id"], ""),
            "logo_url": CONNECTOR_LOGO_OVERRIDES.get(c["id"], ""),
            "popular": c.get("popular", False),
            "fields": c.get("fields", []),
        })
    return {"catalog": grouped, "total": len(CONNECTOR_CATALOG)}


@router.get("/connectors/catalog/{connector_id}")
def get_catalog_entry(connector_id: str):
    entry = CATALOG_BY_ID.get(connector_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_id}' not in catalog")
    return entry


# ── Saved Connections CRUD ─────────────────────────────────────────────────────

class SaveConnectionRequest(BaseModel):
    connector_id: str
    name: str                         # user-given label, e.g. "prod-postgres"
    credentials: Dict[str, Any]       # encrypted server-side
    notes: Optional[str] = ""


class UpdateConnectionRequest(BaseModel):
    name: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


def _ensure_connector_configs_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS connector_configs (
            id TEXT PRIMARY KEY,
            connector_id TEXT NOT NULL,
            name TEXT NOT NULL,
            encrypted_creds TEXT NOT NULL,
            status TEXT DEFAULT 'untested',
            notes TEXT DEFAULT '',
            last_tested_at TIMESTAMP,
            test_message TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()


def _row_to_dict(row) -> Dict:
    return {
        "id": row[0],
        "connector_id": row[1],
        "name": row[2],
        "status": row[4],
        "notes": row[5],
        "last_tested_at": row[6].isoformat() if row[6] else None,
        "test_message": row[7],
        "created_at": row[8].isoformat() if row[8] else None,
        "updated_at": row[9].isoformat() if row[9] else None,
        # Merge catalog metadata
        "connector_name": CATALOG_BY_ID.get(row[1], {}).get("name", row[1]),
        "connector_color": CATALOG_BY_ID.get(row[1], {}).get("color", "#6366F1"),
        "connector_logo": CATALOG_BY_ID.get(row[1], {}).get("logo", "🔌"),
        "connector_domain": CONNECTOR_DOMAINS.get(row[1], ""),
        "connector_logo_url": CONNECTOR_LOGO_OVERRIDES.get(row[1], ""),
        "connector_category": CATALOG_BY_ID.get(row[1], {}).get("category", ""),
    }


@router.get("/connectors/saved")
def list_saved_connections():
    try:
        conn = get_sync_conn()
        _ensure_connector_configs_table(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, connector_id, name, encrypted_creds, status, notes,
                   last_tested_at, test_message, created_at, updated_at
            FROM connector_configs ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        return {"connections": [_row_to_dict(r) for r in rows]}
    except Exception as e:
        return {"connections": [], "error": str(e)}


@router.post("/connectors/saved")
def create_saved_connection(body: SaveConnectionRequest):
    if body.connector_id not in CATALOG_BY_ID:
        raise HTTPException(status_code=400, detail=f"Unknown connector: {body.connector_id}")
    conn_id = str(uuid.uuid4())
    encrypted = encrypt(json.dumps(body.credentials))
    try:
        conn = get_sync_conn()
        _ensure_connector_configs_table(conn)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO connector_configs
              (id, connector_id, name, encrypted_creds, status, notes, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'untested', %s, NOW(), NOW())
        """, (conn_id, body.connector_id, body.name, encrypted, body.notes or ""))
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "id": conn_id,
        "connector_id": body.connector_id,
        "name": body.name,
        "status": "untested",
        "connector_name": CATALOG_BY_ID[body.connector_id]["name"],
        "connector_logo": CATALOG_BY_ID[body.connector_id]["logo"],
        "connector_domain": CONNECTOR_DOMAINS.get(body.connector_id, ""),
        "connector_logo_url": CONNECTOR_LOGO_OVERRIDES.get(body.connector_id, ""),
        "connector_color": CATALOG_BY_ID[body.connector_id]["color"],
        "connector_category": CATALOG_BY_ID[body.connector_id]["category"],
    }


@router.get("/connectors/saved/{connection_id}")
def get_saved_connection(connection_id: str):
    try:
        conn = get_sync_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, connector_id, name, encrypted_creds, status, notes,
                   last_tested_at, test_message, created_at, updated_at
            FROM connector_configs WHERE id = %s
        """, (connection_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Connection not found")
        result = _row_to_dict(row)
        # Decrypt and mask credentials for display
        try:
            raw_creds = json.loads(decrypt(row[3]))
            result["credentials_masked"] = mask_dict(raw_creds)
        except Exception:
            result["credentials_masked"] = {}
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/connectors/saved/{connection_id}")
def update_saved_connection(connection_id: str, body: UpdateConnectionRequest):
    try:
        conn = get_sync_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM connector_configs WHERE id = %s", (connection_id,))
        if not cur.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Connection not found")
        updates = ["updated_at = NOW()"]
        params = []
        if body.name is not None:
            updates.append("name = %s"); params.append(body.name)
        if body.credentials is not None:
            updates.append("encrypted_creds = %s"); params.append(encrypt(json.dumps(body.credentials)))
            updates.append("status = 'untested'")
        if body.notes is not None:
            updates.append("notes = %s"); params.append(body.notes)
        params.append(connection_id)
        cur.execute(f"UPDATE connector_configs SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
        conn.close()
        return {"message": "Updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/connectors/saved/{connection_id}")
def delete_saved_connection(connection_id: str):
    try:
        conn = get_sync_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM connector_configs WHERE id = %s", (connection_id,))
        conn.commit()
        conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connectors/saved/{connection_id}/test")
@limiter.limit("20/minute")
def test_saved_connection(request: Request, connection_id: str):
    """Attempt to connect using saved credentials. Returns success/failure."""
    try:
        conn = get_sync_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT connector_id, encrypted_creds FROM connector_configs WHERE id = %s
        """, (connection_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Connection not found")
        connector_id, encrypted_creds = row[0], row[1]
        creds = json.loads(decrypt(encrypted_creds))

        status, message = _test_connector(connector_id, creds)

        cur.execute("""
            UPDATE connector_configs
            SET status = %s, test_message = %s, last_tested_at = NOW(), updated_at = NOW()
            WHERE id = %s
        """, (status, message, connection_id))
        conn.commit()
        conn.close()
        return {"connection_id": connection_id, "status": status, "message": message}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _test_connector(connector_id: str, creds: Dict) -> tuple:
    """Try a lightweight connection test for each known connector type."""
    try:
        if connector_id == "postgresql":
            import psycopg2 as pg
            c = pg.connect(
                host=creds.get("host", "localhost"),
                port=int(creds.get("port", 5432)),
                dbname=creds.get("database", "postgres"),
                user=creds.get("user", "postgres"),
                password=creds.get("password", ""),
                connect_timeout=5,
            )
            c.close()
            return "connected", "Connection successful"
        elif connector_id == "mysql":
            import pymysql
            c = pymysql.connect(
                host=creds.get("host", "localhost"),
                port=int(creds.get("port", 3306)),
                database=creds.get("database", ""),
                user=creds.get("user", "root"),
                password=creds.get("password", ""),
                connect_timeout=5,
            )
            c.close()
            return "connected", "Connection successful"
        elif connector_id == "s3":
            import boto3
            s3 = boto3.client(
                "s3",
                region_name=creds.get("region", "us-east-1"),
                aws_access_key_id=creds.get("aws_access_key_id"),
                aws_secret_access_key=creds.get("aws_secret_key"),
            )
            s3.head_bucket(Bucket=creds.get("bucket", ""))
            return "connected", "Bucket accessible"
        elif connector_id == "rest_api":
            import httpx
            r = httpx.get(
                creds.get("base_url", ""),
                headers={"Authorization": f"Bearer {creds.get('token', '')}"} if creds.get("token") else {},
                timeout=5,
            )
            return "connected", f"HTTP {r.status_code} — endpoint reachable"
        elif connector_id == "airflow":
            import httpx
            url = creds.get("base_url", "http://localhost:8080")
            r = httpx.get(
                f"{url.rstrip('/')}/api/v1/health",
                auth=(creds.get("username", "airflow"), creds.get("password", "")),
                timeout=5,
            )
            if r.status_code == 200:
                return "connected", "Airflow health OK"
            return "error", f"HTTP {r.status_code}"
        elif connector_id == "snowflake":
            from ...connectors.destination.snowflake_loader import test_snowflake
            return test_snowflake(creds)
        elif connector_id == "csv":
            # A URL source — just confirm it's reachable.
            if creds.get("url"):
                import httpx
                r = httpx.get(creds["url"], timeout=10, follow_redirects=True)
                return (("connected", f"URL reachable (HTTP {r.status_code})")
                        if r.status_code < 400 else ("error", f"HTTP {r.status_code} — URL not reachable"))
            # A local file — verify the BACKEND can actually read it (not just the host).
            fp = creds.get("file_path", "")
            if not fp:
                return "error", "No file_path or url provided"
            if not os.path.exists(fp):
                return ("error",
                        f"File not reachable by the server at '{fp}'. Absolute host paths "
                        f"(e.g. /Users/...) aren't visible to the backend — use the “Upload a file” "
                        f"button, or place it under the project data/ folder and reference data/<name>.")
            try:
                import pandas as pd
                fmt = (creds.get("file_format") or "csv").lower()
                df = (pd.read_parquet(fp) if fmt == "parquet"
                      else pd.read_excel(fp, nrows=5) if fmt == "excel"
                      else pd.read_csv(fp, nrows=5))
                cols = ", ".join(map(str, list(df.columns)[:6]))
                return "connected", f"File readable — columns: {cols}"
            except Exception as e:
                return "error", f"File found but could not be read: {e}"
        else:
            # Generic: just mark as connected for connectors we can't actually test
            return "connected", f"{CATALOG_BY_ID.get(connector_id, {}).get('name', connector_id)} — credentials saved (live test not available)"
    except Exception as e:
        return "error", str(e)[:200]


# ── Pydantic models ────────────────────────────────────────────────────────────

class TestConnectionRequest(BaseModel):
    connector_type: str          # "source" | "destination"
    connector_id: str
    config: Dict[str, Any]


# ── Connector catalogue ────────────────────────────────────────────────────────

@router.get("/connectors/sources")
def get_source_connectors():
    return {"sources": list_sources()}


@router.get("/connectors/destinations")
def get_destination_connectors():
    return {"destinations": list_destinations()}


@router.post("/connectors/test")
def test_connection(body: TestConnectionRequest):
    try:
        if body.connector_type == "source":
            connector = get_source(body.connector_id, body.config)
        elif body.connector_type == "destination":
            connector = get_destination(body.connector_id, body.config)
        else:
            raise HTTPException(status_code=400, detail="connector_type must be 'source' or 'destination'")
        result = connector.test_connection()
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connectors/schema")
def get_connector_schema(body: TestConnectionRequest):
    """Return the schema (columns) discovered from a source connector."""
    try:
        connector = get_source(body.connector_id, body.config)
        schema = connector.get_schema()
        return {"schema": schema}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


