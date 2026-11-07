"""Deterministic SHA-256 hashing utilities for benchmark artifacts."""

import hashlib
import json
from pathlib import Path
from typing import Any, Optional


def compute_sha256(content: str | bytes) -> str:
    """Compute standard SHA-256 hex digest for given string or bytes."""
    hasher = hashlib.sha256()
    if isinstance(content, str):
        hasher.update(content.encode("utf-8"))
    else:
        hasher.update(content)
    return hasher.hexdigest()


def compute_dict_hash(data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash for a dictionary with sorted keys."""
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return compute_sha256(serialized)


def compute_full_input_hash(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> str:
    """Compute deterministic SHA-256 hash covering the complete model input and generation parameters."""
    payload = {
        "max_tokens": max_tokens,
        "prompt": prompt,
        "system_prompt": system_prompt or "",
        "temperature": temperature,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return compute_sha256(serialized)


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hex digest for file content using chunked reading."""
    if not path.is_file():
        raise FileNotFoundError(f"Cannot compute hash: file not found at {path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()
