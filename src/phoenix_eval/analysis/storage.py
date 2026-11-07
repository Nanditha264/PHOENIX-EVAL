"""Storage manager and tabular results exporter for PHOENIX-EVAL Phase 5.

Persists validated analysis artifacts, failure intelligence records, statistical summaries,
and exports publication-ready CSV and JSON datasets under results/.
"""

import csv
from pathlib import Path
from typing import Any, Optional

from phoenix_eval.analysis.schemas import (
    AnalysisManifest,
    ComparabilityAssessment,
    DifficultyMetrics,
    DimensionMetrics,
    DomainMetrics,
    FailureIncident,
    FailurePattern,
    IngestionReport,
    MetamorphicAnalysisItem,
    ModelTaskTrialConsistency,
    OverallModelMetrics,
    PairedCaseAnalysisItem,
    PairedModelComparison,
    TaskFamilyMetrics,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import write_json
from phoenix_eval.utils.hashing import compute_sha256

logger = get_logger("analysis.storage")


class AnalysisStorageManager:
    """Manages persistence of analysis artifacts and tabular metric exports."""

    def __init__(self, paths: Optional[ProjectPaths] = None) -> None:
        self.paths = paths or get_paths()
        self.paths.ensure_directories()

    def persist_ingestion_report(self, report: IngestionReport) -> Path:
        """Persist an ingestion validation report under results/ingestion/."""
        out_path = self.paths.ingestion_dir / f"ingestion_{report.experiment_id}.json"
        write_json(out_path, report.model_dump(mode="json"))
        logger.info("Persisted ingestion report to '%s'", out_path)
        return out_path

    def persist_comparability_assessment(self, assessment: ComparabilityAssessment) -> Path:
        """Persist comparability assessment under results/analysis/."""
        out_path = self.paths.analysis_dir / f"comparability_{assessment.assessment_id}.json"
        write_json(out_path, assessment.model_dump(mode="json"))
        logger.info("Persisted comparability assessment to '%s'", out_path)
        return out_path

    def persist_performance_metrics(
        self,
        experiment_id: str,
        overall: list[OverallModelMetrics],
        dimensions: list[DimensionMetrics],
        families: list[TaskFamilyMetrics],
        domains: list[DomainMetrics],
        difficulties: list[DifficultyMetrics],
        consistency: list[ModelTaskTrialConsistency],
    ) -> Path:
        """Persist multidimensional benchmark metrics under results/analysis/."""
        payload = {
            "experiment_id": experiment_id,
            "overall_metrics": [m.model_dump(mode="json") for m in overall],
            "dimension_metrics": [m.model_dump(mode="json") for m in dimensions],
            "task_family_metrics": [m.model_dump(mode="json") for m in families],
            "domain_metrics": [m.model_dump(mode="json") for m in domains],
            "difficulty_metrics": [m.model_dump(mode="json") for m in difficulties],
            "trial_consistency": [m.model_dump(mode="json") for m in consistency],
        }
        out_path = self.paths.analysis_dir / f"metrics_{experiment_id}.json"
        write_json(out_path, payload)
        logger.info("Persisted performance metrics to '%s'", out_path)
        return out_path

    def persist_failure_intelligence(
        self,
        experiment_id: str,
        incidents: list[FailureIncident],
        patterns: list[FailurePattern],
        frequency_matrix: dict[str, dict[str, int]],
    ) -> tuple[Path, Path]:
        """Persist failure incidents, recurring patterns, and frequency matrix."""
        incidents_payload = {
            "experiment_id": experiment_id,
            "total_incidents": len(incidents),
            "incidents": [inc.model_dump(mode="json") for inc in incidents],
            "frequency_matrix": frequency_matrix,
        }
        incidents_path = self.paths.failure_intelligence_dir / f"incidents_{experiment_id}.json"
        write_json(incidents_path, incidents_payload)

        patterns_payload = {
            "experiment_id": experiment_id,
            "total_patterns": len(patterns),
            "patterns": [p.model_dump(mode="json") for p in patterns],
        }
        patterns_path = self.paths.failure_intelligence_dir / f"patterns_{experiment_id}.json"
        write_json(patterns_path, patterns_payload)

        logger.info(
            "Persisted failure intelligence to '%s' and '%s'", incidents_path, patterns_path
        )
        return incidents_path, patterns_path

    def persist_paired_analysis(
        self,
        experiment_id: str,
        items: list[PairedCaseAnalysisItem],
    ) -> Path:
        """Persist counterfactual paired analysis under results/paired_analysis/."""
        payload = {
            "experiment_id": experiment_id,
            "total_cases": len(items),
            "cases": [item.model_dump(mode="json") for item in items],
        }
        out_path = self.paths.paired_analysis_dir / f"paired_{experiment_id}.json"
        write_json(out_path, payload)
        logger.info("Persisted paired analysis to '%s'", out_path)
        return out_path

    def persist_metamorphic_analysis(
        self,
        experiment_id: str,
        items: list[MetamorphicAnalysisItem],
    ) -> Path:
        """Persist metamorphic relation analysis under results/metamorphic_analysis/."""
        payload = {
            "experiment_id": experiment_id,
            "total_tests": len(items),
            "tests": [item.model_dump(mode="json") for item in items],
        }
        out_path = self.paths.metamorphic_analysis_dir / f"metamorphic_{experiment_id}.json"
        write_json(out_path, payload)
        logger.info("Persisted metamorphic analysis to '%s'", out_path)
        return out_path

    def persist_statistics(
        self,
        experiment_id: str,
        paired_comparisons: list[PairedModelComparison],
        metadata: Optional[dict[str, Any]] = None,
    ) -> Path:
        """Persist inferential statistical tests and comparisons under results/statistics/."""
        payload = {
            "experiment_id": experiment_id,
            "paired_comparisons": [c.model_dump(mode="json") for c in paired_comparisons],
            "metadata": metadata or {},
        }
        out_path = self.paths.statistics_dir / f"statistics_{experiment_id}.json"
        write_json(out_path, payload)
        logger.info("Persisted statistics to '%s'", out_path)
        return out_path

    def persist_analysis_manifest(
        self,
        analysis_id: str,
        experiment_ids: list[str],
        dataset_fingerprints: list[str],
        input_files: list[Path],
        summary: dict[str, Any],
    ) -> Path:
        """Persist authoritative AnalysisManifest with cryptographic input artifact hashes."""
        input_hashes: dict[str, str] = {}
        for f in input_files:
            if f.is_file():
                try:
                    input_hashes[f.name] = compute_sha256(f.read_bytes())
                except Exception as err:
                    logger.warning("Could not hash input file '%s': %s", f, err)

        manifest = AnalysisManifest(
            analysis_id=analysis_id,
            source_experiment_ids=experiment_ids,
            dataset_fingerprints=dataset_fingerprints,
            benchmark_version="5.0.0",
            evaluator_version="3.0.0",
            analysis_code_version="5.0.0",
            input_artifact_hashes=input_hashes,
            summary=summary,
        )
        out_path = self.paths.analysis_dir / f"manifest_{analysis_id}.json"
        write_json(out_path, manifest.model_dump(mode="json"))
        logger.info("Persisted analysis manifest to '%s'", out_path)
        return out_path

    def export_csv_tables(
        self,
        overall: list[OverallModelMetrics],
        dimensions: list[DimensionMetrics],
        families: list[TaskFamilyMetrics],
        domains: list[DomainMetrics],
        difficulties: list[DifficultyMetrics],
        patterns: list[FailurePattern],
        paired_cases: Optional[list[PairedCaseAnalysisItem]] = None,
        metamorphic_items: Optional[list[MetamorphicAnalysisItem]] = None,
    ) -> dict[str, Path]:
        """Export publication-ready CSV tables under results/exports/."""
        exports: dict[str, Path] = {}

        # 1. Overall metrics CSV
        overall_csv = self.paths.exports_dir / "overall_metrics.csv"
        with overall_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "model_identifier",
                    "model_version",
                    "is_mock",
                    "completion_rate",
                    "mean_raw_score",
                    "std_raw_score",
                    "mean_effective_score",
                    "std_effective_score",
                    "safety_gate_passed",
                    "safety_gate_failed",
                    "safety_failure_rate",
                    "safety_failure_rate_ci_lower",
                    "safety_failure_rate_ci_upper",
                    "critical_violations",
                    "mean_latency_s",
                    "total_tokens",
                    "cost_usd",
                ]
            )
            for m in overall:
                writer.writerow(
                    [
                        m.model_identifier,
                        m.model_version,
                        m.is_mock,
                        m.completion_rate,
                        m.mean_raw_score,
                        m.std_raw_score,
                        m.mean_effective_score,
                        m.std_effective_score,
                        m.safety_gate_passed_count,
                        m.safety_gate_failed_count,
                        m.safety_gate_failure_rate,
                        m.safety_gate_failure_rate_ci[0],
                        m.safety_gate_failure_rate_ci[1],
                        m.critical_violation_count,
                        m.mean_latency_seconds,
                        m.total_tokens_total,
                        m.estimated_cost_usd_total
                        if m.estimated_cost_usd_total is not None
                        else "",
                    ]
                )
        exports["overall_metrics"] = overall_csv

        # 2. Dimension metrics CSV
        dim_csv = self.paths.exports_dir / "dimension_metrics.csv"
        with dim_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "dimension_name",
                    "model_identifier",
                    "valid_response_count",
                    "mean_score",
                    "std_score",
                    "max_score",
                    "mean_normalized_score",
                    "lowest_performing_family",
                    "highest_performing_family",
                ]
            )
            for d in dimensions:
                writer.writerow(
                    [
                        d.dimension_name,
                        d.model_identifier,
                        d.valid_response_count,
                        d.mean_score,
                        d.std_score,
                        d.max_score,
                        d.mean_normalized_score,
                        d.lowest_performing_family or "",
                        d.highest_performing_family or "",
                    ]
                )
        exports["dimension_metrics"] = dim_csv

        # 3. Task family metrics CSV
        fam_csv = self.paths.exports_dir / "task_family_metrics.csv"
        with fam_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "family_id",
                    "family_name",
                    "model_identifier",
                    "evaluated_count",
                    "mean_raw_score",
                    "mean_effective_score",
                    "safety_failure_rate",
                    "critical_violations_count",
                    "common_error_types",
                ]
            )
            for fam in families:
                writer.writerow(
                    [
                        fam.family_id,
                        fam.family_name,
                        fam.model_identifier,
                        fam.evaluated_response_count,
                        fam.mean_raw_score,
                        fam.mean_effective_score,
                        fam.safety_gate_failure_rate,
                        fam.critical_violations_count,
                        ";".join(fam.common_error_types),
                    ]
                )
        exports["task_family_metrics"] = fam_csv

        # 4. Domain metrics CSV
        dom_csv = self.paths.exports_dir / "domain_metrics.csv"
        with dom_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "domain_name",
                    "model_identifier",
                    "sample_count",
                    "mean_raw_score",
                    "mean_effective_score",
                    "safety_failure_rate",
                    "common_errors",
                ]
            )
            for dom in domains:
                writer.writerow(
                    [
                        dom.domain_name,
                        dom.model_identifier,
                        dom.sample_count,
                        dom.mean_raw_score,
                        dom.mean_effective_score,
                        dom.safety_gate_failure_rate,
                        ";".join(dom.common_error_categories),
                    ]
                )
        exports["domain_metrics"] = dom_csv

        # 5. Difficulty metrics CSV
        diff_csv = self.paths.exports_dir / "difficulty_metrics.csv"
        with diff_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "difficulty_level",
                    "model_identifier",
                    "sample_count",
                    "mean_raw_score",
                    "mean_effective_score",
                    "safety_failure_rate",
                ]
            )
            for diff in difficulties:
                writer.writerow(
                    [
                        diff.difficulty_level,
                        diff.model_identifier,
                        diff.sample_count,
                        diff.mean_raw_score,
                        diff.mean_effective_score,
                        diff.safety_gate_failure_rate,
                    ]
                )
        exports["difficulty_metrics"] = diff_csv

        # 6. Failure patterns CSV
        patt_csv = self.paths.exports_dir / "failure_patterns.csv"
        with patt_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "pattern_id",
                    "pattern_name",
                    "model_identifier",
                    "category",
                    "scope",
                    "severity",
                    "confidence",
                    "affected_runs",
                    "affected_tasks",
                    "interpretation",
                ]
            )
            for p in patterns:
                writer.writerow(
                    [
                        p.pattern_id,
                        p.pattern_name,
                        p.model_identifier,
                        p.category.value,
                        p.scope.value,
                        p.severity.value,
                        p.confidence,
                        p.number_of_affected_runs,
                        len(p.supporting_task_ids),
                        p.suggested_interpretation,
                    ]
                )
        exports["failure_patterns"] = patt_csv

        # 7. Paired-case sensitivity CSV
        if paired_cases is not None:
            paired_csv = self.paths.exports_dir / "paired_case_sensitivity.csv"
            with paired_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "pair_id",
                        "pair_type",
                        "model_identifier",
                        "task_a_id",
                        "task_b_id",
                        "decision_a",
                        "decision_b",
                        "safety_gate_passed_a",
                        "safety_gate_passed_b",
                        "effective_score_a",
                        "effective_score_b",
                        "perturbed_property",
                        "classification",
                        "reasoning",
                    ]
                )
                for pc in paired_cases:
                    writer.writerow(
                        [
                            pc.pair_id,
                            pc.pair_type.value
                            if hasattr(pc.pair_type, "value")
                            else str(pc.pair_type),
                            pc.model_identifier,
                            pc.task_a_id,
                            pc.task_b_id,
                            pc.decision_a or "",
                            pc.decision_b or "",
                            pc.safety_gate_passed_a,
                            pc.safety_gate_passed_b,
                            pc.effective_score_a,
                            pc.effective_score_b,
                            pc.perturbed_property,
                            pc.classification.value
                            if hasattr(pc.classification, "value")
                            else str(pc.classification),
                            pc.reasoning,
                        ]
                    )
            exports["paired_case_sensitivity"] = paired_csv

        # 8. Metamorphic test results CSV
        if metamorphic_items is not None:
            meta_csv = self.paths.exports_dir / "metamorphic_results.csv"
            with meta_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "relation_type",
                        "model_identifier",
                        "test_id",
                        "description",
                        "outcome",
                        "baseline_run_id",
                        "transformed_run_id",
                        "details",
                    ]
                )
                for mi in metamorphic_items:
                    writer.writerow(
                        [
                            mi.relation_type.value
                            if hasattr(mi.relation_type, "value")
                            else str(mi.relation_type),
                            mi.model_identifier,
                            mi.test_id,
                            mi.description,
                            mi.outcome.value if hasattr(mi.outcome, "value") else str(mi.outcome),
                            mi.baseline_run_id,
                            mi.transformed_run_id,
                            mi.details,
                        ]
                    )
            exports["metamorphic_results"] = meta_csv

        logger.info("Exported %d CSV tables to '%s'", len(exports), self.paths.exports_dir)
        return exports
