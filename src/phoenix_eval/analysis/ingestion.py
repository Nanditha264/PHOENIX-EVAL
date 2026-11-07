"""Experiment results ingestion, artifact integrity verification, and quarantine manager."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from phoenix_eval.analysis.schemas import IngestionRecordStatus, IngestionReport, RunValidationIssue
from phoenix_eval.benchmark.fingerprint import compute_dataset_fingerprints
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluation_report import DetailedEvaluationReport
from phoenix_eval.schemas.common import ExecutionStatus
from phoenix_eval.schemas.experiments import ExperimentManifest, ExperimentRunRecord
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.utils.hashing import compute_sha256

logger = get_logger("analysis.ingestion")


@dataclass
class ValidatedExperimentData:
    """Cleanly validated and partitioned experiment data package ready for benchmark analysis."""

    manifest: ExperimentManifest
    valid_runs: list[ExperimentRunRecord]
    failed_runs: list[ExperimentRunRecord]
    corrupted_runs: list[ExperimentRunRecord]
    raw_responses: dict[str, ModelResponse]
    evaluation_reports: dict[str, DetailedEvaluationReport]
    ingestion_report: IngestionReport
    is_mock: bool


class ExperimentIngestionValidator:
    """Validates experiment outputs, verifying raw files, hashes, dataset fingerprints, and provenance."""

    def __init__(self, paths: Optional[ProjectPaths] = None) -> None:
        self.paths = paths or get_paths()

    def ingest_experiment(
        self,
        experiment_id_or_dir: str | Path,
    ) -> ValidatedExperimentData:
        """Import, validate, and verify an experiment campaign.

        Args:
            experiment_id_or_dir: Experiment ID string (resolved under results/experiments/)
                or direct Path to the experiment output directory.

        Returns:
            ValidatedExperimentData with verified records partitioned from corrupted/failed runs.
        """
        if isinstance(experiment_id_or_dir, Path):
            exp_dir = experiment_id_or_dir.resolve()
        else:
            exp_dir = (self.paths.results_dir / "experiments" / experiment_id_or_dir).resolve()

        if not exp_dir.is_dir():
            raise FileNotFoundError(f"Experiment directory not found: '{exp_dir}'")

        manifest_file = exp_dir / "experiment_manifest.json"
        if not manifest_file.is_file():
            raise FileNotFoundError(f"Experiment manifest missing at '{manifest_file}'")

        # 1. Validate manifest schema
        try:
            manifest_dict = read_json(manifest_file)
            manifest = ExperimentManifest.model_validate(manifest_dict)
        except Exception as err:
            logger.error("Failed to parse experiment manifest '%s': %s", manifest_file, err)
            IngestionReport(
                experiment_id=exp_dir.name,
                import_status=IngestionRecordStatus.FAILED,
                total_scheduled_runs=0,
                total_attempts=0,
                completed_runs=0,
                failed_runs=0,
                summary=f"Fatal schema validation error reading manifest: {err}",
            )
            raise ValueError(f"Corrupted experiment manifest: {err}") from err

        issues: list[RunValidationIssue] = []
        valid_runs: list[ExperimentRunRecord] = []
        failed_runs: list[ExperimentRunRecord] = []
        corrupted_runs: list[ExperimentRunRecord] = []
        raw_responses: dict[str, ModelResponse] = {}
        evaluation_reports: dict[str, DetailedEvaluationReport] = {}

        missing_raw_count = 0
        missing_eval_count = 0
        response_hash_mismatch_count = 0
        prompt_hash_mismatch_count = 0

        # Check mandatory dataset fingerprint consistency across all 5 fields
        active_fp_res = compute_dataset_fingerprints(
            self.paths, task_ids=manifest.config.selected_tasks
        )
        active_fp = active_fp_res.dataset_fingerprint
        recorded_fp = manifest.dataset_fingerprint

        required_fp_fields = {
            "dataset_fingerprint": manifest.dataset_fingerprint,
            "model_visible_dataset_fingerprint": manifest.model_visible_dataset_fingerprint,
            "evaluator_dataset_fingerprint": manifest.evaluator_dataset_fingerprint,
            "dataset_manifest_version": manifest.dataset_manifest_version,
            "fingerprint_algorithm": manifest.fingerprint_algorithm,
        }
        missing_fp_fields = [k for k, v in required_fp_fields.items() if v is None]

        missing_fingerprints = bool(missing_fp_fields)
        if missing_fingerprints:
            fingerprint_match = False
            issues.append(
                RunValidationIssue(
                    run_id="EXPERIMENT_MANIFEST",
                    issue_type="INVALID_MISSING_DATASET_FINGERPRINT",
                    severity="WARNING",
                    description=(
                        f"Experiment manifest is missing mandatory dataset fingerprint fields: "
                        f"{', '.join(missing_fp_fields)}. Historical campaign classified as LEGACY_UNVERIFIABLE."
                    ),
                )
            )
        else:
            fingerprint_match = (
                recorded_fp == active_fp
                and manifest.model_visible_dataset_fingerprint
                == active_fp_res.model_visible_dataset_fingerprint
                and manifest.evaluator_dataset_fingerprint
                == active_fp_res.evaluator_dataset_fingerprint
            )
            if not fingerprint_match:
                issues.append(
                    RunValidationIssue(
                        run_id="EXPERIMENT_MANIFEST",
                        issue_type="INVALID_DATASET_FINGERPRINT_MISMATCH",
                        severity="WARNING",
                        description=(
                            f"Experiment was generated with dataset fingerprint '{recorded_fp}', "
                            f"but active dataset fingerprint is '{active_fp}'."
                        ),
                    )
                )

        # 2. Inspect and validate each run record
        raw_dir = exp_dir / "raw_responses"
        eval_dir = exp_dir / "evaluations"

        for record in manifest.runs:
            run_id = record.run_id
            is_corrupted = False

            # Provider execution failed / timed out
            if record.execution_status != ExecutionStatus.COMPLETED:
                failed_runs.append(record)
                continue

            # Verify raw response file existence
            raw_path = raw_dir / f"{run_id}.json"
            if not raw_path.is_file() and record.raw_response_file:
                cand = raw_dir / Path(record.raw_response_file).name
                if cand.is_file():
                    raw_path = cand

            if not raw_path.is_file():
                missing_raw_count += 1
                is_corrupted = True
                issues.append(
                    RunValidationIssue(
                        run_id=run_id,
                        issue_type="MISSING_RAW_RESPONSE",
                        severity="ERROR",
                        description=f"Referenced raw response file '{raw_path}' does not exist on disk.",
                    )
                )
            else:
                # Load and verify raw response content & SHA-256 hash
                try:
                    resp_dict = read_json(raw_path)
                    model_resp = ModelResponse.model_validate(resp_dict)
                    raw_responses[run_id] = model_resp

                    # Recompute response hash
                    computed_resp_hash = compute_sha256(model_resp.raw_response)
                    if record.response_hash and record.response_hash != computed_resp_hash:
                        response_hash_mismatch_count += 1
                        is_corrupted = True
                        issues.append(
                            RunValidationIssue(
                                run_id=run_id,
                                issue_type="RESPONSE_HASH_MISMATCH",
                                severity="ERROR",
                                description=(
                                    f"Stored response hash '{record.response_hash}' differs from "
                                    f"recomputed raw response SHA-256 '{computed_resp_hash}'."
                                ),
                            )
                        )

                    # Prompt hash check if present
                    if model_resp.prompt_hash and record.prompt_hash != model_resp.prompt_hash:
                        prompt_hash_mismatch_count += 1
                        is_corrupted = True
                        issues.append(
                            RunValidationIssue(
                                run_id=run_id,
                                issue_type="PROMPT_HASH_MISMATCH",
                                severity="ERROR",
                                description=(
                                    f"Run record prompt hash '{record.prompt_hash}' differs from "
                                    f"model response prompt hash '{model_resp.prompt_hash}'."
                                ),
                            )
                        )

                except Exception as raw_err:
                    is_corrupted = True
                    issues.append(
                        RunValidationIssue(
                            run_id=run_id,
                            issue_type="CORRUPTED_RAW_RESPONSE",
                            severity="ERROR",
                            description=f"Raw response file '{raw_path}' failed schema validation: {raw_err}",
                        )
                    )

            # Verify evaluation report file existence
            eval_path = eval_dir / f"{run_id}.json"
            if not eval_path.is_file() and record.evaluation_report_file:
                cand = eval_dir / Path(record.evaluation_report_file).name
                if cand.is_file():
                    eval_path = cand

            if not eval_path.is_file():
                missing_eval_count += 1
                is_corrupted = True
                issues.append(
                    RunValidationIssue(
                        run_id=run_id,
                        issue_type="MISSING_EVAL_REPORT",
                        severity="ERROR",
                        description=f"Referenced evaluation report '{eval_path}' does not exist on disk.",
                    )
                )
            else:
                try:
                    eval_dict = read_json(eval_path)
                    report_obj = DetailedEvaluationReport.model_validate(eval_dict)
                    evaluation_reports[run_id] = report_obj
                except Exception as eval_err:
                    is_corrupted = True
                    issues.append(
                        RunValidationIssue(
                            run_id=run_id,
                            issue_type="CORRUPTED_EVAL_REPORT",
                            severity="ERROR",
                            description=f"Evaluation report '{eval_path}' failed schema validation: {eval_err}",
                        )
                    )

            if is_corrupted:
                corrupted_runs.append(record)
            else:
                valid_runs.append(record)

        # Determine overall import status
        if corrupted_runs:
            import_status = IngestionRecordStatus.CORRUPTED
        elif missing_fingerprints:
            import_status = IngestionRecordStatus.LEGACY_UNVERIFIABLE
        elif not fingerprint_match:
            import_status = IngestionRecordStatus.VALID_WITH_WARNINGS
        else:
            import_status = IngestionRecordStatus.VALID

        is_mock_experiment = any(r.is_mock for r in manifest.runs) or manifest.config.mode == "mock"

        summary_msg = (
            f"Ingested experiment '{manifest.experiment_id}': {len(valid_runs)} valid runs, "
            f"{len(failed_runs)} failed runs, {len(corrupted_runs)} corrupted runs. "
            f"Status: {import_status} (Mode: {'Mock' if is_mock_experiment else 'Real'})."
        )

        ingestion_report = IngestionReport(
            experiment_id=manifest.experiment_id,
            import_status=import_status,
            total_scheduled_runs=manifest.total_scheduled_runs,
            total_attempts=manifest.total_attempts_count,
            completed_runs=len(valid_runs),
            failed_runs=len(failed_runs) + len(corrupted_runs),
            missing_raw_responses_count=missing_raw_count,
            missing_eval_reports_count=missing_eval_count,
            response_hash_mismatches_count=response_hash_mismatch_count,
            prompt_hash_mismatches_count=prompt_hash_mismatch_count,
            dataset_fingerprint_match=fingerprint_match,
            recorded_dataset_fingerprint=recorded_fp,
            active_dataset_fingerprint=active_fp,
            recorded_model_visible_fingerprint=manifest.model_visible_dataset_fingerprint,
            active_model_visible_fingerprint=active_fp_res.model_visible_dataset_fingerprint,
            recorded_evaluator_fingerprint=manifest.evaluator_dataset_fingerprint,
            active_evaluator_fingerprint=active_fp_res.evaluator_dataset_fingerprint,
            fingerprint_algorithm=manifest.fingerprint_algorithm,
            dataset_manifest_version=manifest.dataset_manifest_version,
            is_mock=is_mock_experiment,
            issues=issues,
            valid_run_ids=[r.run_id for r in valid_runs],
            corrupted_run_ids=[r.run_id for r in corrupted_runs],
            summary=summary_msg,
        )

        return ValidatedExperimentData(
            manifest=manifest,
            valid_runs=valid_runs,
            failed_runs=failed_runs,
            corrupted_runs=corrupted_runs,
            raw_responses=raw_responses,
            evaluation_reports=evaluation_reports,
            ingestion_report=ingestion_report,
            is_mock=is_mock_experiment,
        )
