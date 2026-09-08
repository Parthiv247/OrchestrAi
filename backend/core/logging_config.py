"""
Structured JSON logging for OrchestrAI.

Usage in any module:
    from backend.core.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Pipeline triggered", pipeline_id=pipeline_id, records=1234)

Every log line is emitted as:
  {"ts":"2026-07-01T12:34:56.789Z","level":"INFO","logger":"backend.api.routes.pipelines",
   "msg":"Pipeline triggered","pipeline_id":"abc123","records":1234}

In dev mode (LOG_FORMAT=pretty), a human-readable format is used instead.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Append any extra fields set via logger.info("msg", extra={...})
        _SKIP = {
            "name", "msg", "args", "created", "filename", "funcName", "levelname",
            "levelno", "lineno", "module", "msecs", "pathname", "process",
            "processName", "relativeCreated", "stack_info", "thread", "threadName",
            "exc_info", "exc_text", "message",
        }
        for k, v in record.__dict__.items():
            if k not in _SKIP and not k.startswith("_"):
                try:
                    json.dumps(v)  # check serialisable
                    obj[k] = v
                except (TypeError, ValueError):
                    obj[k] = str(v)

        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(obj, ensure_ascii=False)


class _PrettyFormatter(logging.Formatter):
    """Human-readable coloured format for local development."""

    _COLORS = {
        "DEBUG": "\033[36m",    # cyan
        "INFO": "\033[32m",     # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[35m", # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        prefix = f"{color}{ts} {record.levelname:8s}{self._RESET}  {record.name}"
        msg = record.getMessage()
        line = f"{prefix}  {msg}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging() -> None:
    """
    Call once at application startup.
    Reads LOG_LEVEL (default INFO) and LOG_FORMAT (default json; 'pretty' in dev).
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json").lower()

    formatter: logging.Formatter
    if log_format == "pretty":
        formatter = _PrettyFormatter()
    else:
        formatter = _JsonFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level, logging.INFO))

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "chromadb", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a standard logger; call configure_logging() first at app startup."""
    return logging.getLogger(name)
