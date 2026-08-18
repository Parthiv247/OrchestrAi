"""CSV / S3 Source Connector — local file, S3, or HTTP URL; CSV/Excel/Parquet; returns DataFrame."""
import os
from typing import Dict, List, Optional

import pandas as pd


DEMO_CONFIG = {
    "source_type": "url",
    "url": "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet",
    "file_format": "parquet",
    "row_limit": 50000,
}


class CSVSource:
    def __init__(self, config: Dict):
        self.config = config

    def _detect_format(self, path: str) -> str:
        fmt = self.config.get("file_format", "")
        if fmt:
            return fmt.lower()
        ext = path.split("?")[0].rsplit(".", 1)[-1].lower()
        mapping = {"csv": "csv", "xlsx": "excel", "xls": "excel",
                   "parquet": "parquet", "pq": "parquet"}
        return mapping.get(ext, "csv")

    def _read_df(self, path_or_bytes, fmt: str, row_limit: Optional[int] = None) -> pd.DataFrame:
        if fmt == "parquet":
            df = pd.read_parquet(path_or_bytes)
        elif fmt == "excel":
            df = pd.read_excel(path_or_bytes)
        else:
            df = pd.read_csv(path_or_bytes)
        if row_limit and len(df) > row_limit:
            df = df.head(row_limit)
        return df

    def _load_from_s3(self) -> pd.DataFrame:
        import boto3, io
        s3 = boto3.client(
            "s3",
            aws_access_key_id=self.config.get("aws_access_key_id"),
            aws_secret_access_key=self.config.get("aws_secret_access_key"),
            region_name=self.config.get("aws_region", "us-east-1"),
        )
        bucket = self.config["bucket"]
        key = self.config["key"]
        fmt = self._detect_format(key)
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
        return self._read_df(io.BytesIO(data), fmt, self.config.get("row_limit"))

    def _load_from_url(self) -> pd.DataFrame:
        import requests, io
        url = self.config["url"]
        fmt = self._detect_format(url)
        row_limit = self.config.get("row_limit")
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        data = resp.content
        return self._read_df(io.BytesIO(data), fmt, row_limit)

    def _load_from_local(self) -> pd.DataFrame:
        path = self.config["file_path"]
        fmt = self._detect_format(path)
        return self._read_df(path, fmt, self.config.get("row_limit"))

    def test_connection(self) -> Dict:
        import time
        t0 = time.time()
        try:
            df = self.extract()
            return {
                "success": True,
                "latency_ms": round((time.time() - t0) * 1000),
                "details": {"rows": len(df), "columns": list(df.columns)},
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract(self) -> pd.DataFrame:
        source_type = self.config.get("source_type", "local")
        if source_type == "s3":
            return self._load_from_s3()
        elif source_type == "url":
            return self._load_from_url()
        else:
            return self._load_from_local()

    def get_schema(self) -> List[Dict]:
        try:
            df = self.extract()
            if df.empty:
                return []
            return [
                {"column": col, "type": str(df[col].dtype), "nullable": bool(df[col].isna().any())}
                for col in df.columns
            ]
        except Exception:
            return []
