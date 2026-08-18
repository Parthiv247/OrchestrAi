"""REST API Source Connector — pagination, auth, nested JSON, returns pandas DataFrame."""
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


DEMO_CONFIG = {
    "url": "https://api.open-meteo.com/v1/forecast",
    "method": "GET",
    "auth_type": "no_auth",
    "query_params": {
        "latitude": "19.07",
        "longitude": "72.87",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Asia/Kolkata",
        "past_days": "90",
    },
    "data_root": "daily",
    "pagination_type": "none",
}


class RestAPISource:
    def __init__(self, config: Dict):
        self.config = config
        self.session = requests.Session()
        self._setup_auth()

    def _setup_auth(self):
        auth_type = self.config.get("auth_type", "no_auth")
        if auth_type == "basic_auth":
            self.session.auth = (
                self.config.get("basic_auth_user", ""),
                self.config.get("basic_auth_password", ""),
            )
        elif auth_type == "api_key":
            header_name = self.config.get("api_key_header", "X-API-Key")
            self.session.headers[header_name] = self.config.get("api_key_value", "")

    def _make_request(self, extra_params: Optional[Dict] = None, url: Optional[str] = None) -> Any:
        target = url or self.config["url"]
        method = self.config.get("method", "GET").upper()
        params = dict(self.config.get("query_params") or {})
        if extra_params:
            params.update(extra_params)
        body = self.config.get("body")
        if method == "GET":
            resp = self.session.get(target, params=params, timeout=30)
        else:
            resp = self.session.post(target, params=params, json=body, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _extract_node(self, response: Any, data_root: str) -> Any:
        if not data_root:
            return response
        node = response
        for part in data_root.strip().split("."):
            if part and isinstance(node, dict):
                node = node.get(part, [])
        return node

    def _to_rows(self, node: Any) -> List[Dict]:
        if isinstance(node, list):
            return [r if isinstance(r, dict) else {"value": r} for r in node]
        if isinstance(node, dict):
            keys = list(node.keys())
            if keys and all(isinstance(node[k], list) for k in keys):
                length = len(node[keys[0]])
                return [{k: node[k][i] for k in keys} for i in range(length)]
            return [node]
        return []

    def test_connection(self) -> Dict:
        t0 = time.time()
        try:
            resp = self._make_request()
            node = self._extract_node(resp, self.config.get("data_root", ""))
            rows = self._to_rows(node)
            return {
                "success": True,
                "latency_ms": round((time.time() - t0) * 1000),
                "details": {"sample_count": len(rows), "url": self.config.get("url", "")},
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract(self) -> pd.DataFrame:
        pagination_type = self.config.get("pagination_type", "none")
        data_root = self.config.get("data_root", "")
        all_rows: List[Dict] = []

        if pagination_type == "none":
            resp = self._make_request()
            all_rows = self._to_rows(self._extract_node(resp, data_root))

        elif pagination_type == "page_number":
            page = self.config.get("page_start", 1)
            page_param = self.config.get("page_query_param", "page")
            limit = self.config.get("limit_value", 100)
            while True:
                resp = self._make_request({page_param: page})
                rows = self._to_rows(self._extract_node(resp, data_root))
                if not rows:
                    break
                all_rows.extend(rows)
                if len(rows) < limit:
                    break
                page += 1

        elif pagination_type == "limit_offset":
            limit = self.config.get("limit_value", 100)
            offset = 0
            lp = self.config.get("limit_query_param", "limit")
            op = self.config.get("offset_query_param", "offset")
            while True:
                resp = self._make_request({lp: limit, op: offset})
                rows = self._to_rows(self._extract_node(resp, data_root))
                if not rows:
                    break
                all_rows.extend(rows)
                if len(rows) < limit:
                    break
                offset += limit

        elif pagination_type == "cursor":
            next_field = self.config.get("next_page_field", "next")
            next_url = None
            while True:
                resp = self._make_request(url=next_url)
                rows = self._to_rows(self._extract_node(resp, data_root))
                all_rows.extend(rows)
                next_url = resp.get(next_field) if isinstance(resp, dict) else None
                if not next_url or not rows:
                    break

        return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()

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
