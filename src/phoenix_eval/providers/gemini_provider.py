"""Google Gemini model provider adapter for PHOENIX-EVAL using direct REST API."""

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

logger = get_logger("providers.gemini")


class GoogleGeminiProvider(BaseModelProvider):
    """Adapter for Google Gemini models via official Generative Language REST endpoints."""

    def __init__(
        self,
        provider_name: str = "google",
        model_identifier: str = "gemini-1.5-pro",
        model_version: str = "default",
        api_key_env_var: str = "GOOGLE_API_KEY",
        base_url: Optional[str] = None,
        default_timeout: float = 60.0,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
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
        self.base_url = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.pricing_per_1k_prompt = pricing_per_1k_prompt
        self.pricing_per_1k_completion = pricing_per_1k_completion

    @property
    def is_mock(self) -> bool:
        return False

    def _get_api_key(self) -> str:
        """Retrieve Google/Gemini API key with strict validation."""
        key = (
            os.environ.get(self.api_key_env_var, "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        )
        if not key:
            raise ProviderAuthenticationError(
                f"Missing API key for provider '{self.provider_name}'. "
                f"Environment variable '{self.api_key_env_var}' or 'GEMINI_API_KEY' is unset or empty."
            )
        return key

    def validate_connection(self) -> bool:
        """Check credential existence."""
        api_key = self._get_api_key()
        return bool(api_key and len(api_key) >= 8)

    def generate_response(self, request: ProviderPromptRequest) -> ModelResponse:
        """Execute prompt against Gemini generateContent REST endpoint with retries."""
        api_key = self._get_api_key()
        start_time = time.perf_counter()
        prompt_hash = compute_sha256(request.prompt)

        # Build payload
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": request.prompt}],
                }
            ],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }

        sys_instruction = request.system_prompt or BENCHMARK_SYSTEM_PROMPT
        payload["systemInstruction"] = {
            "parts": [{"text": sys_instruction}],
        }

        headers: dict[str, str] = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "PHOENIX-EVAL-Benchmark/4.0",
        }

        endpoint_url = f"{self.base_url}/models/{self.model_identifier}:generateContent"
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

                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise ProviderEmptyResponseError(
                            f"Gemini returned empty candidates list for {self.model_identifier}."
                        )

                    content_obj = candidates[0].get("content", {})
                    parts = content_obj.get("parts", [])
                    if not parts or not parts[0].get("text"):
                        raise ProviderEmptyResponseError(
                            f"Gemini returned candidate with empty text for {self.model_identifier}."
                        )

                    raw_content = parts[0]["text"]
                    duration = time.perf_counter() - start_time

                    # Extract usage metadata
                    usage = data.get("usageMetadata", {})
                    prompt_tokens = usage.get("promptTokenCount")
                    completion_tokens = usage.get("candidatesTokenCount")
                    total_tokens = usage.get("totalTokenCount")

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

                    # Extract parsed JSON if present
                    parsed_json: Optional[dict[str, Any]] = None
                    try:
                        parsed_json = json.loads(raw_content)
                    except Exception:
                        parsed_json = None

                    model_version_val = data.get("modelVersion")
                    if not isinstance(model_version_val, str):
                        model_version_val = None

                    req_id = None
                    if hasattr(resp, "headers") and isinstance(resp.headers, dict):
                        h_req = resp.headers.get("x-goog-request-id")
                        if isinstance(h_req, str):
                            req_id = h_req

                    return ModelResponse(
                        response_id=generate_id("resp", self.model_identifier),
                        task_id=request.task_id,
                        model_provider=self.provider_name,
                        model_identifier=self.model_identifier,
                        model_version=self.model_version,
                        returned_model_identifier=model_version_val or self.model_identifier,
                        returned_model_version=model_version_val,
                        provider_request_id=req_id,
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
                            "provider_type": "google_gemini",
                            "finish_reason": candidates[0].get("finishReason"),
                            "modelVersion": model_version_val,
                            "request_id": req_id,
                            "attempt": attempt,
                        },
                    )

                if resp.status_code in (401, 403):
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    raise ProviderAuthenticationError(
                        f"Authentication failed for Gemini (HTTP {resp.status_code}): {err_msg[:200]}"
                    )

                if resp.status_code == 400:
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    raise ProviderInvalidRequestError(
                        f"Invalid request rejected by Gemini (HTTP 400): {err_msg[:200]}"
                    )

                if resp.status_code == 429:
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    last_error = ProviderRateLimitError(
                        f"Rate limit exceeded for Gemini (HTTP 429): {err_msg[:200]}"
                    )

                elif resp.status_code >= 500:
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    last_error = ProviderServerError(
                        f"Server error from Gemini (HTTP {resp.status_code}): {err_msg[:200]}"
                    )
                else:
                    err_msg = sanitize_text(resp.text, known_secrets={api_key})
                    last_error = ProviderExecutionError(
                        f"Unexpected HTTP {resp.status_code} from Gemini: {err_msg[:200]}"
                    )

            except httpx.TimeoutException:
                last_error = ProviderTimeoutError(
                    f"Request to Gemini timed out after {timeout_val}s."
                )
            except httpx.NetworkError as exc:
                last_error = ProviderNetworkError(f"Network error connecting to Gemini: {exc}")
            except (
                ProviderAuthenticationError,
                ProviderInvalidRequestError,
                ProviderEmptyResponseError,
            ):
                raise
            except Exception as exc:
                last_error = ProviderExecutionError(f"Unexpected error invoking Gemini: {exc}")

            if attempt <= total_retries:
                backoff = self.retry_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Retryable failure on Gemini (attempt %d/%d): %s. Backing off for %.2fs...",
                    attempt,
                    total_retries + 1,
                    last_error,
                    backoff,
                )
                time.sleep(backoff)

        if last_error:
            raise last_error
        raise ProviderExecutionError(
            f"Failed to generate response from Gemini after {attempt} attempts."
        )
