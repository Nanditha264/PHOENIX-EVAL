"""Comprehensive unit tests for Phase 4 model provider adapters, retries, and credential security."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from phoenix_eval.core.exceptions import (
    ProviderAuthenticationError,
    ProviderEmptyResponseError,
    ProviderExecutionError,
    ProviderTimeoutError,
)
from phoenix_eval.core.security import redact_url, sanitize_headers, sanitize_text
from phoenix_eval.providers.base import MockModelProvider, ProviderPromptRequest
from phoenix_eval.providers.gemini_provider import GoogleGeminiProvider
from phoenix_eval.providers.openai_provider import OpenAICompatibleProvider
from phoenix_eval.schemas.common import ExecutionStatus

# -----------------------------------------------------------------------------
# Security & Sanitization Unit Tests
# -----------------------------------------------------------------------------


def test_sanitize_headers_masks_authorization() -> None:
    headers = {
        "Authorization": "Bearer sk-proj-1234567890abcdef123456",
        "Content-Type": "application/json",
        "x-api-key": "secret-api-key-value",
        "User-Agent": "TestClient/1.0",
    }
    sanitized = sanitize_headers(headers)
    assert sanitized["Authorization"] == "[REDACTED]"
    assert sanitized["x-api-key"] == "[REDACTED]"
    assert sanitized["Content-Type"] == "application/json"
    assert sanitized["User-Agent"] == "TestClient/1.0"


def test_redact_url_masks_credentials_and_query_keys() -> None:
    url1 = "https://user:supersecretpass@api.openai.com/v1/chat"
    assert "supersecretpass" not in redact_url(url1)
    assert "[REDACTED]" in redact_url(url1)

    url2 = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=AIzaSySecretKey123"
    assert "AIzaSySecretKey123" not in redact_url(url2)
    assert "key=%5BREDACTED%5D" in redact_url(url2) or "key=[REDACTED]" in redact_url(url2)


def test_sanitize_text_redacts_known_secrets_and_patterns() -> None:
    secret = "sk-live-secret-test-key-9999"
    msg = f"Failed to connect using key {secret} to provider."
    cleaned = sanitize_text(msg, known_secrets={secret})
    assert secret not in cleaned
    assert "[REDACTED]" in cleaned


# -----------------------------------------------------------------------------
# Mock Model Provider Tests
# -----------------------------------------------------------------------------


def test_mock_provider_deterministic_generation() -> None:
    provider = MockModelProvider(
        model_identifier="mock-model-v1",
        behavior="valid_contract",
    )
    req = ProviderPromptRequest(
        task_id="task-01",
        prompt="Explain cutover plan for task-01",
        temperature=0.0,
    )
    resp = provider.generate_response(req)
    assert resp.execution_status == ExecutionStatus.COMPLETED
    assert resp.model_provider == "mock"
    assert resp.token_usage is not None
    assert resp.token_usage.total_tokens > 0
    assert resp.metadata["mock"] is True
    assert resp.metadata["simulated"] is True
    assert provider.is_mock is True


def test_mock_provider_refusal_behavior() -> None:
    provider = MockModelProvider(
        model_identifier="mock-refusal-v1",
        behavior="refusal",
    )
    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")
    resp = provider.generate_response(req)
    assert "MIGRATION_BLOCKED" in resp.raw_response


def test_mock_provider_simulated_failures() -> None:
    timeout_provider = MockModelProvider(simulate_timeout=True)
    error_provider = MockModelProvider(simulate_error=True)
    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")

    with pytest.raises(ProviderTimeoutError, match="simulated timeout"):
        timeout_provider.generate_response(req)

    with pytest.raises(ProviderExecutionError, match="unrecoverable execution failure"):
        error_provider.generate_response(req)


# -----------------------------------------------------------------------------
# OpenAI-Compatible Provider Tests
# -----------------------------------------------------------------------------


def test_openai_provider_missing_api_key_raises_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_OPENAI_KEY", raising=False)
    provider = OpenAICompatibleProvider(api_key_env_var="TEST_OPENAI_KEY")
    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")

    with pytest.raises(ProviderAuthenticationError, match="Missing API key"):
        provider.generate_response(req)


@patch("httpx.Client.post")
def test_openai_provider_successful_response(
    mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-test-valid-key-1234567890")
    provider = OpenAICompatibleProvider(
        provider_name="openai",
        model_identifier="gpt-4o",
        api_key_env_var="TEST_OPENAI_KEY",
        pricing_per_1k_prompt=0.002,
        pricing_per_1k_completion=0.008,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {"content": '{"headline_decision": "MIGRATION_READY"}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        "model": "gpt-4o-2024-08-06",
    }
    mock_post.return_value = mock_resp

    req = ProviderPromptRequest(task_id="task-01", prompt="Test Prompt", temperature=0.0)
    response = provider.generate_response(req)

    assert response.execution_status == ExecutionStatus.COMPLETED
    assert response.raw_response == '{"headline_decision": "MIGRATION_READY"}'
    assert response.parsed_response == {"headline_decision": "MIGRATION_READY"}
    assert response.token_usage is not None
    assert response.token_usage.prompt_tokens == 100
    assert response.token_usage.completion_tokens == 50
    assert response.token_usage.total_tokens == 150
    assert response.token_usage.estimated_cost_usd is not None
    assert response.token_usage.estimated_cost_usd > 0.0
    assert response.returned_model_identifier == "gpt-4o-2024-08-06"


@patch("httpx.Client.post")
def test_openai_provider_authentication_failure_no_retry(
    mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-invalid-key-1234567890")
    provider = OpenAICompatibleProvider(api_key_env_var="TEST_OPENAI_KEY", max_retries=3)

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Incorrect API key provided"
    mock_post.return_value = mock_resp

    req = ProviderPromptRequest(task_id="task-01", prompt="Test")
    with pytest.raises(ProviderAuthenticationError, match="Authentication failed"):
        provider.generate_response(req)

    # Must fail immediately without retries on 401
    assert mock_post.call_count == 1


@patch("httpx.Client.post")
def test_openai_provider_rate_limit_retries_and_succeeds(
    mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-test-key-1234567890")
    provider = OpenAICompatibleProvider(
        api_key_env_var="TEST_OPENAI_KEY",
        max_retries=2,
        retry_delay_seconds=0.01,
    )

    # First call 429, second call 200
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Rate limit exceeded"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": "Success after backoff"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    mock_post.side_effect = [resp_429, resp_200]

    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")
    resp = provider.generate_response(req)

    assert resp.raw_response == "Success after backoff"
    assert mock_post.call_count == 2


@patch("httpx.Client.post")
def test_openai_provider_timeout_handling(
    mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-test-key-1234567890")
    provider = OpenAICompatibleProvider(
        api_key_env_var="TEST_OPENAI_KEY",
        max_retries=1,
        retry_delay_seconds=0.01,
    )
    mock_post.side_effect = httpx.TimeoutException("Read timed out")

    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")
    with pytest.raises(ProviderTimeoutError, match="timed out"):
        provider.generate_response(req)

    assert mock_post.call_count == 2  # 1 initial + 1 retry


@patch("httpx.Client.post")
def test_openai_provider_empty_response_handling(
    mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-test-key-1234567890")
    provider = OpenAICompatibleProvider(api_key_env_var="TEST_OPENAI_KEY", max_retries=0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": []}
    mock_post.return_value = mock_resp

    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")
    with pytest.raises(ProviderEmptyResponseError, match="empty"):
        provider.generate_response(req)


# -----------------------------------------------------------------------------
# Google Gemini Provider Tests
# -----------------------------------------------------------------------------


def test_gemini_provider_missing_key_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_GOOGLE_KEY", raising=False)
    provider = GoogleGeminiProvider(api_key_env_var="TEST_GOOGLE_KEY")
    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")

    with pytest.raises(ProviderAuthenticationError, match="Missing API key"):
        provider.generate_response(req)


@patch("httpx.Client.post")
def test_gemini_provider_successful_response(
    mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_GOOGLE_KEY", "AIzaSyTestKey12345678901234567890")
    provider = GoogleGeminiProvider(
        model_identifier="gemini-1.5-pro",
        api_key_env_var="TEST_GOOGLE_KEY",
        pricing_per_1k_prompt=0.001,
        pricing_per_1k_completion=0.004,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Gemini migration plan"}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 200,
            "candidatesTokenCount": 80,
            "totalTokenCount": 280,
        },
    }
    mock_post.return_value = mock_resp

    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")
    resp = provider.generate_response(req)

    assert resp.raw_response == "Gemini migration plan"
    assert resp.token_usage is not None
    assert resp.token_usage.prompt_tokens == 200
    assert resp.token_usage.completion_tokens == 80
    assert resp.token_usage.total_tokens == 280
    assert resp.token_usage.estimated_cost_usd is not None
