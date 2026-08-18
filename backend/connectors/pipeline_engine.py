"""PipelineEngine — orchestrates extract → transform → load for a single pipeline run."""
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional

from .base import BaseSourceConnector, BaseDestinationConnector, IngestRecord, PipelineStats
from .registry import get_source, get_destination


class PipelineEngine:
    """
    Runs one ETL pipeline end-to-end.

    Usage:
        engine = PipelineEngine(pipeline_config)
        stats = engine.run()
    """

    def __init__(self, config: Dict, on_progress: Optional[Callable[[PipelineStats], None]] = None):
        self.config = config
        self.on_progress = on_progress
        self._stats = PipelineStats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> PipelineStats:
        self._stats = PipelineStats(status="running", last_run_at=datetime.now(timezone.utc).isoformat())
        t0 = time.time()

        try:
            source = get_source(
                self.config["source_connector_id"],
                self.config.get("source_config", {}),
            )
            destination = get_destination(
                self.config["destination_connector_id"],
                self.config.get("destination_config", {}),
            )

            schema_map = source.get_schema()
            for table_name, schema_cols in schema_map.items():
                destination.create_table_if_not_exists(
                    self.config.get("destination_table", table_name),
                    schema_cols,
                )

            batch: List[IngestRecord] = []
            batch_size = self.config.get("batch_size", 500)
            dest_table = self.config.get("destination_table", "records")

            for record in source.fetch_records():
                record = self._apply_transforms(record)
                batch.append(record)
                self._stats.records_ingested += 1

                if len(batch) >= batch_size:
                    loaded = destination.load_records(batch, dest_table)
                    self._stats.records_loaded += loaded
                    self._stats.records_failed += len(batch) - loaded
                    batch = []
                    self._emit_progress(t0)

            if batch:
                loaded = destination.load_records(batch, dest_table)
                self._stats.records_loaded += loaded
                self._stats.records_failed += len(batch) - loaded

            elapsed = time.time() - t0
            self._stats.events_per_minute = (
                round(self._stats.records_loaded / (elapsed / 60), 1) if elapsed > 0 else 0
            )
            self._stats.status = "success"

        except Exception as e:
            self._stats.status = "failed"
            self._stats.error_message = str(e)

        self._stats.records_transformed = self._stats.records_ingested
        self._emit_progress(t0)
        return self._stats

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_transforms(self, record: IngestRecord) -> IngestRecord:
        transforms = self.config.get("transforms", [])
        data = record.data

        for t in transforms:
            op = t.get("op")
            if op == "rename" and t.get("from") in data:
                data[t["to"]] = data.pop(t["from"])
            elif op == "drop" and t.get("column") in data:
                del data[t["column"]]
            elif op == "cast":
                col, target_type = t.get("column"), t.get("type")
                if col in data:
                    data[col] = _cast_value(data[col], target_type)
            elif op == "add_constant":
                data[t.get("column", "_const")] = t.get("value")

        return IngestRecord(
            data=data,
            source_table=record.source_table,
            ingested_at=record.ingested_at,
        )

    def _emit_progress(self, t0: float):
        if self.on_progress is None:
            return
        elapsed = time.time() - t0
        self._stats.events_per_minute = (
            round(self._stats.records_loaded / (elapsed / 60), 1) if elapsed > 0 else 0
        )
        try:
            self.on_progress(self._stats)
        except Exception:
            pass


def _cast_value(val: Any, target_type: str) -> Any:
    if val is None:
        return None
    try:
        if target_type == "integer":
            return int(float(val))
        if target_type == "float":
            return float(val)
        if target_type == "boolean":
            if isinstance(val, str):
                return val.lower() in ("true", "1", "yes")
            return bool(val)
        if target_type == "string":
            return str(val)
    except (ValueError, TypeError):
        pass
    return val
