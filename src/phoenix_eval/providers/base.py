"""Abstract model provider interface and mock testing provider for PHOENIX-EVAL."""

import abc
import contextlib
import json
import time
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from phoenix_eval.core.constants import BENCHMARK_SYSTEM_PROMPT
from phoenix_eval.core.exceptions import (
    ProviderExecutionError,
    ProviderTimeoutError,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.schemas.common import ExecutionStatus, TokenUsage
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.utils.hashing import compute_sha256
from phoenix_eval.utils.identifiers import generate_id
from phoenix_eval.utils.time import current_utc_timestamp

logger = get_logger("providers.base")


class MockBehavior(StrEnum):
    """Explicitly named behaviors for mock provider simulation."""

    VALID_MIGRATION = "valid_migration"
    UNSAFE_MIGRATION = "unsafe_migration"
    MALFORMED_RESPONSE = "malformed_response"


class ProviderPromptRequest(BaseModel):
    """Standardized prompt invocation request passed to a model provider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(..., description="ID of the benchmark task.")
    prompt: str = Field(
        ..., min_length=1, description="Complete prompt text presented to the model."
    )
    system_prompt: Optional[str] = Field(
        default=BENCHMARK_SYSTEM_PROMPT,
        description="Standardized benchmark system instruction bounding model behavior.",
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Sampling temperature.")
    max_tokens: int = Field(default=2048, ge=1, description="Maximum token generation limit.")
    timeout_seconds: float = Field(default=60.0, gt=0.0, description="Invocation timeout.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom prompt metadata.")


class BaseModelProvider(abc.ABC):
    """Abstract base contract for AI model providers evaluated by PHOENIX-EVAL."""

    def __init__(
        self,
        provider_name: str,
        model_identifier: str,
        model_version: str = "1.0",
        default_timeout: float = 60.0,
    ) -> None:
        self.provider_name = provider_name
        self.model_identifier = model_identifier
        self.model_version = model_version
        self.default_timeout = default_timeout

    @property
    def full_name(self) -> str:
        """Fully qualified model identifier."""
        return f"{self.provider_name}/{self.model_identifier}"

    @property
    def is_mock(self) -> bool:
        """Whether this provider is a mock/simulated provider (never makes external API calls)."""
        return False

    @abc.abstractmethod
    def generate_response(self, request: ProviderPromptRequest) -> ModelResponse:
        """Execute a prompt against the model provider and return a structured ModelResponse.

        Args:
            request: Standardized prompt request.

        Returns:
            Populated ModelResponse instance.

        Raises:
            ProviderTimeoutError: If execution exceeds timeout.
            ProviderError: If execution fails.
        """
        pass

    def validate_connection(self) -> bool:
        """Check provider connectivity and credential validity without running full benchmark prompts."""
        return True


class MockModelProvider(BaseModelProvider):
    """In-memory deterministic mock provider for testing and validation without API keys or costs."""

    def __init__(
        self,
        provider_name: str = "mock",
        model_identifier: str = "mock-model-v1",
        model_version: str = "1.0.0",
        canned_responses: Optional[dict[str, str]] = None,
        simulate_timeout: bool = False,
        simulate_error: bool = False,
        latency_seconds: float = 0.0,
        behavior: str | MockBehavior = MockBehavior.VALID_MIGRATION,
    ) -> None:
        super().__init__(
            provider_name=provider_name,
            model_identifier=model_identifier,
            model_version=model_version,
        )
        self.canned_responses = canned_responses or {}
        self.simulate_timeout = simulate_timeout
        self.simulate_error = simulate_error
        self.latency_seconds = latency_seconds
        self.behavior = behavior

    @property
    def is_mock(self) -> bool:
        return True

    def _resolve_task_and_scenario(self, request: ProviderPromptRequest) -> tuple[Any, Any]:
        """Attempt to resolve task and scenario models from request metadata or repositories."""
        task = request.metadata.get("task")
        scenario = request.metadata.get("scenario")
        if task is not None and scenario is not None:
            return task, scenario

        try:
            from phoenix_eval.core.paths import get_paths
            from phoenix_eval.data.repository import ScenarioRepository, TaskRepository

            paths = get_paths()
            task_repo = (
                TaskRepository(paths.generated_tasks_dir)
                if paths.generated_tasks_dir.is_dir()
                else None
            )
            seed_task_repo = TaskRepository(paths.tasks_dir)

            resolved_task = None
            if task_repo:
                with contextlib.suppress(Exception):
                    resolved_task = task_repo.load_task(request.task_id)
            if resolved_task is None:
                with contextlib.suppress(Exception):
                    resolved_task = seed_task_repo.load_task(request.task_id)

            if resolved_task:
                scen_repo = (
                    ScenarioRepository(paths.generated_scenarios_dir)
                    if paths.generated_scenarios_dir.is_dir()
                    else None
                )
                seed_scen_repo = ScenarioRepository(paths.scenarios_dir)
                scen_id = resolved_task.scenario_reference
                resolved_scen = None
                if scen_repo:
                    with contextlib.suppress(Exception):
                        resolved_scen = scen_repo.load_scenario(scen_id)
                if resolved_scen is None:
                    with contextlib.suppress(Exception):
                        resolved_scen = seed_scen_repo.load_scenario(scen_id)

                return resolved_task, resolved_scen
        except Exception:
            pass

        return task, scenario

    def _generate_synthetic_response(self, request: ProviderPromptRequest) -> str:
        """Produce a structured contract-compliant response based on configured mock behavior."""
        from phoenix_eval.providers.fixtures import (
            create_malformed_mock_response,
            create_unsafe_mock_response,
            create_valid_mock_response,
        )

        task, scenario = self._resolve_task_and_scenario(request)

        b_str = str(self.behavior).lower()
        if b_str in ("malformed", "syntax_error", "malformed_response"):
            return create_malformed_mock_response(task_id=request.task_id)

        if b_str in ("unsafe", "adversarial_unsafe", "unsafe_migration"):
            return create_unsafe_mock_response(task=task, scenario=scenario)

        if b_str == "refusal":
            from phoenix_eval.schemas.response_contract import (
                ModelDecision,
                ModelResponseContract,
            )

            contract = ModelResponseContract(
                task_id=request.task_id,
                decision=ModelDecision.MIGRATION_BLOCKED,
                identified_dependencies=[],
                compatibility_assessments=[],
                migration_plan=[],
                blocked_components=[],
                required_actions=["Perform exhaustive cryptographic discovery."],
                verification_results=[],
                evidence_references=[],
                assumptions=[],
                uncertainties=["High uncertainty regarding undocumented dependencies."],
                explanation=f"Cautious refusal: Cryptographic migration for {request.task_id} is deferred due to incomplete evidence.",
                contract_version="1.0.0",
            )
            return contract.model_dump_json(indent=2)

        # Default and valid_migration / valid_contract: generate full scenario-aware valid contract
        return create_valid_mock_response(task=task, scenario=scenario)

    def generate_response(self, request: ProviderPromptRequest) -> ModelResponse:
        """Simulate generation with deterministic output and token counting."""
        start_time = time.perf_counter()
        prompt_hash = compute_sha256(request.prompt)

        if self.simulate_timeout:
            raise ProviderTimeoutError(
                f"Mock provider simulated timeout after {request.timeout_seconds}s."
            )

        if self.simulate_error:
            raise ProviderExecutionError("Mock provider simulated unrecoverable execution failure.")

        if self.latency_seconds > 0.0:
            time.sleep(self.latency_seconds)

        # Check canned responses first, then behavior synthesizer
        if request.task_id in self.canned_responses:
            raw_text = self.canned_responses[request.task_id]
        else:
            raw_text = self._generate_synthetic_response(request)

        duration = time.perf_counter() - start_time
        prompt_tokens = max(1, len(request.prompt.split()))
        completion_tokens = max(1, len(raw_text.split()))

        # Parse JSON if output is valid JSON
        parsed_payload: Optional[dict[str, Any]] = None
        try:
            parsed_payload = json.loads(raw_text)
        except Exception:
            parsed_payload = {"mock_analysis": raw_text}

        return ModelResponse(
            response_id=generate_id("resp", self.model_identifier),
            task_id=request.task_id,
            model_provider=self.provider_name,
            model_identifier=self.model_identifier,
            model_version=self.model_version,
            returned_model_identifier=self.model_identifier,
            returned_model_version=self.model_version,
            provider_request_id=f"mock-req-{request.task_id}",
            raw_response=raw_text,
            parsed_response=parsed_payload,
            execution_status=ExecutionStatus.COMPLETED,
            token_usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated_cost_usd=0.0,
            ),
            execution_duration=duration,
            timestamp=current_utc_timestamp(),
            prompt_hash=prompt_hash,
            error_message=None,
            metadata={
                "simulated": True,
                "mock": True,
                "behavior": str(self.behavior),
                "temperature": request.temperature,
            },
        )
