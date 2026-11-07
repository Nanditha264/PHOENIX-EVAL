"""Unit tests for centralized configuration management."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from phoenix_eval.core.config import Settings, get_settings, reset_settings
from phoenix_eval.core.exceptions import ConfigurationError


def test_default_configuration_loads_cleanly() -> None:
    """Verify that settings initialize cleanly with defaults and no API keys required."""
    reset_settings()
    settings = get_settings()

    assert settings.app_name == "PHOENIX-EVAL"
    assert settings.environment == "development"
    assert settings.log_level in {"DEBUG", "INFO", "WARNING", "ERROR"}
    assert settings.random_seed == 42
    assert settings.request_timeout > 0
    assert settings.max_retries >= 0
    assert settings.output_format == "json"
    assert settings.providers.default_provider == "mock"
    assert settings.providers.openai_api_key is None
    assert settings.providers.anthropic_api_key is None
    assert settings.providers.google_api_key is None


def test_environment_variable_overrides() -> None:
    """Verify that environment variables with PHOENIX_ prefix override defaults."""
    env_vars = {
        "PHOENIX_ENVIRONMENT": "testing",
        "PHOENIX_LOG_LEVEL": "DEBUG",
        "PHOENIX_RANDOM_SEED": "1337",
        "PHOENIX_REQUEST_TIMEOUT": "120.5",
        "PHOENIX_MAX_RETRIES": "5",
        "PHOENIX_OUTPUT_FORMAT": "jsonl",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        reset_settings()
        settings = get_settings()

        assert settings.environment == "testing"
        assert settings.log_level == "DEBUG"
        assert settings.random_seed == 1337
        assert settings.request_timeout == 120.5
        assert settings.max_retries == 5
        assert settings.output_format == "jsonl"


def test_invalid_log_level_raises_error() -> None:
    """Verify that invalid log levels are rejected."""
    with patch.dict(os.environ, {"PHOENIX_LOG_LEVEL": "INVALID_LEVEL"}, clear=False):
        reset_settings()
        with pytest.raises((ConfigurationError, ValidationError)):
            get_settings()


def test_invalid_timeout_raises_error() -> None:
    """Verify that non-positive timeouts are rejected."""
    with patch.dict(os.environ, {"PHOENIX_REQUEST_TIMEOUT": "-10.0"}, clear=False):
        reset_settings()
        with pytest.raises((ConfigurationError, ValidationError)):
            get_settings()


def test_api_keys_are_masked_in_repr() -> None:
    """Verify that SecretStr masks API keys to prevent accidental credential leakage in logs."""
    settings = Settings(
        providers={
            "openai_api_key": "sk-secret-test-key-1234567890",
            "anthropic_api_key": "anthropic-secret-key-abcdef",
        }
    )
    settings_str = str(settings)
    settings_repr = repr(settings)

    assert "sk-secret-test-key-1234567890" not in settings_str
    assert "sk-secret-test-key-1234567890" not in settings_repr
    assert "anthropic-secret-key-abcdef" not in settings_str
    assert "anthropic-secret-key-abcdef" not in settings_repr
    assert "**********" in settings_repr
