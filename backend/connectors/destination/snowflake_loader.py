"""Snowflake Destination Loader — with PostgreSQL fallback when no Snowflake creds."""
import logging
import os
import uuid
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)


def _use_fallback() -> bool:
    return not os.environ.get("SNOWFLAKE_ACCOUNT", "")


# ─────────────────────────────────────────────────────────────────────────────
# Credential-driven helpers (UI/connector field names: account/user/password/
# warehouse/database/schema/role). Used by the ETL engine + connector test so a
# pipeline can load to a REAL Snowflake using saved-connection or .env creds.
# ─────────────────────────────────────────────────────────────────────────────

def _sf_connect(creds: dict):
    """Open a Snowflake connection from a credentials dict (UI or .env shape)."""
    import snowflake.connector
    kwargs = dict(
        account=creds.get("account") or os.environ.get("SNOWFLAKE_ACCOUNT", ""),
        user=creds.get("user") or creds.get("username") or os.environ.get("SNOWFLAKE_USER", ""),
        password=creds.get("password") or os.environ.get("SNOWFLAKE_PASSWORD", ""),
        warehouse=creds.get("warehouse") or os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=creds.get("database") or creds.get("dbname") or os.environ.get("SNOWFLAKE_DB", ""),
        schema=creds.get("schema") or creds.get("sf_schema") or "PUBLIC",
    )
    role = creds.get("role") or os.environ.get("SNOWFLAKE_ROLE", "")
    if role:
        kwargs["role"] = role
    return snowflake.connector.connect(**kwargs)


def has_snowflake_creds(creds: dict | None) -> bool:
    """True when we have enough to attempt a real Snowflake connection."""
    creds = creds or {}
    account = creds.get("account") or os.environ.get("SNOWFLAKE_ACCOUNT", "")
    return bool(account)


def test_snowflake(creds: dict):
    """Live connection test. Returns (status, message) matching _test_connector."""
    try:
        conn = _sf_connect(creds)
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_DATABASE()")
        version, user, db = cur.fetchone()
        conn.close()
        return "connected", f"Snowflake {version} — user {user}, db {db}"
    except Exception as e:
        return "error", str(e)[:200]


def load_to_snowflake(creds: dict, table: str, columns: list[str], rows: list,
                      mode: str = "full_refresh"):
    """
    Bulk-load rows into Snowflake via write_pandas (PUT + COPY INTO under the hood).
    mode 'full_refresh' replaces the table; otherwise appends. Auto-creates the
    table if missing. Returns (rows_written, message).
    """
    from snowflake.connector.pandas_tools import write_pandas
    df = pd.DataFrame(rows, columns=columns)
    df.columns = [c.upper() for c in df.columns]
    schema = (creds.get("schema") or creds.get("sf_schema") or "PUBLIC").upper()
    database = (creds.get("database") or creds.get("dbname")
                or os.environ.get("SNOWFLAKE_DB", "")).upper()
    conn = _sf_connect(creds)
    try:
        conn.cursor().execute('CREATE SCHEMA IF NOT EXISTS "{}"'.format(schema.replace('"', '""')))
        success, _nchunks, nrows, _ = write_pandas(
            conn, df, table_name=table.upper(), schema=schema,
            database=database or None,
            auto_create_table=True,
            overwrite=(mode == "full_refresh"),
            quote_identifiers=False,
        )
        return (nrows if success else 0), ("loaded" if success else "write_pandas reported failure")
    finally:
        conn.close()


class SnowflakeLoader:
    """
    Loads DataFrames into Snowflake.
    Falls back to a local PostgreSQL schema called 'snowflake_dest' when
    SNOWFLAKE_ACCOUNT is not set in environment.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._sf_conn = None
        self._pg_conn = None

    # ─── Connection helpers ────────────────────────────────────────────────────

    def _get_snowflake(self):
        if self._sf_conn is not None:
            return self._sf_conn
        import snowflake.connector
        self._sf_conn = snowflake.connector.connect(
            account=self.config.get("account") or os.environ["SNOWFLAKE_ACCOUNT"],
            user=self.config.get("username") or os.environ["SNOWFLAKE_USER"],
            password=self.config.get("password") or os.environ["SNOWFLAKE_PASSWORD"],
            database=self.config.get("database") or os.environ.get("SNOWFLAKE_DB", "ORCHESTRAI"),
            schema=self.config.get("sf_schema", "RAW"),
            warehouse=self.config.get("warehouse") or os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        )
        return self._sf_conn

    def _get_postgres(self):
        if self._pg_conn is not None and not self._pg_conn.closed:
            return self._pg_conn
        import psycopg2
        self._pg_conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", 5432)),
            dbname=os.environ.get("POSTGRES_DB", "orchestrai"),
            user=os.environ.get("POSTGRES_USER", "admin"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
        )
        self._pg_conn.autocommit = False
        return self._pg_conn

    # ─── Schema helpers ────────────────────────────────────────────────────────

    def create_schema_if_not_exists(self, schema: str = "RAW"):
        if _use_fallback():
            pg = self._get_postgres()
            with pg.cursor() as cur:
                cur.execute('CREATE SCHEMA IF NOT EXISTS snowflake_dest')
            pg.commit()
        else:
            sf = self._get_snowflake()
            sf.cursor().execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    def _pg_schema(self) -> str:
        return "snowflake_dest"

    def _pg_qualified(self, table_name: str) -> str:
        return f'"snowflake_dest"."{table_name.lower()}"'

    # ─── Table creation ────────────────────────────────────────────────────────

    def create_table_from_dataframe(self, df: pd.DataFrame, table_name: str, schema: str = "RAW"):
        if _use_fallback():
            self._pg_create_table(df, table_name)
        else:
            self._sf_create_table(df, table_name, schema)

    def _pg_type(self, dtype) -> str:
        s = str(dtype).lower()
        if "int" in s:
            return "BIGINT"
        if "float" in s or "double" in s:
            return "DOUBLE PRECISION"
        if "bool" in s:
            return "BOOLEAN"
        if "datetime" in s or "timestamp" in s:
            return "TIMESTAMPTZ"
        return "TEXT"

    def _pg_create_table(self, df: pd.DataFrame, table_name: str):
        pg = self._get_postgres()
        cols = ", ".join(
            f'"{c}" {self._pg_type(df[c].dtype)}' for c in df.columns
        )
        ddl = f'CREATE TABLE IF NOT EXISTS {self._pg_qualified(table_name)} ({cols}, "_SOURCE" TEXT, "_INGESTED_AT" TIMESTAMPTZ, "_RUN_ID" TEXT)'
        with pg.cursor() as cur:
            cur.execute(ddl)
        pg.commit()

    def _sf_create_table(self, df: pd.DataFrame, table_name: str, schema: str):
        sf = self._get_snowflake()
        sf.cursor().execute(
            "CREATE TABLE IF NOT EXISTS {}.{} ({}, _SOURCE VARCHAR, _INGESTED_AT TIMESTAMPTZ, _RUN_ID VARCHAR)".format(
                schema, table_name.upper(),
                ", ".join(f'"{c.upper()}" VARCHAR' for c in df.columns),
            )
        )

    # ─── Write methods ─────────────────────────────────────────────────────────

    def _add_metadata(self, df: pd.DataFrame, source: str, run_id: str) -> pd.DataFrame:
        out = df.copy()
        out["_SOURCE"] = source
        out["_INGESTED_AT"] = datetime.now(timezone.utc).isoformat()
        out["_RUN_ID"] = run_id
        return out

    def table_exists(self, table_name: str, schema: str = "RAW") -> bool:
        if _use_fallback():
            pg = self._get_postgres()
            with pg.cursor() as cur:
                cur.execute(
                    "SELECT to_regclass(%s)",
                    (f'"snowflake_dest"."{table_name.lower()}"',),
                )
                _r = cur.fetchone()
                return _r is not None and _r[0] is not None
        else:
            sf = self._get_snowflake()
            cur = sf.cursor()
            cur.execute(f"SHOW TABLES LIKE '{table_name.upper()}' IN SCHEMA {schema}")
            return cur.fetchone() is not None

    def get_row_count(self, table_name: str, schema: str = "RAW") -> int:
        try:
            if _use_fallback():
                pg = self._get_postgres()
                with pg.cursor() as cur:
                    cur.execute(f'SELECT COUNT(*) FROM {self._pg_qualified(table_name)}')
                    _r = cur.fetchone()
                    return _r[0] if _r else 0
            else:
                sf = self._get_snowflake()
                cur = sf.cursor()
                cur.execute(f"SELECT COUNT(*) FROM {schema}.{table_name.upper()}")
                _r = cur.fetchone()
                return _r[0] if _r else 0
        except Exception:
            return 0

    def append(self, df: pd.DataFrame, table_name: str, schema: str = "RAW",
                source: str = "unknown", run_id: str | None = None) -> int:
        if df.empty:
            return 0
        run_id = run_id or str(uuid.uuid4())
        df = self._add_metadata(df, source, run_id)
        if _use_fallback():
            return self._pg_insert(df, table_name)
        return self._sf_write(df, table_name, schema)

    def upsert(self, df: pd.DataFrame, table_name: str, primary_key: str,
               schema: str = "RAW", source: str = "unknown", run_id: str | None = None) -> int:
        if df.empty:
            return 0
        run_id = run_id or str(uuid.uuid4())
        df = self._add_metadata(df, source, run_id)
        if _use_fallback():
            return self._pg_upsert(df, table_name, primary_key)
        return self._sf_merge(df, table_name, primary_key, schema)

    def _pg_insert(self, df: pd.DataFrame, table_name: str) -> int:
        import psycopg2.extras
        pg = self._get_postgres()
        cols = list(df.columns)
        col_str = ", ".join(f'"{c}"' for c in cols)
        rows = [tuple(row) for row in df.itertuples(index=False, name=None)]
        qualified = self._pg_qualified(table_name)
        try:
            with pg.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    f'INSERT INTO {qualified} ({col_str}) VALUES %s',
                    rows,
                )
            pg.commit()
            return len(rows)
        except Exception as e:
            pg.rollback()
            logger.error("[SnowflakeLoader] pg_insert error: %s", e)
            return 0

    def _pg_upsert(self, df: pd.DataFrame, table_name: str, primary_key: str) -> int:
        import psycopg2.extras
        pg = self._get_postgres()
        cols = list(df.columns)
        col_str = ", ".join(f'"{c}"' for c in cols)
        update_str = ", ".join(
            f'"{c}" = EXCLUDED."{c}"' for c in cols if c != primary_key
        )
        qualified = self._pg_qualified(table_name)
        sql = f'INSERT INTO {qualified} ({col_str}) VALUES %s ON CONFLICT ("{primary_key}") DO UPDATE SET {update_str}'
        rows = [tuple(row) for row in df.itertuples(index=False, name=None)]
        try:
            with pg.cursor() as cur:
                psycopg2.extras.execute_values(cur, sql, rows)
            pg.commit()
            return len(rows)
        except Exception as e:
            pg.rollback()
            logger.error("[SnowflakeLoader] pg_upsert error: %s", e)
            return 0

    def _sf_write(self, df: pd.DataFrame, table_name: str, schema: str) -> int:
        from snowflake.connector.pandas_tools import write_pandas
        sf = self._get_snowflake()
        df.columns = [c.upper() for c in df.columns]
        success, _, nrows, _ = write_pandas(
            sf, df, table_name.upper(), schema=schema,
            database=self.config.get("database") or os.environ.get("SNOWFLAKE_DB", "ORCHESTRAI"),
            auto_create_table=True, overwrite=False,
        )
        return nrows if success else 0

    # Run metadata columns are excluded from change-detection (they change every run).
    _META_COLS = {"_SOURCE", "_INGESTED_AT", "_RUN_ID", "_ROW_HASH"}

    def _sf_merge(self, df: pd.DataFrame, table_name: str, primary_key: str, schema: str) -> int:
        """
        Hevo/Fivetran-style idempotent load: stage the batch (write_pandas = PUT +
        COPY INTO), then MERGE on the primary key. A row-content hash (over data
        columns, excluding run metadata) drives change detection so UNCHANGED rows
        are skipped. Returns the number of rows actually CHANGED (inserts + real
        updates); the full breakdown is stored on self.last_merge_stats.
        """
        from snowflake.connector.pandas_tools import write_pandas
        sf = self._get_snowflake()
        df.columns = [c.upper() for c in df.columns]
        pk = primary_key.upper()
        if pk not in df.columns:
            raise ValueError(f"primary_key '{primary_key}' not found in dataframe columns")

        # Dedupe within the batch — MERGE errors if many source rows match one target row.
        df = df.drop_duplicates(subset=[pk], keep="last")

        # Content hash over data columns only (so changing metadata won't fake an update).
        hash_cols = [c for c in df.columns if c not in self._META_COLS]
        df = self.add_surrogate_key(df, key_cols=hash_cols, key_name="_ROW_HASH")

        tbl = table_name.upper()
        stage = f"_STAGE_{tbl}"
        db = self.config.get("database") or os.environ.get("SNOWFLAKE_DB", "ORCHESTRAI")
        cur = sf.cursor()
        cur.execute(f"USE DATABASE {db}")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        # 1) COPY the batch into a fresh stage table (write_pandas does PUT + COPY INTO).
        cur.execute(f"DROP TABLE IF EXISTS {schema}.{stage}")
        write_pandas(sf, df, stage, schema=schema, database=db,
                     auto_create_table=True, overwrite=True)

        # 2) Ensure the target exists with the same structure (first run / older tables).
        cur.execute(f"CREATE TABLE IF NOT EXISTS {schema}.{tbl} LIKE {schema}.{stage}")
        cur.execute(f'ALTER TABLE {schema}.{tbl} ADD COLUMN IF NOT EXISTS "_ROW_HASH" VARCHAR')

        # 3) Count genuine inserts / updates BEFORE merging (for true "loaded" metric).
        cur.execute(
            f'SELECT COUNT(*) FROM {schema}.{stage} src LEFT JOIN {schema}.{tbl} tgt '
            f'ON tgt."{pk}" = src."{pk}" WHERE tgt."{pk}" IS NULL')
        _r = cur.fetchone(); inserts = int(_r[0]) if _r else 0
        cur.execute(
            f'SELECT COUNT(*) FROM {schema}.{stage} src JOIN {schema}.{tbl} tgt ON tgt."{pk}" = src."{pk}" '
            'WHERE COALESCE(tgt."_ROW_HASH", \'\') <> src."_ROW_HASH"')
        _r = cur.fetchone(); updates = int(_r[0]) if _r else 0

        # 4) MERGE — update ONLY when the content hash differs; insert new keys.
        cols = list(df.columns)
        update_cols = [c for c in cols if c != pk]
        upd = ", ".join(f'tgt."{c}" = src."{c}"' for c in update_cols) \
              or f'tgt."{pk}" = src."{pk}"'
        merge_sql = (
            'MERGE INTO {s}.{t} tgt USING {s}.{st} src ON tgt."{pk}" = src."{pk}" '
            'WHEN MATCHED AND COALESCE(tgt."_ROW_HASH", \'\') <> src."_ROW_HASH" THEN UPDATE SET {upd} '
            'WHEN NOT MATCHED THEN INSERT ({icols}) VALUES ({ivals})'
        ).format(
            s=schema, t=tbl, st=stage, pk=pk, upd=upd,
            icols=", ".join(f'"{c}"' for c in cols),
            ivals=", ".join(f'src."{c}"' for c in cols),
        )
        cur.execute(merge_sql)
        cur.execute(f"DROP TABLE IF EXISTS {schema}.{stage}")

        ingested = len(df)
        self.last_merge_stats = {
            "ingested": ingested, "inserts": inserts, "updates": updates,
            "unchanged": max(0, ingested - inserts - updates),
            "loaded": inserts + updates,
        }
        return inserts + updates

    @staticmethod
    def add_surrogate_key(df: pd.DataFrame, key_cols: list | None = None,
                          key_name: str = "_PK") -> pd.DataFrame:
        """
        Add a deterministic MD5 surrogate key from the given business columns
        (defaults to all columns). Same source row -> same key across runs, so the
        MERGE upsert stays idempotent. Use this when the source has no natural PK.
        """
        import hashlib
        cols = key_cols if key_cols else list(df.columns)
        out = df.copy()
        out[key_name] = out.apply(
            lambda r: hashlib.md5(
                "||".join("" if pd.isna(r[c]) else str(r[c]) for c in cols).encode("utf-8")
            ).hexdigest(),
            axis=1,
        )
        return out
