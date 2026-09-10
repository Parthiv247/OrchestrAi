"""Connector registry — maps connector_id strings to connector classes."""

from .destination.snowflake_loader import SnowflakeLoader
from .sources.csv_s3_source import CSVSource
from .sources.google_sheets_source import GoogleSheetsSource
from .sources.postgresql_source import PostgreSQLSource
from .sources.rest_api_source import RestAPISource

SOURCE_REGISTRY = {
    "rest_api": RestAPISource,
    "postgresql": PostgreSQLSource,
    "google_sheets": GoogleSheetsSource,
    "csv": CSVSource,
}


def get_source(connector_id: str, config: dict):
    cls = SOURCE_REGISTRY.get(connector_id)
    if cls is None:
        raise ValueError(f"Unknown source connector: {connector_id!r}")
    return cls(config)


def get_destination(connector_id: str, config: dict):
    if connector_id in ("snowflake", "postgresql", "snowflake_dest"):
        return SnowflakeLoader(config)
    raise ValueError(f"Unknown destination connector: {connector_id!r}")


def list_sources():
    return [
        {"id": k, "display_name": k.replace("_", " ").title()}
        for k in SOURCE_REGISTRY
    ]


def list_destinations():
    return [
        {"id": "snowflake", "display_name": "Snowflake / PostgreSQL"},
    ]
