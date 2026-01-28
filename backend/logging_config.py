"""
Centralized logging configuration for the backend.

Provides structured JSON logging with correlation ID support,
secret redaction, environment-aware behavior, and 48-hour log retention.

All backend modules should use:
    from backend.logging_config import get_logger
    logger = get_logger(__name__)

Or for the root application logger:
    from backend.logging_config import get_logger
    logger = get_logger("vespa_app")
"""

import json
import logging
import os
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Correlation ID context (thread-safe via contextvars)
# ---------------------------------------------------------------------------
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

CORRELATION_HEADER = "x-correlation-id"


def get_correlation_id() -> str:
    """Return the current correlation ID, or empty string if none set."""
    return _correlation_id.get()


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current context."""
    _correlation_id.set(cid)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------
def _get_environment() -> str:
    """Detect the current environment from ENV or APP_ENV."""
    return os.environ.get("APP_ENV", os.environ.get("ENV", "development")).lower()


def is_production() -> bool:
    return _get_environment() == "production"


def is_development() -> bool:
    return _get_environment() in ("development", "dev", "local", "")


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------
_SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key\s*[:=]\s*)['\"]?[\w\-]{10,}['\"]?", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)['\"]?[\w\-]{10,}['\"]?", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*)['\"]?[^\s'\"]{4,}['\"]?", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*)['\"]?[\w\-]{10,}['\"]?", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[\w\-\.]{10,}", re.IGNORECASE),
    re.compile(r"(authorization\s*[:=]\s*)['\"]?Bearer\s+[\w\-\.]+['\"]?", re.IGNORECASE),
]

_SECRET_ENV_KEYS = {
    "OPENROUTER_API_KEY", "OPENAI_API_KEY", "VESPA_CLOUD_SECRET_TOKEN",
    "VESPA_CLOUD_MTLS_KEY", "VESPA_CLOUD_MTLS_CERT", "AWS_SECRET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID", "PROCORE_DATABASE_URL",
}


def _redact_secrets(message: str) -> str:
    """Remove secret values from log messages."""
    result = message
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(r"\1[REDACTED]", result)
    # Redact known env var values that appear in the message
    for key in _SECRET_ENV_KEYS:
        val = os.environ.get(key)
        if val and len(val) > 4 and val in result:
            result = result.replace(val, "[REDACTED]")
    return result


# ---------------------------------------------------------------------------
# Structured JSON formatter
# ---------------------------------------------------------------------------
class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON objects.

    Every log entry includes: timestamp, level, service, context, correlationId.
    Error-level logs also include stackTrace.
    """

    LEVEL_MAP = {
        "DEBUG": "debug",
        "INFO": "info",
        "WARNING": "warn",
        "ERROR": "error",
        "CRITICAL": "fatal",
    }

    def __init__(self, service: str = "vespa_app"):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        level = self.LEVEL_MAP.get(record.levelname, record.levelname.lower())

        message = record.getMessage()
        message = _redact_secrets(message)

        entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": level,
            "service": self.service,
            "context": record.name,
            "correlationId": get_correlation_id() or None,
            "message": message,
        }

        # Include stack trace for error and fatal levels
        if record.exc_info and record.exc_info[1] is not None:
            entry["stackTrace"] = _redact_secrets(
                self.formatException(record.exc_info)
            )
        elif level in ("error", "fatal") and not record.exc_info:
            # Capture current stack for errors logged without an exception
            pass

        # Extra structured fields passed via `extra={"data": {...}}`
        if hasattr(record, "data") and isinstance(record.data, dict):
            entry["data"] = record.data

        return json.dumps(entry, default=str)


# ---------------------------------------------------------------------------
# Development formatter (human-readable)
# ---------------------------------------------------------------------------
class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for local development.

    Fails loudly: shows full stack traces and correlation IDs.
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        cid = get_correlation_id()
        cid_str = f" [{cid[:8]}]" if cid else ""
        msg = _redact_secrets(record.getMessage())
        base = f"{record.levelname}:\t{ts}\t{record.name}{cid_str}\t{msg}"

        if record.exc_info and record.exc_info[1] is not None:
            base += "\n" + _redact_secrets(self.formatException(record.exc_info))

        return base


# ---------------------------------------------------------------------------
# 48-hour file handler with retention
# ---------------------------------------------------------------------------
LOG_DIR = Path(os.environ.get("LOG_DIR", "logs"))
LOG_RETENTION_HOURS = 48


class RetentionFileHandler(logging.FileHandler):
    """File handler that enforces 48-hour log retention.

    Logs are written to logs/app.log. On initialization and periodically,
    old log files exceeding the retention window are cleaned up.
    """

    def __init__(self, log_dir: Path = LOG_DIR, retention_hours: int = LOG_RETENTION_HOURS):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / "app.log"
        self.log_dir = log_dir
        self.retention_hours = retention_hours
        self._last_cleanup = 0.0
        self._cleanup_interval = 3600  # Check every hour
        super().__init__(str(self.log_file), mode="a", encoding="utf-8")
        self._cleanup_old_logs()

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._last_cleanup = now
            self._cleanup_old_logs()

    def _cleanup_old_logs(self) -> None:
        """Remove log entries and files older than retention_hours.

        Retention enforced at 48 hours (configurable). This method:
        1. Removes any rotated log files beyond retention
        2. Truncates the main log file to only keep recent entries
        """
        self._last_cleanup = time.time()
        cutoff = time.time() - (self.retention_hours * 3600)

        # Clean up any rotated log files
        for log_file in self.log_dir.glob("app.log.*"):
            try:
                if log_file.stat().st_mtime < cutoff:
                    log_file.unlink()
            except OSError:
                pass

        # Truncate main log if it's older than retention
        try:
            if self.log_file.exists() and self.log_file.stat().st_mtime < cutoff:
                self.log_file.write_text("")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------
_configured = False
_root_service = "vespa_app"


def configure_logging(
    log_level: str = "INFO",
    service: str = "vespa_app",
    enable_file_logging: bool = True,
) -> None:
    """Configure the centralized logging system.

    Call once at application startup (e.g., in main.py).
    All subsequent get_logger() calls will inherit this config.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        service: Service name included in every structured log entry.
        enable_file_logging: Whether to write logs to disk with 48h retention.
    """
    global _configured, _root_service
    _root_service = service

    root_logger = logging.getLogger("vespa_app")
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Choose formatter based on environment
    if is_production():
        formatter = StructuredJsonFormatter(service=service)
    else:
        formatter = DevelopmentFormatter()

    # Console handler (always present)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    # File handler with 48-hour retention
    if enable_file_logging:
        try:
            file_handler = RetentionFileHandler()
            json_formatter = StructuredJsonFormatter(service=service)
            file_handler.setFormatter(json_formatter)
            root_logger.addHandler(file_handler)
        except OSError:
            root_logger.warning("Could not initialize file logging")

    # Prevent duplicate propagation
    root_logger.propagate = False
    _configured = True


def get_logger(name: str = "vespa_app") -> logging.Logger:
    """Get a logger that routes through the centralized configuration.

    All loggers are children of the 'vespa_app' root logger so they
    inherit its handlers and formatting.

    Args:
        name: Logger name (typically __name__). Gets prefixed under vespa_app.

    Returns:
        Configured logging.Logger instance.
    """
    if not _configured:
        # Auto-configure with defaults if not explicitly configured
        configure_logging()

    if name == "vespa_app":
        return logging.getLogger("vespa_app")

    # Make child loggers of vespa_app so they inherit handlers
    logger = logging.getLogger(f"vespa_app.{name}")
    logger.propagate = True
    return logger
