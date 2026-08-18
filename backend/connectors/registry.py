"""Connector registry — maps connector_id strings to connector classes."""
from typing import Dict, Type

from .sources.rest_api_source import RestAPISource
from .sources.postgresql_source import PostgreSQLSource
from .sources.google_sheets_source import GoogleSheetsSource
from .sources.csv_s3_source import CSVSource
from .destination.snowflake_loader import SnowflakeLoader


SOURCE_REGISTRY = {
    "rest_api": RestAPISource,
    "postgresql": PostgreSQLSource,
    "google_sheets": GoogleSheetsSource,
    "csv": CSVSource,
}


def get_source(connector_id: str, config: Dict):
    cls = SOURCE_REGISTRY.get(connector_id)
    if cls is None:
        raise ValueError("Unknown source connector: {!r}".format(connector_id))
    return cls(config)


def get_destination(connector_id: str, config: Dict):
    if connector_id in ("snowflake", "postgresql", "snowflake_dest"):
        return SnowflakeLoader(config)
    raise ValueError("Unknown destination connector: {!r}".format(connector_id))


def list_sources():
    return [
        {"id": k, "display_name": k.replace("_", " ").title()}
        for k in SOURCE_REGISTRY
    ]


def list_destinations():
    return [
        {"id": "snowflake", "display_name": "Snowflake / PostgreSQL"},
    ]
