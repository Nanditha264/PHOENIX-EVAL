"""Centralized structured logging with sensitive data redaction for PHOENIX-EVAL."""

import logging
import logging.handlers
import os
import re
from pathlib import Path
from typing import Any, Optional

from phoenix_eval.core.paths import get_paths

_LOGGER_INITIALIZED = False

# Regex patterns for detecting potential credentials, API keys, tokens
SENSITIVE_PATTERNS = [
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|auth|credential)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"
    ),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI-style keys
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),  # Google API keys
    re.compile(r"anthropic-[a-zA-Z0-9-_]{20,}"),  # Anthropic keys
]


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs sensitive credentials, keys, and tokens from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._scrub_val(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._scrub_val(a) for a in record.args)
        return True

    def redact(self, text: str) -> str:
        scrubbed = text
        # Redact labeled credentials: "api_key: xyz...", "password=xyz..."
        scrubbed = re.sub(
            r"(?i)(api[_-]?key|secret|token|password|auth|credential)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?",
            r"\1: [REDACTED]",
            scrubbed,
        )
        # Redact known provider token formats
        scrubbed = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_API_KEY]", scrubbed)
        scrubbed = re.sub(r"AIza[0-9A-Za-z-_]{35}", "[REDACTED_API_KEY]", scrubbed)
        scrubbed = re.sub(r"anthropic-[a-zA-Z0-9-_]{20,}", "[REDACTED_API_KEY]", scrubbed)
        return scrubbed

    def _scrub_val(self, val: Any) -> Any:
        if isinstance(val, str):
            return self.redact(val)
        return val


class StructuredFormatter(logging.Formatter):
    """Standardized log formatter with ISO timestamp, component, and level."""

    def __init__(self, use_colors: bool = False) -> None:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
        super().__init__(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        # Standard base formatting
        formatted = super().format(record)
        return formatted


def configure_logging(
    level: str = "INFO",
    log_to_file: bool = True,
    log_file_path: Optional[Path] = None,
    console: bool = True,
) -> None:
    """Initialize centralized logging for PHOENIX-EVAL.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_to_file: Whether to attach rotating file logger.
        log_file_path: Path to log file (defaults to results/phoenix_eval.log).
        console: Whether to log to stdout.
    """
    global _LOGGER_INITIALIZED
    root_logger = logging.getLogger("phoenix_eval")

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on re-configuration
    root_logger.handlers.clear()

    redacting_filter = RedactingFilter()
    formatter = StructuredFormatter()

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(redacting_filter)
        root_logger.addHandler(console_handler)

    if log_to_file:
        if log_file_path is None:
            paths = get_paths()
            paths.results_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = paths.results_dir / "phoenix_eval.log"
        else:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redacting_filter)
        root_logger.addHandler(file_handler)

    _LOGGER_INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """Get a namespaced logger under the 'phoenix_eval' hierarchy.

    Args:
        name: Sub-module or component name (e.g. 'benchmark.registry').

    Returns:
        Configured logging.Logger instance.
    """
    global _LOGGER_INITIALIZED
    if not _LOGGER_INITIALIZED:
        # Auto-initialize with default settings if not explicitly called yet
        configure_logging(level=os.getenv("PHOENIX_LOG_LEVEL", "INFO"))

    if name.startswith("phoenix_eval"):
        return logging.getLogger(name)
    return logging.getLogger(f"phoenix_eval.{name}")
