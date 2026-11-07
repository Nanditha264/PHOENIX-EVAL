"""Unit tests for model provider interface contracts and mock provider."""

import pytest
from pydantic import ValidationError

from phoenix_eval.core.exceptions import ProviderExecutionError, ProviderTimeoutError
from phoenix_eval.providers.base import MockModelProvider, ProviderPromptRequest
from phoenix_eval.schemas.common import ExecutionStatus


def test_mock_provider_generation() -> None:
    """Verify that MockModelProvider responds deterministically with accurate metadata."""
    provider = MockModelProvider(
        provider_name="mock-provider",
        model_identifier="mock-v1",
        canned_responses={"task-01": "Deterministic plan for task-01"},
    )

    req = ProviderPromptRequest(
        task_id="task-01",
        prompt="Explain migration sequence for task-01",
        temperature=0.0,
        max_tokens=500,
    )

    resp = provider.generate_response(req)
    assert resp.model_provider == "mock-provider"
    assert resp.model_identifier == "mock-v1"
    assert resp.raw_response == "Deterministic plan for task-01"
    assert resp.execution_status == ExecutionStatus.COMPLETED
    assert resp.token_usage is not None
    assert resp.token_usage.total_tokens > 0
    assert resp.prompt_hash is not None


def test_mock_provider_timeout_simulation() -> None:
    """Verify that simulate_timeout raises ProviderTimeoutError."""
    provider = MockModelProvider(simulate_timeout=True)
    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")

    with pytest.raises(ProviderTimeoutError, match="simulated timeout"):
        provider.generate_response(req)


def test_mock_provider_error_simulation() -> None:
    """Verify that simulate_error raises ProviderExecutionError."""
    provider = MockModelProvider(simulate_error=True)
    req = ProviderPromptRequest(task_id="task-01", prompt="Prompt")

    with pytest.raises(ProviderExecutionError, match="unrecoverable execution failure"):
        provider.generate_response(req)


def test_provider_request_validation() -> None:
    """Verify that invalid temperature or max_tokens is rejected by Pydantic."""
    with pytest.raises(ValidationError):
        ProviderPromptRequest(
            task_id="task-01",
            prompt="Prompt",
            temperature=3.5,  # Exceeds max 2.0
        )

    with pytest.raises(ValidationError):
        ProviderPromptRequest(
            task_id="task-01",
            prompt="Prompt",
            max_tokens=-10,  # Negative tokens
        )
