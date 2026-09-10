"""PostgreSQL Source Connector — full load and incremental sync, returns pandas DataFrame."""
import logging

import pandas as pd
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


DEMO_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "orchestrai",
    "username": "admin",
    "password": "orchestrai_secret",
    "schema": "public",
}

BATCH_SIZE = 1000


class PostgreSQLSource:
    def __init__(self, config: dict):
        self.config = config
        self._conn = None

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=self.config["host"],
                port=int(self.config.get("port", 5432)),
                dbname=self.config["database"],
                user=self.config["username"],
                password=self.config["password"],
                sslmode=self.config.get("ssl_mode", "disable"),
                connect_timeout=10,
            )
        return self._conn

    def _close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> dict:
        import time
        t0 = time.time()
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                _r = cur.fetchone()
                version = _r[0] if _r else "unknown"
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
                    (self.config.get("schema", "public"),),
                )
                _r = cur.fetchone()
                table_count = _r[0] if _r else 0
            return {
                "success": True,
                "latency_ms": round((time.time() - t0) * 1000),
                "details": {"version": version, "table_count": table_count},
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self._close()

    def get_schema(self) -> dict[str, list[dict]]:
        schema_name = self.config.get("schema", "public")
        result = {}
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name, column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = %s ORDER BY table_name, ordinal_position",
                    (schema_name,),
                )
                for table_name, col_name, data_type, is_nullable in cur.fetchall():
                    result.setdefault(table_name, []).append({
                        "column": col_name,
                        "type": data_type,
                        "nullable": is_nullable == "YES",
                    })
        except Exception:
            pass
        finally:
            self._close()
        return result

    def get_row_count(self, table: str) -> int:
        schema_name = self.config.get("schema", "public")
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) FROM "{schema_name}"."{table}"')
                _r = cur.fetchone()
                return _r[0] if _r else 0
        except Exception:
            return 0
        finally:
            self._close()

    def extract(
        self,
        table: str,
        cursor_field: str | None = None,
        last_value: str | None = None,
    ) -> pd.DataFrame:
        """Extract table as DataFrame. Incremental if cursor_field+last_value given."""
        schema_name = self.config.get("schema", "public")
        chunks = []
        try:
            conn = self._get_conn()
            with conn.cursor(
                name=f"pg_src_{table}",
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                cur.itersize = BATCH_SIZE
                if cursor_field and last_value is not None:
                    cur.execute(
                        f'SELECT * FROM "{schema_name}"."{table}" '
                        f'WHERE "{cursor_field}" > %s ORDER BY "{cursor_field}" ASC',
                        (last_value,),
                    )
                else:
                    cur.execute(f'SELECT * FROM "{schema_name}"."{table}"')
                batch = cur.fetchmany(BATCH_SIZE)
                while batch:
                    chunks.append(pd.DataFrame([dict(r) for r in batch]))
                    batch = cur.fetchmany(BATCH_SIZE)
        except Exception as e:
            logger.error("[PostgreSQLSource] extract error on %s: %s", table, e)
        finally:
            self._close()
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

    def list_tables(self) -> list[str]:
        schema_name = self.config.get("schema", "public")
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name",
                    (schema_name,),
                )
                return [r[0] for r in cur.fetchall()]
        except Exception:
            return []
        finally:
            self._close()

# Backward compatibility alias
PostgreSQLSourceConnector = PostgreSQLSource
