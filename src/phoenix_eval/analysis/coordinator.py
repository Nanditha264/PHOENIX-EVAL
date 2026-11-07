"""Phase 5 Analysis Coordinator orchestrating benchmark execution analysis workflows.

Coordinates ingestion, integrity validation, comparability checks, multidimensional metrics,
failure intelligence, recurring pattern detection, paired-case counterfactuals,
metamorphic relation verification, statistical inference, artifact persistence, and report generation.
"""

from pathlib import Path
from typing import Any, Optional

from phoenix_eval.analysis.comparability import ExperimentComparabilityEvaluator
from phoenix_eval.analysis.failures import FailureIntelligenceEngine
from phoenix_eval.analysis.ingestion import (
    ExperimentIngestionValidator,
)
from phoenix_eval.analysis.metamorphic import MetamorphicAnalyzer
from phoenix_eval.analysis.paired import PairedCaseAnalyzer
from phoenix_eval.analysis.patterns import FailurePatternDetector
from phoenix_eval.analysis.performance import BenchmarkPerformanceAnalyzer
from phoenix_eval.analysis.report_generator import ResearchReportGenerator
from phoenix_eval.analysis.schemas import (
    AnalysisManifest,
    IngestionReport,
    MetamorphicAnalysisItem,
    PairedCaseAnalysisItem,
    PairedModelComparison,
)
from phoenix_eval.analysis.statistics import calculate_paired_comparison
from phoenix_eval.analysis.storage import AnalysisStorageManager
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.utils.identifiers import generate_id

logger = get_logger("analysis.coordinator")


class Phase5AnalysisCoordinator:
    """Master coordinator executing end-to-end Phase 5 analysis and reporting workflows."""

    def __init__(self, paths: Optional[ProjectPaths] = None) -> None:
        self.paths = paths or get_paths()
        self.storage = AnalysisStorageManager(self.paths)
        self.ingestion_validator = ExperimentIngestionValidator(self.paths)
        self.comparability_evaluator = ExperimentComparabilityEvaluator()
        self.performance_analyzer = BenchmarkPerformanceAnalyzer(self.paths)
        self.failure_engine = FailureIntelligenceEngine()
        self.pattern_detector = FailurePatternDetector(self.performance_analyzer)
        self.paired_analyzer = PairedCaseAnalyzer(self.paths)
        self.metamorphic_analyzer = MetamorphicAnalyzer(self.paths)
        self.report_generator = ResearchReportGenerator(self.paths)

    def validate_experiment(self, experiment_id: str) -> IngestionReport:
        """Audit and validate experiment artifact integrity and provenance."""
        data = self.ingestion_validator.ingest_experiment(experiment_id)
        self.storage.persist_ingestion_report(data.ingestion_report)
        return data.ingestion_report

    def failure_analysis(self, experiment_id: str) -> dict[str, Any]:
        """Extract failure incidents and detect recurring failure patterns."""
        data = self.ingestion_validator.ingest_experiment(experiment_id)
        incidents = self.failure_engine.extract_incidents(data)
        patterns = self.pattern_detector.detect_patterns(incidents, data)
        freq_matrix = self.failure_engine.compute_failure_frequency_matrix(incidents)

        inc_path, patt_path = self.storage.persist_failure_intelligence(
            experiment_id=experiment_id,
            incidents=incidents,
            patterns=patterns,
            frequency_matrix=freq_matrix,
        )

        return {
            "experiment_id": experiment_id,
            "total_incidents": len(incidents),
            "total_patterns": len(patterns),
            "incidents": incidents,
            "patterns": patterns,
            "frequency_matrix": freq_matrix,
            "incidents_file": str(inc_path),
            "patterns_file": str(patt_path),
        }

    def paired_analysis(self, experiment_id: str) -> list[PairedCaseAnalysisItem]:
        """Execute counterfactual paired-case sensitivity analysis."""
        data = self.ingestion_validator.ingest_experiment(experiment_id)
        items = self.paired_analyzer.analyze_experiment(data)
        self.storage.persist_paired_analysis(experiment_id, items)
        return items

    def metamorphic_analysis(self, experiment_id: str) -> list[MetamorphicAnalysisItem]:
        """Verify metamorphic relation invariants (MR1-MR6) on experiment outputs."""
        data = self.ingestion_validator.ingest_experiment(experiment_id)
        items = self.metamorphic_analyzer.analyze_experiment(data)
        self.storage.persist_metamorphic_analysis(experiment_id, items)
        return items

    def analyze_experiment(
        self,
        experiment_id: str,
        generate_report: bool = True,
        output_report_path: Optional[Path] = None,
    ) -> AnalysisManifest:
        """Run complete end-to-end scientific analysis on an experiment campaign."""
        logger.info("Executing comprehensive Phase 5 analysis on experiment '%s'", experiment_id)

        # 1. Ingestion & artifact verification
        data = self.ingestion_validator.ingest_experiment(experiment_id)
        self.storage.persist_ingestion_report(data.ingestion_report)

        # 2. Multidimensional performance metrics
        overall = self.performance_analyzer.compute_overall_metrics(data)
        dimensions = self.performance_analyzer.compute_dimension_metrics(data)
        families = self.performance_analyzer.compute_task_family_metrics(data)
        domains = self.performance_analyzer.compute_domain_metrics(data)
        difficulties = self.performance_analyzer.compute_difficulty_metrics(data)
        consistency = self.performance_analyzer.compute_trial_consistency(data)

        self.storage.persist_performance_metrics(
            experiment_id=experiment_id,
            overall=overall,
            dimensions=dimensions,
            families=families,
            domains=domains,
            difficulties=difficulties,
            consistency=consistency,
        )

        # 3. Failure intelligence & patterns
        incidents = self.failure_engine.extract_incidents(data)
        patterns = self.pattern_detector.detect_patterns(incidents, data)
        freq_matrix = self.failure_engine.compute_failure_frequency_matrix(incidents)

        self.storage.persist_failure_intelligence(
            experiment_id=experiment_id,
            incidents=incidents,
            patterns=patterns,
            frequency_matrix=freq_matrix,
        )

        # 4. Paired-case counterfactual sensitivity
        paired_items = self.paired_analyzer.analyze_experiment(data)
        self.storage.persist_paired_analysis(experiment_id, paired_items)

        # 5. Metamorphic relation testing
        meta_items = self.metamorphic_analyzer.analyze_experiment(data)
        self.storage.persist_metamorphic_analysis(experiment_id, meta_items)

        # 6. Statistical comparisons between models on common tasks
        comparisons: list[PairedModelComparison] = []
        all_models = sorted({r.model_identifier for r in data.valid_runs})
        for i in range(len(all_models)):
            for j in range(i + 1, len(all_models)):
                m_a = all_models[i]
                m_b = all_models[j]

                # Aggregate trials per task (mean trial score per task)
                task_scores_a: dict[str, list[float]] = {}
                for r in data.valid_runs:
                    if r.model_identifier == m_a and r.effective_score is not None:
                        task_scores_a.setdefault(r.task_id, []).append(r.effective_score)

                task_scores_b: dict[str, list[float]] = {}
                for r in data.valid_runs:
                    if r.model_identifier == m_b and r.effective_score is not None:
                        task_scores_b.setdefault(r.task_id, []).append(r.effective_score)

                scores_a = {t: float(sum(s) / len(s)) for t, s in task_scores_a.items()}
                scores_b = {t: float(sum(s) / len(s)) for t, s in task_scores_b.items()}

                trials_a = sum(len(s) for s in task_scores_a.values())
                trials_b = sum(len(s) for s in task_scores_b.values())

                comp = calculate_paired_comparison(
                    model_a_scores=scores_a,
                    model_b_scores=scores_b,
                    model_a_name=m_a,
                    model_b_name=m_b,
                    model_a_trial_count=trials_a,
                    model_b_trial_count=trials_b,
                )
                comparisons.append(comp)

        self.storage.persist_statistics(
            experiment_id=experiment_id,
            paired_comparisons=comparisons,
        )

        # 7. Export CSV tables
        self.storage.export_csv_tables(
            overall=overall,
            dimensions=dimensions,
            families=families,
            domains=domains,
            difficulties=difficulties,
            patterns=patterns,
            paired_cases=paired_items,
            metamorphic_items=meta_items,
        )

        # 8. Generate 26-section research report
        if generate_report:
            self.report_generator.generate_report(
                validated_data=data,
                overall=overall,
                dimensions=dimensions,
                families=families,
                domains=domains,
                difficulties=difficulties,
                consistency=consistency,
                incidents=incidents,
                patterns=patterns,
                paired_items=paired_items,
                metamorphic_items=meta_items,
                comparisons=comparisons,
                output_path=output_report_path,
            )

        # 9. Persist analysis manifest with cryptographic input hashes
        analysis_id = generate_id("anal")
        exp_dir = self.paths.results_dir / "experiments" / experiment_id
        input_files = [
            exp_dir / "experiment_manifest.json",
            exp_dir / "runs.jsonl",
        ]

        summary_dict = {
            "experiment_id": experiment_id,
            "models_evaluated": [m.model_identifier for m in overall],
            "total_runs_evaluated": sum(m.evaluated_responses for m in overall),
            "total_incidents": len(incidents),
            "total_patterns": len(patterns),
            "is_mock": data.is_mock,
        }

        manifest_path = self.storage.persist_analysis_manifest(
            analysis_id=analysis_id,
            experiment_ids=[experiment_id],
            dataset_fingerprints=[data.manifest.dataset_fingerprint or "unknown"],
            input_files=input_files,
            summary=summary_dict,
        )

        logger.info("Phase 5 analysis complete. Manifest: '%s'", manifest_path)
        manifest_data = read_json(manifest_path)
        return AnalysisManifest.model_validate(manifest_data)

    def analyze_all(self) -> list[AnalysisManifest]:
        """Scan results/experiments/ and run analysis on all discovered completed experiments."""
        exp_root = self.paths.results_dir / "experiments"
        if not exp_root.is_dir():
            logger.warning("No experiments directory found at '%s'", exp_root)
            return []

        manifests: list[AnalysisManifest] = []
        for exp_dir in sorted(exp_root.iterdir()):
            if exp_dir.is_dir() and (exp_dir / "experiment_manifest.json").is_file():
                try:
                    res = self.analyze_experiment(exp_dir.name)
                    manifests.append(res)
                except Exception as err:
                    logger.error("Failed to analyze experiment '%s': %s", exp_dir.name, err)

        return manifests

    def generate_research_report(
        self,
        experiment_id: str,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Directly produce PHOENIX_EVAL_PHASE_5_RESEARCH_REPORT.md for a given experiment."""
        self.analyze_experiment(experiment_id, generate_report=True, output_report_path=output_path)
        target = output_path or (self.paths.root / "PHOENIX_EVAL_PHASE_5_RESEARCH_REPORT.md")
        return target

    def inspect_analysis(self, analysis_id: str) -> dict[str, Any]:
        """Load and display the analysis manifest and summary for a given analysis ID."""
        # Find manifest file
        manifest_file = self.paths.analysis_dir / f"manifest_{analysis_id}.json"
        if not manifest_file.is_file():
            # Search by prefix or direct name
            candidates = list(self.paths.analysis_dir.glob(f"*{analysis_id}*.json"))
            if candidates:
                manifest_file = candidates[0]
            else:
                raise FileNotFoundError(
                    f"Analysis manifest not found for '{analysis_id}' in '{self.paths.analysis_dir}'"
                )

        data = read_json(manifest_file)
        return dict(data) if isinstance(data, dict) else {}
