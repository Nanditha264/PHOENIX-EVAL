"""Identifier generation and validation utilities for benchmark entities."""

import re
import uuid
from typing import Optional

from phoenix_eval.core.exceptions import SchemaValidationError

# Valid identifier pattern: starts with alphanumeric, contains letters, digits, underscores, hyphens, dots
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\.]{1,127}$")


def validate_identifier(identifier: str) -> bool:
    """Check if string is a valid PHOENIX-EVAL resource identifier."""
    if not isinstance(identifier, str):
        return False
    return bool(IDENTIFIER_PATTERN.match(identifier.strip()))


def ensure_valid_identifier(identifier: str, field_name: str = "identifier") -> str:
    """Validate identifier string and return stripped value, or raise SchemaValidationError."""
    if not isinstance(identifier, str) or not identifier.strip():
        raise SchemaValidationError(f"{field_name} must be a non-empty string.")

    cleaned = identifier.strip()
    if not IDENTIFIER_PATTERN.match(cleaned):
        raise SchemaValidationError(
            f"Invalid {field_name} '{identifier}'. Must match pattern: {IDENTIFIER_PATTERN.pattern}"
        )
    return cleaned


def generate_id(prefix: str, name_hint: Optional[str] = None) -> str:
    """Generate a unique resource identifier with a standard prefix.

    Examples:
        generate_id("task", "pqc-seq") -> "task-pqc-seq-4a8f9c12"
        generate_id("comp") -> "comp-e92a18fb"
    """
    cleaned_prefix = prefix.strip().lower()
    suffix = uuid.uuid4().hex[:8]

    if name_hint:
        clean_hint = re.sub(r"[^a-zA-Z0-9_-]", "-", name_hint.lower().strip())
        clean_hint = re.sub(r"-+", "-", clean_hint).strip("-")
        return f"{cleaned_prefix}-{clean_hint}-{suffix}"
    return f"{cleaned_prefix}-{suffix}"
