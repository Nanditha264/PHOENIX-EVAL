"""Experiment Quality Control Smoke Test Runner for PHOENIX-EVAL Phase 6.

Validates provider integration, response contract parsing, evaluator isolation,
scoring engine, and safety gate enforcement across three canonical task archetypes:
1. Ordinary valid task (T09)
2. Unsafe migration task (T03)
3. Epistemic uncertainty / missing-evidence task (T04)
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from phoenix_eval.benchmark.prompt_builder import build_model_prompt
from phoenix_eval.core.constants import BENCHMARK_SYSTEM_PROMPT
from phoenix_eval.core.exceptions import (
    GroundTruthLeakageError,
    ProviderAuthenticationError,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.core.security import sanitize_text
from phoenix_eval.data.repository import GroundTruthRepository, ScenarioRepository, TaskRepository
from phoenix_eval.data.serialization import write_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.response_parser import parse_model_response
from phoenix_eval.providers.base import BaseModelProvider, ProviderPromptRequest
from phoenix_eval.providers.model_registry import ModelRegistry, get_model_registry
from phoenix_eval.utils.time import current_utc_timestamp

logger = get_logger("experiment.smoke_test")

CANONICAL_SMOKE_TASKS: list[dict[str, str]] = [
    {
        "task_id": "task-gen-t09-bank-02",
        "archetype": "ORDINARY_VALID",
        "description": "Ordinary valid migration with full compatibility and passing test evidence.",
    },
    {
        "task_id": "task-gen-t03-telco-01",
        "archetype": "UNSAFE_BLOCKER",
        "description": "Downstream incompatible consumer requiring migration cutover to be blocked.",
    },
    {
        "task_id": "task-gen-t04-bank-02",
        "archetype": "EPISTEMIC_UNCERTAINTY",
        "description": "Unknown external provider readiness requiring discovery under uncertainty.",
    },
]


class SmokeTaskResult(BaseModel):
    """Detailed audit outcome for a single smoke test task invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    archetype: str
    description: str
    prompt_sent: bool
    ground_truth_isolated: bool
    response_received: bool
    contract_valid: bool
    decision_reported: Optional[str] = None
    raw_score: float = 0.0
    effective_score: float = 0.0
    safety_gate_passed: bool = False
    critical_violations_count: int = 0
    violation_codes: list[str] = Field(default_factory=list)
    latency_seconds: float = 0.0
    error_message: Optional[str] = None


class SmokeTestReport(BaseModel):
    """Authoritative quality control audit report certifying provider readiness for benchmarking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    is_mock: bool
    status: str  # "PASSED", "FAILED", "AUTH_FAILED"
    timestamp: datetime = Field(default_factory=current_utc_timestamp)
    total_tasks: int = 3
    successful_requests: int = 0
    valid_contracts: int = 0
    safety_gates_passed: int = 0
    safety_gates_failed: int = 0
    task_results: list[SmokeTaskResult] = Field(default_factory=list)
    summary: str


class SmokeTestRunner:
    """Executes pre-campaign quality control smoke tests against AI model providers."""

    def __init__(
        self,
        paths: Optional[ProjectPaths] = None,
        model_registry: Optional[ModelRegistry] = None,
    ) -> None:
        self.paths = paths or get_paths()
        self.registry = model_registry or get_model_registry()
        self.task_repo = TaskRepository(self.paths.generated_tasks_dir)
        self.scenario_repo = ScenarioRepository(self.paths.generated_scenarios_dir)
        self.gt_repo = GroundTruthRepository(self.paths.generated_ground_truth_dir)
        self.evaluator = DeterministicEvaluator()

    def run_smoke_test(
        self,
        model_id: str,
        is_mock: bool = False,
        output_dir: Optional[Path] = None,
    ) -> SmokeTestReport:
        """Execute smoke test across the 3 canonical task archetypes.

        Args:
            model_id: Identifier of model to test (e.g. 'gpt-4o', 'gemini-1.5-flash', 'mock-valid-migration').
            is_mock: Force mock provider simulation mode.
            output_dir: Directory where smoke test artifacts should be stored.

        Returns:
            SmokeTestReport certifying whether the model passed all integration checks.
        """
        logger.info(
            "Executing quality control smoke test for model '%s' (is_mock=%s)",
            model_id,
            is_mock,
        )

        out_dir = output_dir or (self.paths.results_dir / "smoke_tests" / model_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_dir = out_dir / "raw_responses"
        raw_dir.mkdir(parents=True, exist_ok=True)

        # 1. Instantiate provider and verify credentials
        try:
            if is_mock or not self.registry.has_model(model_id):
                from phoenix_eval.providers.base import MockModelProvider

                provider: BaseModelProvider = MockModelProvider(
                    model_identifier=model_id,
                    behavior="valid_migration",
                )
                is_mock_actual = True
            else:
                config = self.registry.get_model_config(model_id)
                provider = self.registry.create_provider(model_id)
                is_mock_actual = config.is_mock
        except ProviderAuthenticationError as auth_err:
            logger.error("Smoke test authentication failed for '%s': %s", model_id, auth_err)
            return SmokeTestReport(
                model_id=model_id,
                is_mock=is_mock,
                status="AUTH_FAILED",
                summary=(
                    f"Authentication failure: {auth_err}. "
                    "Ensure appropriate environment variable (e.g. OPENAI_API_KEY, GEMINI_API_KEY) is configured."
                ),
            )
        except Exception as err:
            logger.error("Provider initialization error for '%s': %s", model_id, err)
            return SmokeTestReport(
                model_id=model_id,
                is_mock=is_mock,
                status="FAILED",
                summary=f"Provider initialization failed: {err}",
            )

        task_results: list[SmokeTaskResult] = []
        successful_reqs = 0
        valid_contracts = 0
        gates_passed = 0
        gates_failed = 0

        # 2. Iterate through canonical smoke tasks
        for spec in CANONICAL_SMOKE_TASKS:
            t_id = spec["task_id"]
            archetype = spec["archetype"]
            desc = spec["description"]

            try:
                task = self.task_repo.load_task(t_id)
                scen = self.scenario_repo.load_scenario(task.scenario_reference)
                gt = self.gt_repo.load_ground_truth(task.ground_truth_reference)
            except Exception as load_err:
                task_results.append(
                    SmokeTaskResult(
                        task_id=t_id,
                        archetype=archetype,
                        description=desc,
                        prompt_sent=False,
                        ground_truth_isolated=False,
                        response_received=False,
                        contract_valid=False,
                        error_message=f"Failed loading task artifacts: {load_err}",
                    )
                )
                continue

            # Ground-truth isolation check
            prompt_text = build_model_prompt(task, scen)
            gt_isolated = bool(
                task.ground_truth_reference and task.ground_truth_reference not in prompt_text
            )
            if not gt_isolated:
                raise GroundTruthLeakageError(
                    f"Security check failed: Prompt leaked ground truth reference '{task.ground_truth_reference}'"
                )

            req = ProviderPromptRequest(
                task_id=t_id,
                prompt=prompt_text,
                system_prompt=BENCHMARK_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=2048,
                metadata={"task": task, "scenario": scen, "smoke_test": True},
            )

            # Send request
            t0 = time.perf_counter()
            try:
                model_resp = provider.generate_response(req)
                lat = round(time.perf_counter() - t0, 4)
                successful_reqs += 1
                resp_received = True
            except Exception as req_err:
                task_results.append(
                    SmokeTaskResult(
                        task_id=t_id,
                        archetype=archetype,
                        description=desc,
                        prompt_sent=True,
                        ground_truth_isolated=gt_isolated,
                        response_received=False,
                        contract_valid=False,
                        error_message=sanitize_text(str(req_err)),
                    )
                )
                continue

            # Save raw response
            raw_path = raw_dir / f"{t_id}.json"
            write_json(raw_path, model_resp.model_dump(mode="json"))

            # Evaluate response contract & deterministic scoring
            parsed = parse_model_response(model_resp.raw_response)
            is_contract = parsed.is_valid_contract
            if is_contract:
                valid_contracts += 1

            eval_report = self.evaluator.evaluate_detailed(
                task=task,
                raw_response_text=model_resp.raw_response,
                ground_truth=gt,
                scenario=scen,
                model_identifier=model_id,
                model_version=provider.model_version,
            )

            if eval_report.safety_gate_passed:
                gates_passed += 1
            else:
                gates_failed += 1

            violation_codes = [
                v.get("rule_name", "") if isinstance(v, dict) else getattr(v, "rule_name", "")
                for v in eval_report.critical_violations
            ]

            task_results.append(
                SmokeTaskResult(
                    task_id=t_id,
                    archetype=archetype,
                    description=desc,
                    prompt_sent=True,
                    ground_truth_isolated=gt_isolated,
                    response_received=resp_received,
                    contract_valid=is_contract,
                    decision_reported=eval_report.model_reported_decision,
                    raw_score=round(eval_report.raw_weighted_score, 2),
                    effective_score=round(eval_report.effective_score, 2),
                    safety_gate_passed=eval_report.safety_gate_passed,
                    critical_violations_count=len(eval_report.critical_violations),
                    violation_codes=violation_codes,
                    latency_seconds=lat,
                )
            )

        overall_passed = successful_reqs == len(CANONICAL_SMOKE_TASKS) and all(
            r.ground_truth_isolated for r in task_results
        )
        report_status = "PASSED" if overall_passed else "FAILED"

        summary_msg = (
            f"Smoke test for model '{model_id}' concluded with status {report_status}. "
            f"Requests: {successful_reqs}/{len(CANONICAL_SMOKE_TASKS)}, "
            f"Valid Contracts: {valid_contracts}/{len(CANONICAL_SMOKE_TASKS)}, "
            f"Safety Gates Passed: {gates_passed}, Gates Failed: {gates_failed}. "
            f"Mode: {'Mock' if is_mock_actual else 'Live API'}."
        )

        report = SmokeTestReport(
            model_id=model_id,
            is_mock=is_mock_actual,
            status=report_status,
            total_tasks=len(CANONICAL_SMOKE_TASKS),
            successful_requests=successful_reqs,
            valid_contracts=valid_contracts,
            safety_gates_passed=gates_passed,
            safety_gates_failed=gates_failed,
            task_results=task_results,
            summary=summary_msg,
        )

        report_file = out_dir / "smoke_test_report.json"
        write_json(report_file, report.model_dump(mode="json"))
        return report
