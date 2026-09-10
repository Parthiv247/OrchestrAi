from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConnectorType(Enum):
    SOURCE = "source"
    DESTINATION = "destination"


class ConnectionStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class ConnectorTestResult:
    status: ConnectionStatus
    message: str
    details: dict | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "message": self.message,
            "details": self.details or {},
        }


@dataclass
class IngestRecord:
    data: dict[str, Any]
    source_table: str
    ingested_at: str

    def to_dict(self) -> dict:
        return {
            "data": self.data,
            "source_table": self.source_table,
            "ingested_at": self.ingested_at,
        }


@dataclass
class PipelineStats:
    records_ingested: int = 0
    records_transformed: int = 0
    records_loaded: int = 0
    records_failed: int = 0
    events_per_minute: float = 0.0
    last_run_at: str | None = None
    status: str = "running"
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "records_ingested": self.records_ingested,
            "records_transformed": self.records_transformed,
            "records_loaded": self.records_loaded,
            "records_failed": self.records_failed,
            "events_per_minute": self.events_per_minute,
            "last_run_at": self.last_run_at,
            "status": self.status,
            "error_message": self.error_message,
        }


class BaseSourceConnector(ABC):
    connector_id: str = ""
    display_name: str = ""
    icon_url: str = ""

    @abstractmethod
    def test_connection(self) -> ConnectorTestResult:
        """Test if connection config is valid."""

    @abstractmethod
    def fetch_records(self) -> Iterator[IngestRecord]:
        """Fetch records from source — yields one record at a time."""

    @abstractmethod
    def get_schema(self) -> dict[str, list[dict]]:
        """Return schema: {table_name: [{column, type, nullable}]}"""

    @classmethod
    def get_config_schema(cls) -> list[dict]:
        """Return list of config field descriptors for UI rendering."""
        return []


class BaseDestinationConnector(ABC):
    connector_id: str = ""
    display_name: str = ""

    @abstractmethod
    def test_connection(self) -> ConnectorTestResult:
        pass

    @abstractmethod
    def load_records(self, records: list[IngestRecord], target_table: str) -> int:
        """Load records into destination. Returns count loaded."""

    @abstractmethod
    def create_table_if_not_exists(self, table_name: str, schema: list[dict]) -> bool:
        pass

    @classmethod
    def get_config_schema(cls) -> list[dict]:
        return []
