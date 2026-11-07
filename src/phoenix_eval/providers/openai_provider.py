"""OpenAI-compatible model provider adapter for PHOENIX-EVAL."""

import json
import os
import time
from typing import Any, Optional

import httpx

from phoenix_eval.core.constants import BENCHMARK_SYSTEM_PROMPT
from phoenix_eval.core.exceptions import (
    ProviderAuthenticationError,
    ProviderEmptyResponseError,
    ProviderExecutionError,
    ProviderInvalidRequestError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.security import redact_url, sanitize_text
from phoenix_eval.providers.base import BaseModelProvider, ProviderPromptRequest
from phoenix_eval.schemas.common import ExecutionStatus, TokenUsage
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.utils.hashing import compute_sha256
from phoenix_eval.utils.identifiers import generate_id
from phoenix_eval.utils.time import current_utc_timestamp

logger = get_logger("providers.openai")


class OpenAICompatibleProvider(BaseModelProvider):
    """Adapter for OpenAI and OpenAI-compatible API endpoints (vLLM, Groq, Together, Ollama, etc.)."""

    def __init__(
        self,
        provider_name: str = "openai",
        model_identifier: str = "gpt-4o",
        model_version: str = "default",
        api_key_env_var: str = "OPENAI_API_KEY",
        base_url: Optional[str] = None,
        default_timeout: float = 60.0,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        custom_headers: Optional[dict[str, str]] = None,
        pricing_per_1k_prompt: Optional[float] = None,
        pricing_per_1k_completion: Optional[float] = None,
    ) -> None:
        super().__init__(
            provider_name=provider_name,
            model_identifier=model_identifier,
            model_version=model_version,
            default_timeout=default_timeout,
        )
        self.api_key_env_var = api_key_env_var
        # Resolve base URL from param, env var OPENAI_BASE_URL, or default official OpenAI
        resolved_base = base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        self.base_url = resolved_base.rstrip("/")
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.custom_headers = custom_headers or {}
        self.pricing_per_1k_prompt = pricing_per_1k_prompt
        self.pricing_per_1k_completion = pricing_per_1k_completion

    @property
    def is_mock(self) -> bool:
        return False

    def _get_api_key(self) -> str:
        """Retrieve API key from configured environment variable with strict validation."""
        key = os.environ.get(self.api_key_env_var, "").strip()
        if not key:
            raise ProviderAuthenticationError(
                f"Missing API key for provider '{self.provider_name}'. "
                f"Environment variable '{self.api_key_env_var}' is unset or empty."
            )
        return key

    def validate_connection(self) -> bool:
        """Verify credential presence and endpoint syntax without executing full generation."""
        api_key = self._get_api_key()
        return bool(api_key and len(api_key) >= 8)

    def generate_response(self, request: ProviderPromptRequest) -> ModelResponse:
        """Send chat completion request to OpenAI-compatible endpoint with retries and backoff."""
        api_key = self._get_api_key()
        start_time = time.perf_counter()
        prompt_hash = compute_sha256(request.prompt)

        # Build payload
        sys_instruction = request.system_prompt or BENCHMARK_SYSTEM_PROMPT
        messages: list[dict[str, str]] = [
            {"role": "system", "content": sys_instruction},
            {"role": "user", "content": request.prompt},
        ]

        payload: dict[str, Any] = {
            "model": self.model_identifier,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # Build headers
        headers: dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "PHOENIX-EVAL-Benchmark/4.0",
            **self.custom_headers,
        }

        endpoint_url = f"{self.base_url}/chat/completions"
        timeout_val = request.timeout_seconds or self.default_timeout

        last_error: Optional[Exception] = None
        attempt = 0
        total_retries = self.max_retries

        while attempt <= total_retries:
            attempt += 1
            try:
                logger.debug(
                    "Calling %s (attempt %d/%d) model=%s",
                    redact_url(endpoint_url),
                    attempt,
                    total_retries + 1,
                    self.model_identifier,
                )

                with httpx.Client(timeout=timeout_val) as client:
                    resp = client.post(
                        endpoint_url,
                        headers=headers,
                        json=payload,
                    )

                # Process HTTP status
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        raise ProviderEmptyResponseError(
                            f"Provider '{self.provider_name}' returned empty choices=[] with no message content."
                        )

                    message = choices[0].get("message", {})
                    raw_content = message.get("content") or ""
                    if not raw_content.strip():
                        raise ProviderEmptyResponseError(
                            f"Provider '{self.provider_name}' returned empty or whitespace-only response."
                        )

                    duration = time.perf_counter() - start_time

                    # Extract usage metadata if present
                    usage_dict = data.get("usage", {})
                    prompt_tokens = usage_dict.get("prompt_tokens")
                    completion_tokens = usage_dict.get("completion_tokens")
                    total_tokens = usage_dict.get("total_tokens")

                    token_usage: Optional[TokenUsage] = None
                    if prompt_tokens is not None and completion_tokens is not None:
                        cost: Optional[float] = None
                        if self.pricing_per_1k_prompt and self.pricing_per_1k_completion:
                            cost = round(
                                (prompt_tokens / 1000.0) * self.pricing_per_1k_prompt
                                + (completion_tokens / 1000.0) * self.pricing_per_1k_completion,
                                6,
                            )
                        token_usage = TokenUsage(
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens or (prompt_tokens + completion_tokens),
                            estimated_cost_usd=cost,
                        )

                    # Extract parsed JSON if structured
                    parsed_json: Optional[dict[str, Any]] = None
                    try:
                        parsed_json = json.loads(raw_content)
                    except Exception:
                        parsed_json = None

                    returned_model = data.get("model")
                    if not isinstance(returned_model, str):
                        returned_model = None

                    request_id = data.get("id")
                    if not isinstance(request_id, str):
                        request_id = None
                    if (
                        request_id is None
                        and hasattr(resp, "headers")
                        and isinstance(resp.headers, dict)
                    ):
                        h_id = resp.headers.get("x-request-id")
                        if isinstance(h_id, str):
                            request_id = h_id

                    return ModelResponse(
                        response_id=generate_id("resp", self.model_identifier),
                        task_id=request.task_id,
                        model_provider=self.provider_name,
                        model_identifier=self.model_identifier,
                        model_version=self.model_version,
                        returned_model_identifier=returned_model,
                        returned_model_version=None,
                        provider_request_id=request_id,
                        raw_response=raw_content,
                        parsed_response=parsed_json,
                        execution_status=ExecutionStatus.COMPLETED,
                        token_usage=token_usage,
                        execution_duration=round(duration, 4),
                        timestamp=current_utc_timestamp(),
                        prompt_hash=prompt_hash,
                        error_message=None,
                        metadata={
                            "simulated": False,
                            "mock": False,
                            "provider_type": "openai_compatible",
                            "base_url": redact_url(self.base_url),
                            "finish_reason": choices[0].get("finish_reason"),
                            "returned_model": returned_model,
                            "request_id": request_id,
                            "attempt": attempt,
                        },
                    )

                # Handle specific HTTP error status codes
                if resp.status_code in (401, 403):
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    raise ProviderAuthenticationError(
                        f"Authentication failed for {self.provider_name} (HTTP {resp.status_code}): {err_msg[:200]}"
                    )

                if resp.status_code == 400:
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    raise ProviderInvalidRequestError(
                        f"Invalid request rejected by {self.provider_name} (HTTP 400): {err_msg[:200]}"
                    )

                if resp.status_code == 429:
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    last_error = ProviderRateLimitError(
                        f"Rate limit exceeded for {self.provider_name} (HTTP 429): {err_msg[:200]}"
                    )

                elif resp.status_code >= 500:
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    last_error = ProviderServerError(
                        f"Server error from {self.provider_name} (HTTP {resp.status_code}): {err_msg[:200]}"
                    )
                else:
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    last_error = ProviderExecutionError(
                        f"Unexpected HTTP {resp.status_code} from {self.provider_name}: {err_msg[:200]}"
                    )

            except httpx.TimeoutException:
                last_error = ProviderTimeoutError(
                    f"Request to {redact_url(endpoint_url)} timed out after {timeout_val}s."
                )
            except httpx.NetworkError as exc:
                last_error = ProviderNetworkError(
                    f"Network error connecting to {redact_url(endpoint_url)}: {exc}"
                )
            except (
                ProviderAuthenticationError,
                ProviderInvalidRequestError,
                ProviderEmptyResponseError,
            ):
                # Non-retryable errors fail immediately
                raise
            except Exception as exc:
                last_error = ProviderExecutionError(
                    f"Unexpected error invoking {self.provider_name}: {exc}"
                )

            # If we reached here, a retryable error occurred
            if attempt <= total_retries:
                backoff = self.retry_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Retryable failure on %s (attempt %d/%d): %s. Backing off for %.2fs...",
                    self.model_identifier,
                    attempt,
                    total_retries + 1,
                    last_error,
                    backoff,
                )
                time.sleep(backoff)

        # All retries exhausted
        if last_error:
            raise last_error
        raise ProviderExecutionError(
            f"Failed to generate response from {self.provider_name} after {attempt} attempts."
        )
