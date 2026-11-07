"""Security utilities for credential scrubbing and sensitive information masking."""

import re
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Common sensitive header names (case-insensitive)
SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "api-key",
    "proxy-authorization",
    "x-goog-api-key",
    "token",
}

# Common sensitive dictionary keys
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "access_token",
    "auth",
    "authorization",
    "private_key",
    "credentials",
}

# Regex to detect probable API keys (sk-..., AIzaSy...,Bearer ...)
_KEY_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}", re.IGNORECASE),
    re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),
]


def redact_url(url: str) -> str:
    """Mask credentials and sensitive query parameters in a URL.

    Example:
        https://api.example.com/v1?key=AIzaSy12345 -> https://api.example.com/v1?key=[REDACTED]
        https://user:password@example.com -> https://user:[REDACTED]@example.com
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # 1. Mask netloc username:password
        netloc = parsed.netloc
        if "@" in netloc:
            userinfo, host = netloc.split("@", 1)
            if ":" in userinfo:
                user, _ = userinfo.split(":", 1)
                netloc = f"{user}:[REDACTED]@{host}"
            else:
                netloc = f"[REDACTED]@{host}"

        # 2. Mask query params like 'key', 'api_key', 'token'
        query = parsed.query
        if query:
            params = parse_qs(query, keep_blank_values=True)
            redacted_params: dict[str, list[str]] = {}
            for k, vals in params.items():
                if k.lower() in SENSITIVE_KEYS or "key" in k.lower() or "token" in k.lower():
                    redacted_params[k] = ["[REDACTED]"]
                else:
                    redacted_params[k] = vals
            query = urlencode(redacted_params, doseq=True)

        return urlunparse(
            (parsed.scheme, netloc, parsed.path, parsed.params, query, parsed.fragment)
        )
    except Exception:
        # Fallback regex redaction if URL parsing fails
        return re.sub(r"(key|token|api_key)=[^&\s]+", r"\1=[REDACTED]", url, flags=re.IGNORECASE)


def sanitize_text(text: str, known_secrets: Optional[set[str]] = None) -> str:
    """Mask known secrets and API key patterns from an arbitrary string."""
    if not text:
        return ""

    sanitized = text

    # Redact known secrets explicitly
    if known_secrets:
        for secret in known_secrets:
            if secret and len(secret) >= 4:
                sanitized = sanitized.replace(secret, "[REDACTED]")

    # Redact common key patterns
    for pattern in _KEY_PATTERNS:
        sanitized = pattern.sub("[REDACTED_API_KEY]", sanitized)

    return sanitized


def sanitize_dict(data: dict[str, Any], known_secrets: Optional[set[str]] = None) -> dict[str, Any]:
    """Recursively mask sensitive keys and values in a dictionary."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        k_lower = str(key).lower()
        if k_lower in SENSITIVE_KEYS or any(
            s in k_lower for s in ("api_key", "secret", "password", "token")
        ):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, known_secrets=known_secrets)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, known_secrets=known_secrets)
                if isinstance(item, dict)
                else (
                    sanitize_text(str(item), known_secrets=known_secrets)
                    if isinstance(item, str)
                    else item
                )
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = sanitize_text(value, known_secrets=known_secrets)
        else:
            result[key] = value
    return result


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of HTTP headers with sensitive authentication headers masked."""
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value
    return sanitized
