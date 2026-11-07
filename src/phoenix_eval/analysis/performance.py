"""Benchmark performance metrics analyzer for PHOENIX-EVAL Phase 5.

Computes overall model metrics, dimension metrics, task-family breakdowns (T01-T10),
domain breakdowns, difficulty breakdowns, and trial stability/consistency.
Strictly separates mock and real evaluations, maintains explicit denominators,
and utilizes Wilson score intervals for safety failure rates.
"""

from collections import defaultdict
from typing import Any, Optional

from phoenix_eval.analysis.ingestion import ValidatedExperimentData
from phoenix_eval.analysis.schemas import (
    DifficultyMetrics,
    DimensionMetrics,
    DomainMetrics,
    ModelTaskTrialConsistency,
    OverallModelMetrics,
    TaskFamilyMetrics,
    TrialConsistencyOutcome,
)
from phoenix_eval.analysis.statistics import (
    calculate_descriptive_stats,
    calculate_wilson_interval,
)
from phoenix_eval.benchmark.task_loader import load_tasks_from_dir
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.schemas.experiments import ExperimentRunRecord
from phoenix_eval.schemas.tasks import BenchmarkTask

logger = get_logger("analysis.performance")

TASK_FAMILY_TITLES: dict[str, str] = {
    "T01": "Hidden Downstream Dependency",
    "T02": "False Cryptographic Discovery",
    "T03": "Incompatible Downstream Consumer",
    "T04": "Unknown External Provider",
    "T05": "Migration Ordering",
    "T06": "Dependency Cycle",
    "T07": "Missing Validation Evidence",
    "T08": "Failed Interoperability Test",
    "T09": "Valid Migration Control",
    "T10": "Conditional Plan Under Uncertainty",
}


class BenchmarkPerformanceAnalyzer:
    """Analyzes benchmark execution data into rigorous multidimensional performance metrics."""

    def __init__(self, paths: Optional[ProjectPaths] = None) -> None:
        self.paths = paths or get_paths()
        self._task_cache: dict[str, BenchmarkTask] = {}
        self._scenario_cache: dict[str, dict[str, Any]] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Cache all benchmark tasks and scenarios for metadata extraction."""
        # Tasks from generated and seed directories
        for t_dir in [self.paths.generated_tasks_dir, self.paths.tasks_dir]:
            if t_dir.is_dir():
                for t in load_tasks_from_dir(t_dir):
                    self._task_cache[t.task_id] = t

        # Scenarios from generated and seed directories
        for s_dir in [self.paths.generated_scenarios_dir, self.paths.scenarios_dir]:
            if s_dir.is_dir():
                for s_file in s_dir.glob("*.json"):
                    try:
                        s_data = read_json(s_file)
                        scen_id = s_data.get("scenario_id") or s_file.stem
                        self._scenario_cache[scen_id] = s_data
                    except Exception as err:
                        logger.warning("Failed to cache scenario '%s': %s", s_file, err)

    def _resolve_task_family(self, task_id: str) -> tuple[str, str]:
        """Resolve family ID (e.g. T01) and family title for a given task ID."""
        task = self._task_cache.get(task_id)
        fam_id = "T05"  # default migration ordering
        if task and task.task_family:
            fam_id = str(task.task_family).strip()
        else:
            # Fallback string parsing (e.g. task-gen-t01-bank-01)
            parts = task_id.lower().split("-")
            for part in parts:
                if part.startswith("t") and len(part) == 3 and part[1:].isdigit():
                    fam_id = part.upper()
                    break

        title = TASK_FAMILY_TITLES.get(fam_id, f"Task Family {fam_id}")
        return fam_id, title

    def _resolve_task_domain(self, task_id: str) -> str:
        """Resolve synthetic enterprise domain for a given task ID."""
        task = self._task_cache.get(task_id)
        if task and task.scenario_reference:
            scen_id = task.scenario_reference
            scen = self._scenario_cache.get(scen_id)
            if scen:
                custom = scen.get("metadata", {}).get("custom", {})
                if "domain" in custom:
                    return str(custom["domain"])
                tags = scen.get("metadata", {}).get("tags", [])
                for tag in tags:
                    tag_upper = tag.upper()
                    if "BANK" in tag_upper:
                        return "BANKING_PAYMENTS"
                    if "IDENTITY" in tag_upper or "IDP" in tag_upper:
                        return "CLOUD_IDENTITY"
                    if "TELCO" in tag_upper or "TELECOM" in tag_upper:
                        return "TELECOM_NETWORK"
                    if "GOV" in tag_upper:
                        return "GOVERNMENT_CRITICAL"
                    if "ENTERPRISE" in tag_upper or "SERVICES" in tag_upper:
                        return "ENTERPRISE_SERVICES"

        # Parsing heuristic from task_id
        tid_lower = task_id.lower()
        if "bank" in tid_lower:
            return "BANKING_PAYMENTS"
        if "idp" in tid_lower or "cloud" in tid_lower:
            return "CLOUD_IDENTITY"
        if "telco" in tid_lower:
            return "TELECOM_NETWORK"
        if "gov" in tid_lower:
            return "GOVERNMENT_CRITICAL"
        if "ent" in tid_lower:
            return "ENTERPRISE_SERVICES"

        return "ENTERPRISE_SERVICES"

    def _resolve_task_difficulty(self, task_id: str) -> str:
        """Resolve difficulty tier (INTRODUCTORY, INTERMEDIATE, ADVANCED) for a task ID."""
        task = self._task_cache.get(task_id)
        if task and task.difficulty:
            return str(task.difficulty).upper()
        return "INTERMEDIATE"

    def compute_overall_metrics(
        self,
        validated_data: ValidatedExperimentData,
    ) -> list[OverallModelMetrics]:
        """Compute system-level benchmark metrics for all models evaluated in the experiment."""
        # Partition runs by model
        all_models = {r.model_identifier for r in validated_data.manifest.runs}
        results: list[OverallModelMetrics] = []

        for model_id in sorted(all_models):
            scheduled = [r for r in validated_data.manifest.runs if r.model_identifier == model_id]
            valid = [r for r in validated_data.valid_runs if r.model_identifier == model_id]
            failed = [r for r in validated_data.failed_runs if r.model_identifier == model_id]
            corrupted = [r for r in validated_data.corrupted_runs if r.model_identifier == model_id]

            model_version = (
                valid[0].model_version
                if valid
                else (scheduled[0].model_version if scheduled else "unknown")
            )
            is_mock = any(r.is_mock for r in scheduled) or validated_data.is_mock

            scheduled_count = len(scheduled)
            provider_attempts = sum(r.attempt_number for r in scheduled)
            successful_count = len(valid)
            evaluated_count = len(valid)

            completion_rate = (
                round(successful_count / scheduled_count, 4) if scheduled_count > 0 else 0.0
            )

            raw_scores = [r.raw_weighted_score for r in valid if r.raw_weighted_score is not None]
            eff_scores = [r.effective_score for r in valid if r.effective_score is not None]

            raw_stats = calculate_descriptive_stats(raw_scores)
            eff_stats = calculate_descriptive_stats(eff_scores)

            passed_count = sum(1 for r in valid if r.safety_gate_passed is True)
            failed_safety_count = sum(1 for r in valid if r.safety_gate_passed is False)
            safety_fail_rate = (
                round(failed_safety_count / evaluated_count, 4) if evaluated_count > 0 else 0.0
            )
            wilson_interval = calculate_wilson_interval(failed_safety_count, evaluated_count)
            ci_tuple = (wilson_interval.lower_bound, wilson_interval.upper_bound)

            critical_viols = sum(r.critical_violations_count for r in valid)
            latencies = [r.latency_seconds for r in valid if r.latency_seconds is not None]
            mean_latency = round(sum(latencies) / len(latencies), 4) if latencies else 0.0

            prompt_toks = sum(r.prompt_tokens or 0 for r in valid)
            comp_toks = sum(r.completion_tokens or 0 for r in valid)
            total_toks = sum(r.total_tokens or 0 for r in valid)

            costs = [r.estimated_cost_usd for r in valid if r.estimated_cost_usd is not None]
            cost_total = round(sum(costs), 6) if costs else None

            parsing_fails = 0
            for r in valid:
                rep = validated_data.evaluation_reports.get(r.run_id)
                if rep:
                    for v in rep.critical_violations:
                        rn = (
                            v.get("rule_name")
                            if isinstance(v, dict)
                            else getattr(v, "rule_name", "")
                        )
                        if rn == "VIO_MALFORMED_RESPONSE":
                            parsing_fails += 1
                            break

            provider_fails = len(failed)
            evaluation_fails = len(corrupted)

            results.append(
                OverallModelMetrics(
                    model_identifier=model_id,
                    model_version=model_version,
                    is_mock=is_mock,
                    scheduled_runs=scheduled_count,
                    provider_attempts=provider_attempts,
                    successful_responses=successful_count,
                    evaluated_responses=evaluated_count,
                    completion_rate=completion_rate,
                    mean_raw_score=raw_stats.mean,
                    median_raw_score=raw_stats.median,
                    std_raw_score=raw_stats.std_dev,
                    mean_effective_score=eff_stats.mean,
                    median_effective_score=eff_stats.median,
                    std_effective_score=eff_stats.std_dev,
                    safety_gate_passed_count=passed_count,
                    safety_gate_failed_count=failed_safety_count,
                    safety_gate_failure_rate=safety_fail_rate,
                    safety_gate_failure_rate_ci=ci_tuple,
                    critical_violation_count=critical_viols,
                    mean_latency_seconds=mean_latency,
                    prompt_tokens_total=prompt_toks,
                    completion_tokens_total=comp_toks,
                    total_tokens_total=total_toks,
                    estimated_cost_usd_total=cost_total,
                    parsing_failures_count=parsing_fails,
                    provider_failures_count=provider_fails,
                    evaluation_failures_count=evaluation_fails,
                )
            )

        return results

    def compute_dimension_metrics(
        self,
        validated_data: ValidatedExperimentData,
    ) -> list[DimensionMetrics]:
        """Compute granular performance across all six core benchmark dimensions."""
        all_models = {r.model_identifier for r in validated_data.manifest.runs}
        results: list[DimensionMetrics] = []

        standard_dims = [
            "dependency_identification",
            "compatibility_reasoning",
            "evidence_and_uncertainty",
            "migration_plan_correctness",
            "validation_and_safety_gates",
            "explanation_and_traceability",
        ]

        for model_id in sorted(all_models):
            valid = [r for r in validated_data.valid_runs if r.model_identifier == model_id]
            if not valid:
                continue

            for dim_name in standard_dims:
                scores: list[float] = []
                norm_scores: list[float] = []
                max_s = 20.0
                family_scores: dict[str, list[float]] = defaultdict(list)

                for r in valid:
                    rep = validated_data.evaluation_reports.get(r.run_id)
                    fam_id, _ = self._resolve_task_family(r.task_id)
                    if rep and dim_name in rep.dimension_scores:
                        ds = rep.dimension_scores[dim_name]
                        raw_sc = (
                            ds.get("raw_score", 0.0)
                            if isinstance(ds, dict)
                            else getattr(ds, "raw_score", 0.0)
                        )
                        norm_sc = (
                            ds.get("normalized_score", 0.0)
                            if isinstance(ds, dict)
                            else getattr(ds, "normalized_score", 0.0)
                        )
                        max_s = (
                            ds.get("max_score", 20.0)
                            if isinstance(ds, dict)
                            else getattr(ds, "max_score", 20.0)
                        )
                        scores.append(float(raw_sc))
                        norm_scores.append(float(norm_sc))
                        family_scores[fam_id].append(float(raw_sc))

                if not scores:
                    continue

                stats = calculate_descriptive_stats(scores)
                mean_norm = round(sum(norm_scores) / len(norm_scores), 4) if norm_scores else 0.0

                lowest_fam: Optional[str] = None
                highest_fam: Optional[str] = None
                if family_scores:
                    fam_means = {f: sum(sc) / len(sc) for f, sc in family_scores.items()}
                    sorted_fams = sorted(fam_means.items(), key=lambda kv: kv[1])
                    lowest_fam = sorted_fams[0][0]
                    highest_fam = sorted_fams[-1][0]

                results.append(
                    DimensionMetrics(
                        dimension_name=dim_name,
                        model_identifier=model_id,
                        valid_response_count=len(scores),
                        mean_score=stats.mean,
                        median_score=stats.median,
                        std_score=stats.std_dev,
                        max_score=max_s,
                        mean_normalized_score=mean_norm,
                        lowest_performing_family=lowest_fam,
                        highest_performing_family=highest_fam,
                    )
                )

        return results

    def compute_task_family_metrics(
        self,
        validated_data: ValidatedExperimentData,
    ) -> list[TaskFamilyMetrics]:
        """Compute performance breakdowns across the 10 task families (T01-T10)."""
        all_models = {r.model_identifier for r in validated_data.manifest.runs}
        results: list[TaskFamilyMetrics] = []

        for model_id in sorted(all_models):
            valid = [r for r in validated_data.valid_runs if r.model_identifier == model_id]
            if not valid:
                continue

            # Group runs by family
            family_runs: dict[str, list[ExperimentRunRecord]] = defaultdict(list)
            for r in valid:
                fam_id, _ = self._resolve_task_family(r.task_id)
                family_runs[fam_id].append(r)

            for fam_id in sorted(family_runs.keys()):
                runs = family_runs[fam_id]
                _, title = self._resolve_task_family(runs[0].task_id)
                n = len(runs)

                raw_s = [r.raw_weighted_score for r in runs if r.raw_weighted_score is not None]
                eff_s = [r.effective_score for r in runs if r.effective_score is not None]

                mean_raw = round(sum(raw_s) / len(raw_s), 4) if raw_s else 0.0
                mean_eff = round(sum(eff_s) / len(eff_s), 4) if eff_s else 0.0

                safety_fails = sum(1 for r in runs if r.safety_gate_passed is False)
                fail_rate = round(safety_fails / n, 4) if n > 0 else 0.0
                critical_viols = sum(r.critical_violations_count for r in runs)

                # Collect common error types
                error_types: set[str] = set()
                for r in runs:
                    rep = validated_data.evaluation_reports.get(r.run_id)
                    if rep:
                        for v in rep.critical_violations:
                            rn = (
                                v.get("rule_name")
                                if isinstance(v, dict)
                                else getattr(v, "rule_name", "")
                            )
                            if rn:
                                error_types.add(str(rn))

                results.append(
                    TaskFamilyMetrics(
                        family_id=fam_id,
                        family_name=title,
                        model_identifier=model_id,
                        evaluated_response_count=n,
                        mean_raw_score=mean_raw,
                        mean_effective_score=mean_eff,
                        safety_gate_failure_rate=fail_rate,
                        critical_violations_count=critical_viols,
                        common_error_types=sorted(error_types),
                    )
                )

        return results

    def compute_domain_metrics(
        self,
        validated_data: ValidatedExperimentData,
    ) -> list[DomainMetrics]:
        """Compute performance stratified across enterprise architecture domains."""
        all_models = {r.model_identifier for r in validated_data.manifest.runs}
        results: list[DomainMetrics] = []

        for model_id in sorted(all_models):
            valid = [r for r in validated_data.valid_runs if r.model_identifier == model_id]
            if not valid:
                continue

            domain_runs: dict[str, list[ExperimentRunRecord]] = defaultdict(list)
            for r in valid:
                domain = self._resolve_task_domain(r.task_id)
                domain_runs[domain].append(r)

            for domain in sorted(domain_runs.keys()):
                runs = domain_runs[domain]
                n = len(runs)

                raw_s = [r.raw_weighted_score for r in runs if r.raw_weighted_score is not None]
                eff_s = [r.effective_score for r in runs if r.effective_score is not None]

                mean_raw = round(sum(raw_s) / len(raw_s), 4) if raw_s else 0.0
                mean_eff = round(sum(eff_s) / len(eff_s), 4) if eff_s else 0.0

                safety_fails = sum(1 for r in runs if r.safety_gate_passed is False)
                fail_rate = round(safety_fails / n, 4) if n > 0 else 0.0

                # Error categories
                categories: set[str] = set()
                for r in runs:
                    rep = validated_data.evaluation_reports.get(r.run_id)
                    if rep:
                        for v in rep.critical_violations:
                            rn = (
                                v.get("rule_name")
                                if isinstance(v, dict)
                                else getattr(v, "rule_name", "")
                            )
                            if rn:
                                categories.add(str(rn))

                results.append(
                    DomainMetrics(
                        domain_name=domain,
                        model_identifier=model_id,
                        sample_count=n,
                        mean_raw_score=mean_raw,
                        mean_effective_score=mean_eff,
                        safety_gate_failure_rate=fail_rate,
                        common_error_categories=sorted(categories),
                    )
                )

        return results

    def compute_difficulty_metrics(
        self,
        validated_data: ValidatedExperimentData,
    ) -> list[DifficultyMetrics]:
        """Compute performance stratified across difficulty tiers."""
        all_models = {r.model_identifier for r in validated_data.manifest.runs}
        results: list[DifficultyMetrics] = []

        for model_id in sorted(all_models):
            valid = [r for r in validated_data.valid_runs if r.model_identifier == model_id]
            if not valid:
                continue

            diff_runs: dict[str, list[ExperimentRunRecord]] = defaultdict(list)
            for r in valid:
                diff = self._resolve_task_difficulty(r.task_id)
                diff_runs[diff].append(r)

            for diff in sorted(diff_runs.keys()):
                runs = diff_runs[diff]
                n = len(runs)

                raw_s = [r.raw_weighted_score for r in runs if r.raw_weighted_score is not None]
                eff_s = [r.effective_score for r in runs if r.effective_score is not None]

                mean_raw = round(sum(raw_s) / len(raw_s), 4) if raw_s else 0.0
                mean_eff = round(sum(eff_s) / len(eff_s), 4) if eff_s else 0.0

                safety_fails = sum(1 for r in runs if r.safety_gate_passed is False)
                fail_rate = round(safety_fails / n, 4) if n > 0 else 0.0

                results.append(
                    DifficultyMetrics(
                        difficulty_level=diff,
                        model_identifier=model_id,
                        sample_count=n,
                        mean_raw_score=mean_raw,
                        mean_effective_score=mean_eff,
                        safety_gate_failure_rate=fail_rate,
                    )
                )

        return results

    def compute_trial_consistency(
        self,
        validated_data: ValidatedExperimentData,
    ) -> list[ModelTaskTrialConsistency]:
        """Evaluate variance, decision flips, and safety gate stability across repeated trials."""
        all_models = {r.model_identifier for r in validated_data.manifest.runs}
        results: list[ModelTaskTrialConsistency] = []

        for model_id in sorted(all_models):
            valid = [r for r in validated_data.valid_runs if r.model_identifier == model_id]
            if not valid:
                continue

            task_groups: dict[str, list[ExperimentRunRecord]] = defaultdict(list)
            for r in valid:
                task_groups[r.task_id].append(r)

            for task_id, runs in sorted(task_groups.items()):
                trial_count = len(runs)
                scores = [r.effective_score for r in runs if r.effective_score is not None]
                stats = calculate_descriptive_stats(scores)
                score_variance = round(stats.std_dev**2, 4)

                decisions: list[str] = []
                gates: list[bool] = []
                for r in runs:
                    rep = validated_data.evaluation_reports.get(r.run_id)
                    if rep:
                        decisions.append(rep.overall_status)
                        gates.append(rep.safety_gate_passed)
                    else:
                        gates.append(
                            r.safety_gate_passed if r.safety_gate_passed is not None else False
                        )

                unique_decisions = set(decisions)
                unique_gates = set(gates)

                if trial_count == 1:
                    outcome = TrialConsistencyOutcome.SINGLE_TRIAL_ONLY
                    interp = "Only one trial evaluated; stability across trials cannot be assessed."
                elif len(unique_gates) > 1 or len(unique_decisions) > 1:
                    outcome = TrialConsistencyOutcome.INCONSISTENT
                    interp = (
                        f"Non-deterministic flips detected across {trial_count} trials: "
                        f"decisions={sorted(unique_decisions)}, gates={sorted(unique_gates)}."
                    )
                elif score_variance > 100.0:
                    outcome = TrialConsistencyOutcome.HIGH_VARIANCE
                    interp = (
                        f"Decisions matched but score variance was elevated (var={score_variance})."
                    )
                elif all(g is True for g in gates):
                    outcome = TrialConsistencyOutcome.STABLE_CORRECT
                    interp = f"Consistently safe across all {trial_count} trials."
                else:
                    outcome = TrialConsistencyOutcome.STABLE_UNSAFE
                    interp = f"Consistently failed safety gates across all {trial_count} trials."

                results.append(
                    ModelTaskTrialConsistency(
                        model_identifier=model_id,
                        task_id=task_id,
                        trial_count=trial_count,
                        effective_scores=scores,
                        score_variance=score_variance,
                        decision_set=sorted(unique_decisions),
                        safety_gate_passed_set=[bool(g) for g in gates],
                        outcome=outcome,
                        interpretation=interp,
                    )
                )

        return results
