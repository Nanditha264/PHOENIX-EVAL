"""Experiment execution runner orchestrating multi-model multi-task evaluations, resumption, and persistence."""

import contextlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from phoenix_eval.benchmark.fingerprint import compute_dataset_fingerprints
from phoenix_eval.benchmark.prompt_builder import build_model_prompt
from phoenix_eval.core.constants import BENCHMARK_SYSTEM_PROMPT
from phoenix_eval.core.exceptions import (
    ExperimentError,
    GroundTruthLeakageError,
    ProviderAuthenticationError,
    ProviderEmptyResponseError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.core.security import sanitize_text
from phoenix_eval.data.repository import GroundTruthRepository, ScenarioRepository, TaskRepository
from phoenix_eval.data.serialization import read_json, write_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.experiment.aggregator import ExperimentAggregator
from phoenix_eval.experiment.config_loader import ExperimentValidator
from phoenix_eval.experiment.lifecycle import derive_experiment_lifecycle_status
from phoenix_eval.providers.base import BaseModelProvider, ProviderPromptRequest
from phoenix_eval.providers.model_registry import ModelRegistry, get_model_registry
from phoenix_eval.schemas.common import ExecutionStatus
from phoenix_eval.schemas.experiments import (
    ExperimentConfig,
    ExperimentLifecycleStatus,
    ExperimentManifest,
    ExperimentRunRecord,
)
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask
from phoenix_eval.utils.hashing import compute_full_input_hash, compute_sha256
from phoenix_eval.utils.time import current_utc_timestamp

logger = get_logger("experiment.runner")


class FileLock:
    """Atomic file lock to prevent concurrent executions against the same experiment directory.

    Uses atomic O_CREAT | O_EXCL to eliminate check-then-write (TOCTOU) race conditions.
    Records owner PID and UTC timestamp inside the lock file.
    Verifies process ownership before releasing to prevent deleting another runner's lock.

    Stale Lock Recovery Procedure:
    If a runner process crashes or is killed ungracefully, the lock file remains on disk.
    1. Read the lock file to inspect the owner PID and timestamp.
    2. Check if a process with that PID is active.
    3. If no active process owns the lock, or the process has exited, remove the lock file:
       `rm <output_dir>/.experiment.lock`
    """

    def __init__(self, lock_file: Path) -> None:
        self.lock_file = lock_file
        self._acquired = False
        self._fd: Optional[int] = None

    def acquire(self) -> None:
        """Atomically create the lock file using exclusive creation flags."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(self.lock_file), flags)
            self._fd = fd
            payload = f"pid={os.getpid()}\ntimestamp={current_utc_timestamp().isoformat()}\n"
            os.write(fd, payload.encode("utf-8"))
            self._acquired = True
        except FileExistsError:
            owner_info = "unknown"
            with contextlib.suppress(Exception):
                owner_info = self.lock_file.read_text(encoding="utf-8").strip()
            raise ExperimentError(
                f"Experiment lock exists at '{self.lock_file}'. "
                "Another experiment runner is currently executing.\n"
                f"Existing lock details:\n{owner_info}\n"
                "Stale Lock Recovery: If the prior process terminated abnormally, "
                f"verify PID is inactive and delete '{self.lock_file}'."
            ) from None
        except Exception as err:
            raise ExperimentError(
                f"Could not acquire experiment lock at '{self.lock_file}': {err}"
            ) from err

    def release(self) -> None:
        """Release the lock after verifying PID ownership."""
        if not self._acquired:
            return

        # Close descriptor if still open
        if self._fd is not None:
            with contextlib.suppress(Exception):
                os.close(self._fd)
            self._fd = None

        if self.lock_file.exists():
            try:
                content = self.lock_file.read_text(encoding="utf-8")
                expected_pid = f"pid={os.getpid()}"
                if expected_pid in content or content.strip() == str(os.getpid()):
                    self.lock_file.unlink()
                else:
                    logger.warning(
                        "Lock release skipped: PID mismatch on '%s'. Expected PID %s, found: %s",
                        self.lock_file,
                        os.getpid(),
                        content.strip(),
                    )
            except Exception as err:
                logger.warning("Could not release lock file '%s': %s", self.lock_file, err)
            finally:
                self._acquired = False
        else:
            self._acquired = False

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


class ExperimentRunner:
    """Central orchestration service executing multi-model multi-task benchmark campaigns."""

    def __init__(
        self,
        config: ExperimentConfig,
        paths: Optional[ProjectPaths] = None,
        evaluator: Optional[DeterministicEvaluator] = None,
        model_registry: Optional[ModelRegistry] = None,
        progress_callback: Optional[
            Callable[[int, int, Optional[ExperimentRunRecord]], None]
        ] = None,
    ) -> None:
        self.config = config
        self.paths = paths or get_paths()
        self.evaluator = evaluator or DeterministicEvaluator()
        self.model_registry = model_registry or get_model_registry()
        self.progress_callback = progress_callback

        # Initialize repositories
        self.task_repo = TaskRepository(self.paths.generated_tasks_dir)
        self.seed_task_repo = TaskRepository(self.paths.tasks_dir)

        self.scenario_repo = ScenarioRepository(self.paths.generated_scenarios_dir)
        self.seed_scenario_repo = ScenarioRepository(self.paths.scenarios_dir)

        # Ground truth repository (evaluator-only boundary)
        extra_gt_dirs = (
            [self.paths.generated_ground_truth_dir]
            if self.paths.generated_ground_truth_dir.is_dir()
            else []
        )
        self.gt_repo = GroundTruthRepository(self.paths.ground_truth_dir, extra_dirs=extra_gt_dirs)

        # Pre-flight validator
        self.validator = ExperimentValidator(paths=self.paths, registry=self.model_registry)

        # Setup output directory
        if self.config.output_dir:
            self.output_dir = Path(self.config.output_dir).resolve()
        else:
            self.output_dir = (
                self.paths.results_dir / "experiments" / self.config.experiment_id
            ).resolve()

        self.raw_responses_dir = self.output_dir / "raw_responses"
        self.evaluations_dir = self.output_dir / "evaluations"
        self.runs_jsonl_path = self.output_dir / "runs.jsonl"
        self.manifest_path = self.output_dir / "experiment_manifest.json"
        self.lock_file_path = self.output_dir / ".experiment.lock"

    def _load_task(self, task_id: str) -> BenchmarkTask:
        """Resolve and load task model from repositories."""
        try:
            return self.task_repo.load_task(task_id)
        except Exception:
            return self.seed_task_repo.load_task(task_id)

    def _load_scenario(self, scenario_id: str) -> ScenarioModel:
        """Resolve and load scenario model from repositories."""
        try:
            return self.scenario_repo.load_scenario(scenario_id)
        except Exception:
            return self.seed_scenario_repo.load_scenario(scenario_id)

    def _load_existing_runs(self) -> tuple[dict[str, ExperimentRunRecord], int]:
        """Load existing run attempts from runs.jsonl for resumption.

        Returns:
            Tuple of (dict mapping run_id to its latest ExperimentRunRecord, total attempts count).
        """
        authoritative_runs: dict[str, ExperimentRunRecord] = {}
        total_attempts = 0
        if not self.runs_jsonl_path.exists():
            return authoritative_runs, 0

        try:
            with open(self.runs_jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record_dict = json.loads(line)
                        record = ExperimentRunRecord.model_validate(record_dict)
                        total_attempts += 1
                        # Retain latest attempt as authoritative state for run_id
                        authoritative_runs[record.run_id] = record
                    except Exception as err:
                        logger.warning("Error parsing existing run record line: %s", err)
        except Exception as err:
            logger.warning("Could not read existing runs from %s: %s", self.runs_jsonl_path, err)

        return authoritative_runs, total_attempts

    def _append_run_record(self, record: ExperimentRunRecord) -> None:
        """Append a run record to the runs.jsonl log."""
        with open(self.runs_jsonl_path, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def _verify_ground_truth_isolation(self, prompt: str, task: BenchmarkTask) -> None:
        """Assert that prompt contains zero ground truth identifiers or leaked answers."""
        gt_ref = task.ground_truth_reference
        if gt_ref and gt_ref in prompt:
            raise GroundTruthLeakageError(
                f"Security Violation: Prompt contains ground truth reference '{gt_ref}'."
            )

    def _save_manifest(
        self,
        status: ExperimentLifecycleStatus,
        runs: list[ExperimentRunRecord],
        total_scheduled: int,
        total_attempts: int,
        skipped_count: int,
        fingerprint_result: Any,
        pre_flight_mode: str,
        summary_metrics: Optional[dict[str, Any]] = None,
    ) -> ExperimentManifest:
        """Atomically persist experiment manifest to disk with complete metadata."""
        completed_runs_count = sum(
            1 for r in runs if r.execution_status == ExecutionStatus.COMPLETED
        )
        failed_runs_count = sum(1 for r in runs if r.execution_status != ExecutionStatus.COMPLETED)

        is_terminal = status in (
            ExperimentLifecycleStatus.COMPLETED,
            ExperimentLifecycleStatus.COMPLETED_WITH_FAILURES,
            ExperimentLifecycleStatus.FAILED,
            ExperimentLifecycleStatus.INTERRUPTED,
        )

        manifest = ExperimentManifest(
            experiment_id=self.config.experiment_id,
            experiment_name=self.config.experiment_name,
            config=self.config,
            started_at=runs[0].timestamp_started if runs else current_utc_timestamp(),
            completed_at=current_utc_timestamp() if is_terminal else None,
            execution_status=status,
            dataset_fingerprint=fingerprint_result.dataset_fingerprint,
            model_visible_dataset_fingerprint=fingerprint_result.model_visible_dataset_fingerprint,
            evaluator_dataset_fingerprint=fingerprint_result.evaluator_dataset_fingerprint,
            dataset_manifest_version=fingerprint_result.dataset_manifest_version,
            fingerprint_algorithm=fingerprint_result.fingerprint_algorithm,
            fingerprint_created_at=fingerprint_result.fingerprint_created_at,
            total_scheduled_runs=total_scheduled,
            total_attempts_count=total_attempts,
            completed_runs_count=completed_runs_count,
            failed_runs_count=failed_runs_count,
            skipped_resumed_runs_count=skipped_count,
            runs=runs,
            summary_metrics=summary_metrics,
            reproducibility_metadata={
                "evaluator_version": self.evaluator.evaluator_version,
                "benchmark_version": "4.0.0",
                "mode": pre_flight_mode,
            },
        )
        write_json(self.manifest_path, manifest)
        return manifest

    def run(self) -> ExperimentManifest:
        """Execute the complete multi-model benchmark experiment with full resumption support."""
        # 1. Pre-flight checks
        pre_flight = self.validator.validate_pre_flight(self.config)
        resolved_tasks = pre_flight["resolved_tasks"]
        selected_models = pre_flight["models"]
        total_runs_scheduled = pre_flight["total_runs"]

        # Compute deterministic dataset fingerprint for the resolved tasks and benchmark data
        dataset_fp_result = compute_dataset_fingerprints(self.paths, task_ids=resolved_tasks)

        # 2. Ensure output directory layout
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_responses_dir.mkdir(parents=True, exist_ok=True)
        self.evaluations_dir.mkdir(parents=True, exist_ok=True)

        # Check existing manifest on resume for dataset fingerprint mismatch
        if self.config.resume and self.manifest_path.exists():
            try:
                existing_manifest_data = read_json(self.manifest_path)
                recorded_fp = existing_manifest_data.get("dataset_fingerprint")
                if recorded_fp and recorded_fp != dataset_fp_result.dataset_fingerprint:
                    if not self.config.ignore_dataset_mismatch:
                        raise ExperimentError(
                            f"Dataset fingerprint mismatch for experiment '{self.config.experiment_id}'.\n"
                            f"Recorded fingerprint: {recorded_fp}\n"
                            f"Active dataset fingerprint: {dataset_fp_result.dataset_fingerprint}\n"
                            "The underlying benchmark task or scenario files have changed since this experiment started. "
                            "Resuming against modified data violates benchmark reproducibility.\n"
                            "To override, set ignore_dataset_mismatch=True in ExperimentConfig."
                        )
                    else:
                        logger.warning(
                            "Dataset fingerprint mismatch detected for '%s' (recorded: %s, active: %s), "
                            "resuming anyway because ignore_dataset_mismatch=True.",
                            self.config.experiment_id,
                            recorded_fp,
                            dataset_fp_result.dataset_fingerprint,
                        )
            except ExperimentError:
                raise
            except Exception as err:
                logger.warning(
                    "Could not inspect existing manifest for fingerprint validation: %s", err
                )

        logger.info(
            "Starting Experiment '%s' (%s): %d models x %d tasks x %d trials = %d runs",
            self.config.experiment_id,
            self.config.experiment_name,
            len(selected_models),
            len(resolved_tasks),
            self.config.number_of_trials,
            total_runs_scheduled,
        )

        with FileLock(self.lock_file_path):
            existing_runs, historical_attempts = (
                self._load_existing_runs() if self.config.resume else ({}, 0)
            )
            authoritative_runs: dict[str, ExperimentRunRecord] = dict(existing_runs)
            total_attempts_executed = historical_attempts
            skipped_runs_count = 0

            # Write initial manifest in RUNNING state
            self._save_manifest(
                status=ExperimentLifecycleStatus.RUNNING,
                runs=list(authoritative_runs.values()),
                total_scheduled=total_runs_scheduled,
                total_attempts=total_attempts_executed,
                skipped_count=skipped_runs_count,
                fingerprint_result=dataset_fp_result,
                pre_flight_mode=pre_flight["mode"],
            )

            # Instantiate providers upfront to verify connections
            providers: dict[str, BaseModelProvider] = {}
            for m_id in selected_models:
                p = self.model_registry.create_provider(m_id)
                # Let ExperimentRunner directly manage retry loops and exponential backoff
                if hasattr(p, "max_retries"):
                    p.max_retries = 0
                providers[m_id] = p

            task_metadata: dict[str, dict[str, Any]] = {}
            run_counter = 0

            # Transient errors subject to bounded exponential backoff retries
            transient_error_types = (
                ProviderTimeoutError,
                ProviderNetworkError,
                ProviderRateLimitError,
                ProviderServerError,
            )

            try:
                # Execute Cartesian product: models x tasks x trials
                for m_id in selected_models:
                    provider = providers[m_id]

                    for t_id in resolved_tasks:
                        task = self._load_task(t_id)
                        scenario = self._load_scenario(task.scenario_reference)

                        # Cache task metadata for aggregation
                        fam_val = getattr(task, "task_family", None)
                        if not fam_val:
                            parts = t_id.lower().split("-")
                            for part in parts:
                                if part.startswith("t") and len(part) == 3 and part[1:].isdigit():
                                    fam_val = part.upper()
                                    break
                        if not fam_val:
                            fam_val = (
                                str(task.task_category.value)
                                if hasattr(task.task_category, "value")
                                else str(task.task_category)
                            )
                        fam_val = str(fam_val)

                        dom_val = None
                        if scenario.metadata and scenario.metadata.custom:
                            dom_val = scenario.metadata.custom.get("domain")
                        if not dom_val and scenario.metadata and scenario.metadata.tags:
                            for tag in scenario.metadata.tags:
                                tag_u = tag.upper()
                                if "BANK" in tag_u:
                                    dom_val = "BANKING_PAYMENTS"
                                    break
                                elif "TELCO" in tag_u or "TELECOM" in tag_u:
                                    dom_val = "TELECOM_NETWORK"
                                    break
                                elif "IDP" in tag_u or "IDENTITY" in tag_u:
                                    dom_val = "CLOUD_IDENTITY"
                                    break
                                elif "GOV" in tag_u:
                                    dom_val = "GOVERNMENT_CRITICAL"
                                    break
                                elif "ERP" in tag_u or "ENTERPRISE" in tag_u:
                                    dom_val = "ENTERPRISE_SERVICES"
                                    break
                        if not dom_val:
                            t_lower = t_id.lower()
                            if "bank" in t_lower:
                                dom_val = "BANKING_PAYMENTS"
                            elif "telco" in t_lower:
                                dom_val = "TELECOM_NETWORK"
                            elif "idp" in t_lower or "cloud" in t_lower:
                                dom_val = "CLOUD_IDENTITY"
                            elif "gov" in t_lower:
                                dom_val = "GOVERNMENT_CRITICAL"
                            elif "erp" in t_lower or "ent" in t_lower:
                                dom_val = "ENTERPRISE_SERVICES"
                        if not dom_val:
                            dom_attr = getattr(scenario, "domain", None)
                            dom_val = (
                                str(dom_attr.value)
                                if (dom_attr is not None and hasattr(dom_attr, "value"))
                                else str(dom_attr or "Unknown")
                            )
                        dom_val = str(dom_val)

                        diff_val = (
                            str(task.difficulty.value)
                            if hasattr(task.difficulty, "value")
                            else str(task.difficulty)
                        )
                        task_metadata[t_id] = {
                            "family": fam_val,
                            "domain": dom_val,
                            "difficulty": diff_val,
                        }

                        for trial in range(1, self.config.number_of_trials + 1):
                            run_counter += 1
                            run_id = f"run-{self.config.experiment_id}-{m_id}-{t_id}-t{trial}"
                            prior_run = authoritative_runs.get(run_id)

                            # Check if already completed under resume
                            if (
                                self.config.resume
                                and prior_run is not None
                                and prior_run.execution_status == ExecutionStatus.COMPLETED
                            ):
                                logger.info(
                                    "[%d/%d] Resuming: Skipping already completed run %s",
                                    run_counter,
                                    total_runs_scheduled,
                                    run_id,
                                )
                                skipped_runs_count += 1
                                if self.progress_callback:
                                    self.progress_callback(
                                        run_counter, total_runs_scheduled, prior_run
                                    )
                                continue

                            attempt_number = (prior_run.attempt_number + 1) if prior_run else 1
                            total_attempts_executed += 1

                            logger.info(
                                "[%d/%d] Executing run %s (model=%s, task=%s, trial=%d, attempt=%d)",
                                run_counter,
                                total_runs_scheduled,
                                run_id,
                                m_id,
                                t_id,
                                trial,
                                attempt_number,
                            )

                            # Step 1: Build model prompt and reproducible input hashes
                            prompt_text = build_model_prompt(task, scenario)
                            self._verify_ground_truth_isolation(prompt_text, task)
                            prompt_hash = compute_sha256(prompt_text)
                            system_prompt = BENCHMARK_SYSTEM_PROMPT
                            full_input_hash = compute_full_input_hash(
                                prompt=prompt_text,
                                system_prompt=system_prompt,
                                temperature=self.config.temperature,
                                max_tokens=self.config.max_output_tokens,
                            )

                            request = ProviderPromptRequest(
                                task_id=t_id,
                                prompt=prompt_text,
                                system_prompt=system_prompt,
                                temperature=self.config.temperature,
                                max_tokens=self.config.max_output_tokens,
                                timeout_seconds=self.config.timeout_seconds,
                                metadata={
                                    "experiment_id": self.config.experiment_id,
                                    "trial": trial,
                                    "attempt": attempt_number,
                                    "task": task,
                                    "scenario": scenario,
                                },
                            )

                            start_time = current_utc_timestamp()
                            raw_response_path: Optional[Path] = None
                            eval_report_path: Optional[Path] = None
                            exec_status = ExecutionStatus.COMPLETED
                            error_type: Optional[str] = None
                            error_msg: Optional[str] = None
                            model_resp: Optional[ModelResponse] = None

                            # Step 2: Invoke Provider with bounded exponential retry loop
                            retries_attempted = 0
                            max_retries = self.config.retry_count

                            for retry_idx in range(max_retries + 1):
                                try:
                                    model_resp = provider.generate_response(request)
                                    exec_status = ExecutionStatus.COMPLETED
                                    error_type = None
                                    error_msg = None
                                    break
                                except transient_error_types as err:
                                    if retry_idx < max_retries:
                                        retries_attempted += 1
                                        backoff = min(10.0, 0.5 * (2**retry_idx))
                                        logger.warning(
                                            "Run %s transient error (attempt %d/%d, retrying in %.2fs): %s",
                                            run_id,
                                            retry_idx + 1,
                                            max_retries + 1,
                                            backoff,
                                            err,
                                        )
                                        time.sleep(backoff)
                                    else:
                                        retries_attempted = retry_idx
                                        if isinstance(err, ProviderTimeoutError):
                                            exec_status = ExecutionStatus.TIMED_OUT
                                            error_type = "TimeoutError"
                                        else:
                                            exec_status = ExecutionStatus.FAILED
                                            error_type = type(err).__name__
                                        error_msg = sanitize_text(str(err))
                                        logger.error(
                                            "Run %s transient retries exhausted (%d): %s",
                                            run_id,
                                            max_retries,
                                            error_msg,
                                        )
                                except ProviderAuthenticationError as err:
                                    exec_status = ExecutionStatus.FAILED
                                    error_type = "AuthenticationError"
                                    error_msg = sanitize_text(str(err))
                                    logger.error("Run %s auth failed: %s", run_id, error_msg)
                                    raise
                                except (
                                    ProviderInvalidRequestError,
                                    ProviderEmptyResponseError,
                                ) as err:
                                    exec_status = ExecutionStatus.FAILED
                                    error_type = type(err).__name__
                                    error_msg = sanitize_text(str(err))
                                    logger.error(
                                        "Run %s non-retryable provider error: %s", run_id, error_msg
                                    )
                                    break
                                except ProviderError as err:
                                    exec_status = ExecutionStatus.FAILED
                                    error_type = type(err).__name__
                                    error_msg = sanitize_text(str(err))
                                    logger.error("Run %s provider failed: %s", run_id, error_msg)
                                    break
                                except Exception as err:
                                    exec_status = ExecutionStatus.FAILED
                                    error_type = "UnexpectedError"
                                    error_msg = sanitize_text(str(err))
                                    logger.error("Run %s unexpected error: %s", run_id, error_msg)
                                    break

                            # Step 3: Handle Outcome & Evaluation
                            end_time = current_utc_timestamp()
                            latency_val = (
                                model_resp.execution_duration
                                if model_resp
                                else (end_time - start_time).total_seconds()
                            )
                            response_hash: Optional[str] = None
                            prompt_tokens: Optional[int] = None
                            completion_tokens: Optional[int] = None
                            total_tokens: Optional[int] = None
                            cost_usd: Optional[float] = None

                            raw_score: Optional[float] = None
                            eff_score: Optional[float] = None
                            safety_gate_passed: Optional[bool] = None
                            crit_viols = 0
                            overall_status: Optional[str] = None

                            if model_resp and exec_status == ExecutionStatus.COMPLETED:
                                response_hash = compute_sha256(model_resp.raw_response)

                                # Persist raw response
                                raw_file = self.raw_responses_dir / f"{run_id}.json"
                                write_json(raw_file, model_resp)
                                raw_response_path = raw_file

                                # Extract usage
                                if model_resp.token_usage:
                                    prompt_tokens = model_resp.token_usage.prompt_tokens
                                    completion_tokens = model_resp.token_usage.completion_tokens
                                    total_tokens = model_resp.token_usage.total_tokens
                                    cost_usd = model_resp.token_usage.estimated_cost_usd

                                # Evaluate response using DeterministicEvaluator
                                try:
                                    ground_truth = self.gt_repo.load_ground_truth(
                                        task.ground_truth_reference
                                    )
                                    eval_report = self.evaluator.evaluate_detailed(
                                        task=task,
                                        raw_response_text=model_resp.raw_response,
                                        ground_truth=ground_truth,
                                        scenario=scenario,
                                        model_identifier=m_id,
                                        model_version=model_resp.model_version,
                                    )

                                    # Persist evaluation report
                                    eval_file = self.evaluations_dir / f"{run_id}.json"
                                    eval_report.save(self.evaluations_dir)
                                    # rename or copy to deterministic run_id filename
                                    generated_eval_file = (
                                        self.evaluations_dir / f"{eval_report.evaluation_id}.json"
                                    )
                                    if (
                                        generated_eval_file.exists()
                                        and generated_eval_file != eval_file
                                    ):
                                        generated_eval_file.rename(eval_file)
                                    eval_report_path = eval_file

                                    raw_score = eval_report.raw_weighted_score
                                    eff_score = eval_report.effective_score
                                    safety_gate_passed = eval_report.safety_gate_passed
                                    crit_viols = len(eval_report.critical_violations)
                                    overall_status = eval_report.overall_status

                                except Exception as eval_err:
                                    logger.error(
                                        "Evaluation failed on run %s: %s", run_id, eval_err
                                    )
                                    exec_status = ExecutionStatus.FAILED
                                    error_type = "EvaluationError"
                                    error_msg = sanitize_text(str(eval_err))

                            # Step 4: Record run record (appended to runs.jsonl and replaces prior state in manifest)
                            run_record = ExperimentRunRecord(
                                experiment_id=self.config.experiment_id,
                                run_id=run_id,
                                task_id=t_id,
                                scenario_id=scenario.scenario_id,
                                provider_name=provider.provider_name,
                                model_identifier=m_id,
                                model_version=provider.model_version,
                                configured_model_identifier=m_id,
                                configured_model_version=provider.model_version,
                                returned_model_identifier=model_resp.returned_model_identifier
                                if model_resp
                                else None,
                                returned_model_version=model_resp.returned_model_version
                                if model_resp
                                else None,
                                provider_request_id=model_resp.provider_request_id
                                if model_resp
                                else None,
                                trial_number=trial,
                                attempt_number=attempt_number,
                                execution_status=exec_status,
                                timestamp_started=start_time,
                                timestamp_completed=end_time,
                                latency_seconds=round(latency_val, 4),
                                prompt_hash=prompt_hash,
                                full_input_hash=full_input_hash,
                                system_prompt=system_prompt,
                                response_hash=response_hash,
                                raw_response_file=str(raw_response_path)
                                if raw_response_path
                                else None,
                                evaluation_report_file=str(eval_report_path)
                                if eval_report_path
                                else None,
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                total_tokens=total_tokens,
                                estimated_cost_usd=cost_usd,
                                retry_count=retries_attempted,
                                error_type=error_type,
                                error_message=error_msg,
                                is_mock=provider.is_mock,
                                raw_weighted_score=raw_score,
                                effective_score=eff_score,
                                safety_gate_passed=safety_gate_passed,
                                critical_violations_count=crit_viols,
                                overall_status=overall_status,
                                execution_metadata={"attempt": attempt_number},
                            )

                            self._append_run_record(run_record)
                            # Replace authoritative state for run_id
                            authoritative_runs[run_id] = run_record

                            if self.progress_callback:
                                self.progress_callback(
                                    run_counter, total_runs_scheduled, run_record
                                )

                            # Step 5: Rate limiting delay
                            if self.config.request_delay_seconds > 0.0:
                                time.sleep(self.config.request_delay_seconds)

            except KeyboardInterrupt:
                logger.warning(
                    "Experiment '%s' interrupted by user (SIGINT).", self.config.experiment_id
                )
                final_runs = list(authoritative_runs.values())
                interrupted_status = derive_experiment_lifecycle_status(
                    total_runs_scheduled, final_runs, is_interrupted=True
                )
                self._save_manifest(
                    status=interrupted_status,
                    runs=final_runs,
                    total_scheduled=total_runs_scheduled,
                    total_attempts=total_attempts_executed,
                    skipped_count=skipped_runs_count,
                    fingerprint_result=dataset_fp_result,
                    pre_flight_mode=pre_flight["mode"],
                )
                raise
            except Exception as exc:
                logger.error(
                    "Experiment '%s' crashed with unexpected error: %s",
                    self.config.experiment_id,
                    exc,
                )
                final_runs = list(authoritative_runs.values())
                crashed_status = derive_experiment_lifecycle_status(
                    total_runs_scheduled, final_runs, initialization_failed=(len(final_runs) == 0)
                )
                self._save_manifest(
                    status=crashed_status,
                    runs=final_runs,
                    total_scheduled=total_runs_scheduled,
                    total_attempts=total_attempts_executed,
                    skipped_count=skipped_runs_count,
                    fingerprint_result=dataset_fp_result,
                    pre_flight_mode=pre_flight["mode"],
                )
                raise

            # 3. Post-execution Aggregations on authoritative final state
            final_runs = list(authoritative_runs.values())
            aggregator = ExperimentAggregator(
                config=self.config,
                runs=final_runs,
                task_metadata=task_metadata,
            )
            summary_data = aggregator.compute_summary()

            # Export comparison artifacts
            aggregator.write_summary_json(self.output_dir / "model_summary.json")
            aggregator.write_comparison_csv(self.output_dir / "model_comparison.csv")
            aggregator.write_markdown_summary(self.output_dir / "experiment_summary.md")

            final_lifecycle_status = derive_experiment_lifecycle_status(
                total_scheduled_runs=total_runs_scheduled,
                runs=final_runs,
            )

            manifest = self._save_manifest(
                status=final_lifecycle_status,
                runs=final_runs,
                total_scheduled=total_runs_scheduled,
                total_attempts=total_attempts_executed,
                skipped_count=skipped_runs_count,
                fingerprint_result=dataset_fp_result,
                pre_flight_mode=pre_flight["mode"],
                summary_metrics=summary_data,
            )

            logger.info(
                "Experiment '%s' completed with status %s. Output at %s",
                self.config.experiment_id,
                final_lifecycle_status,
                self.output_dir,
            )
            return manifest
