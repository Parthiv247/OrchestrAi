"""Google Sheets Source Connector — service_account or public CSV export, returns DataFrame."""
import csv
import io
import logging
from typing import Dict, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# Public CSV fallback when Google Sheets export is unavailable
FALLBACK_CSV_URL = "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv"

DEMO_CONFIG = {
    "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
    "sheet_name": "Class Data",
    "auth_mode": "public",
    "fallback_csv_url": FALLBACK_CSV_URL,
}


class GoogleSheetsSource:
    def __init__(self, config: Dict):
        self.config = config
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service
        credentials_json = self.config.get("credentials_json", "")
        if not credentials_json:
            return None
        try:
            import json
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
            creds_dict = json.loads(credentials_json) if isinstance(credentials_json, str) else credentials_json
            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
            self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        except Exception as e:
            logger.warning("[GoogleSheetsSource] service_account init failed: %s", e)
        return self._service

    def _fetch_public_csv(self, spreadsheet_id: str, gid: str = "0") -> pd.DataFrame:
        """Try Google Sheets export URL, fall back to configured fallback_csv_url."""
        export_url = (
            "https://docs.google.com/spreadsheets/d/{}/export?format=csv&gid={}".format(
                spreadsheet_id, gid)
        )
        try:
            resp = requests.get(export_url, timeout=15, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 100:
                reader = csv.DictReader(io.StringIO(resp.text))
                rows = list(reader)
                if rows:
                    return pd.DataFrame(rows)
        except Exception:
            pass
        # Fallback to alternate public CSV
        fallback = self.config.get("fallback_csv_url", FALLBACK_CSV_URL)
        if fallback:
            resp2 = requests.get(fallback, timeout=30)
            resp2.raise_for_status()
            return pd.read_csv(io.StringIO(resp2.text))
        return pd.DataFrame()

    def _fetch_via_api(self, spreadsheet_id: str, sheet_name: str) -> pd.DataFrame:
        service = self._get_service()
        if service is None:
            raise RuntimeError("No service account credentials configured")
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=sheet_name)
            .execute()
        )
        values = result.get("values", [])
        if not values:
            return pd.DataFrame()
        headers = values[0]
        rows = [
            {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            for row in values[1:]
        ]
        return pd.DataFrame(rows)

    def test_connection(self) -> Dict:
        import time
        t0 = time.time()
        try:
            df = self.extract(self.config.get("sheet_name", "Sheet1"))
            return {
                "success": True,
                "latency_ms": round((time.time() - t0) * 1000),
                "details": {"rows": len(df), "columns": list(df.columns)},
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract(self, sheet_name: Optional[str] = None) -> pd.DataFrame:
        spreadsheet_id = self.config.get("spreadsheet_id", DEMO_CONFIG["spreadsheet_id"])
        auth_mode = self.config.get("auth_mode", "public")

        if auth_mode == "service_account" and self.config.get("credentials_json"):
            sheet = sheet_name or self.config.get("sheet_name", "Sheet1")
            return self._fetch_via_api(spreadsheet_id, sheet)
        return self._fetch_public_csv(spreadsheet_id, self.config.get("gid", "0"))

    def get_all_sheets(self) -> List[str]:
        service = self._get_service()
        if service is None:
            return [self.config.get("sheet_name", "Sheet1")]
        spreadsheet_id = self.config.get("spreadsheet_id", DEMO_CONFIG["spreadsheet_id"])
        try:
            meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            return [s["properties"]["title"] for s in meta.get("sheets", [])]
        except Exception:
            return []
