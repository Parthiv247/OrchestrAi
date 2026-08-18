"""Secure Connection Manager — encrypts credentials with Fernet before storing in DB."""
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

import psycopg2
from cryptography.fernet import Fernet

_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("ENCRYPTION_KEY", "")
        if not key:
            raise RuntimeError(
                "ENCRYPTION_KEY not set. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode())
    return _fernet


def _get_db_conn():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        dbname=os.environ.get("POSTGRES_DB", "orchestrai"),
        user=os.environ.get("POSTGRES_USER", "admin"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )


class ConnectionManager:
    """
    Saves and retrieves connector credentials, encrypting them with Fernet.
    Credentials never leave the system in plaintext.
    """

    def save_connection(
        self,
        name: str,
        db_type: str,
        config: Dict,
        tenant_id: Optional[str] = None,
    ) -> str:
        import json
        conn_id = str(uuid.uuid4())
        fernet = _get_fernet()
        plaintext = json.dumps(config).encode()
        encrypted = fernet.encrypt(plaintext).decode()

        db = _get_db_conn()
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO data_connections
                        (id, tenant_id, name, db_type, config_encrypted, is_active, created_at)
                    VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        config_encrypted = EXCLUDED.config_encrypted,
                        db_type = EXCLUDED.db_type,
                        is_active = TRUE
                    """,
                    (conn_id, tenant_id, name, db_type, encrypted, datetime.now(timezone.utc)),
                )
            db.commit()
        finally:
            db.close()
        return conn_id

    def get_connection(self, name: str) -> Optional[Dict]:
        import json
        db = _get_db_conn()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT config_encrypted FROM data_connections WHERE name = %s AND is_active = TRUE",
                    (name,),
                )
                row = cur.fetchone()
        finally:
            db.close()
        if row is None:
            return None
        fernet = _get_fernet()
        return json.loads(fernet.decrypt(row[0].encode()).decode())

    def test_connection(self, db_type: str, config: Dict) -> Dict:
        import time
        t0 = time.time()
        try:
            if db_type == "postgresql":
                conn = psycopg2.connect(
                    host=config["host"],
                    port=int(config.get("port", 5432)),
                    dbname=config["database"],
                    user=config["username"],
                    password=config["password"],
                    connect_timeout=5,
                )
                with conn.cursor() as cur:
                    cur.execute("SELECT version()")
                    _r = cur.fetchone()
                    version = _r[0] if _r else "unknown"
                conn.close()
                return {"success": True, "latency_ms": round((time.time()-t0)*1000), "details": {"version": version}}

            elif db_type == "rest_api":
                import requests
                resp = requests.get(config["url"], timeout=10)
                resp.raise_for_status()
                return {"success": True, "latency_ms": round((time.time()-t0)*1000), "details": {"status": resp.status_code}}

            elif db_type in ("snowflake", "snowflake_dest"):
                import snowflake.connector
                con = snowflake.connector.connect(
                    account=config["account"],
                    user=config["username"],
                    password=config["password"],
                    database=config.get("database", ""),
                    schema=config.get("sf_schema", "PUBLIC"),
                    warehouse=config.get("warehouse", "COMPUTE_WH"),
                )
                cur = con.cursor()
                cur.execute("SELECT CURRENT_VERSION()")
                _r = cur.fetchone()
                version = _r[0] if _r else "unknown"
                con.close()
                return {"success": True, "latency_ms": round((time.time()-t0)*1000), "details": {"version": version}}

            else:
                return {"success": True, "latency_ms": 0, "details": {"note": "No live test for this type"}}

        except Exception as e:
            return {"success": False, "error": str(e), "latency_ms": round((time.time()-t0)*1000)}

    def list_connections(self) -> list:
        db = _get_db_conn()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT id, name, db_type, is_active, last_tested_at, last_test_status, created_at "
                    "FROM data_connections WHERE is_active = TRUE ORDER BY created_at DESC"
                )
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
        finally:
            db.close()
        return [dict(zip(cols, r)) for r in rows]


connection_manager = ConnectionManager()
