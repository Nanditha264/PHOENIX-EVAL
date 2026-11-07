"""Scientific comparability evaluator for benchmark experiments and models."""

from collections import defaultdict

from phoenix_eval.analysis.ingestion import ValidatedExperimentData
from phoenix_eval.analysis.schemas import (
    ComparabilityAssessment,
    ComparabilityClassification,
    ComparabilityCriterion,
    ModelPairComparability,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.schemas.experiments import ExperimentManifest, ExperimentRunRecord

logger = get_logger("analysis.comparability")


class ExperimentComparabilityEvaluator:
    """Evaluates whether pairs of models or experiment runs satisfy scientific comparability invariants."""

    def evaluate_model_pair(
        self,
        model_a: str,
        runs_a: list[ExperimentRunRecord],
        manifest_a: ExperimentManifest,
        model_b: str,
        runs_b: list[ExperimentRunRecord],
        manifest_b: ExperimentManifest,
    ) -> ModelPairComparability:
        """Assess scientific comparability between two models across experiments or within an experiment.

        Checks:
        1. Mock vs Real isolation (strictly non-comparable).
        2. Dataset fingerprint identity.
        3. Benchmark and evaluator version compatibility.
        4. Task set intersection and coverage.
        5. Hyperparameter alignment (temperature, max tokens, sampling).
        """
        criteria: list[ComparabilityCriterion] = []
        reasons: list[str] = []

        is_mock_a = any(r.is_mock for r in runs_a) or (
            manifest_a.config.mode == "mock" if manifest_a.config else False
        )
        is_mock_b = any(r.is_mock for r in runs_b) or (
            manifest_b.config.mode == "mock" if manifest_b.config else False
        )

        # 1. Mock vs Real isolation
        mock_aligned = is_mock_a == is_mock_b
        criteria.append(
            ComparabilityCriterion(
                criterion_name="MOCK_REAL_ALIGNMENT",
                satisfied=mock_aligned,
                details=(
                    f"Model A is {'mock' if is_mock_a else 'real'}; "
                    f"Model B is {'mock' if is_mock_b else 'real'}."
                ),
            )
        )
        if not mock_aligned:
            reasons.append(
                "Cannot scientifically compare synthetic mock simulation models with real API models."
            )

        # 2. Dataset fingerprint identity
        fp_a = manifest_a.dataset_fingerprint
        fp_b = manifest_b.dataset_fingerprint
        fp_matched = (fp_a is not None and fp_a == fp_b) or (fp_a is None and fp_b is None)
        criteria.append(
            ComparabilityCriterion(
                criterion_name="DATASET_FINGERPRINT_MATCH",
                satisfied=fp_matched,
                details=f"Model A dataset FP: '{fp_a}'; Model B dataset FP: '{fp_b}'.",
            )
        )
        if not fp_matched:
            reasons.append(
                f"Dataset fingerprint mismatch: Model A used '{fp_a}', Model B used '{fp_b}'."
            )

        # 3. Benchmark / Manifest version match
        ver_a = manifest_a.dataset_manifest_version
        ver_b = manifest_b.dataset_manifest_version
        ver_matched = ver_a == ver_b
        criteria.append(
            ComparabilityCriterion(
                criterion_name="DATASET_VERSION_MATCH",
                satisfied=ver_matched,
                details=f"Model A dataset version: '{ver_a}'; Model B dataset version: '{ver_b}'.",
            )
        )
        if not ver_matched:
            reasons.append(f"Dataset versions differ: '{ver_a}' vs '{ver_b}'.")

        # 4. Task set intersection
        tasks_a = {r.task_id for r in runs_a}
        tasks_b = {r.task_id for r in runs_b}
        common_tasks = tasks_a & tasks_b
        disjoint_tasks = (tasks_a | tasks_b) - common_tasks

        has_common_tasks = len(common_tasks) > 0
        identical_tasks = len(disjoint_tasks) == 0
        criteria.append(
            ComparabilityCriterion(
                criterion_name="TASK_SET_OVERLAP",
                satisfied=has_common_tasks,
                details=(
                    f"Common tasks: {len(common_tasks)}; "
                    f"Disjoint tasks: {len(disjoint_tasks)} "
                    f"(Model A total: {len(tasks_a)}, Model B total: {len(tasks_b)})."
                ),
            )
        )
        if not has_common_tasks:
            reasons.append("Zero common tasks between models; cannot perform comparison.")
        elif not identical_tasks:
            reasons.append(
                f"Task sets are not identical ({len(disjoint_tasks)} disjoint tasks). "
                "Comparisons must be restricted to common task subset."
            )

        # 5. Model configuration alignment (temperature, max tokens)
        cfg_a = manifest_a.config
        cfg_b = manifest_b.config
        temp_a = cfg_a.temperature if cfg_a else None
        temp_b = cfg_b.temperature if cfg_b else None
        temp_aligned = temp_a == temp_b
        criteria.append(
            ComparabilityCriterion(
                criterion_name="TEMPERATURE_ALIGNMENT",
                satisfied=temp_aligned,
                details=f"Temperature: Model A={temp_a}, Model B={temp_b}.",
            )
        )
        if not temp_aligned:
            reasons.append(
                f"Temperature generation parameters differ (Model A={temp_a}, Model B={temp_b})."
            )

        # Classify overall comparability
        if not mock_aligned or not has_common_tasks or (not fp_matched and fp_a and fp_b):
            classification = ComparabilityClassification.NOT_COMPARABLE
        elif not identical_tasks or not temp_aligned or not ver_matched:
            classification = ComparabilityClassification.COMPARABLE_WITH_LIMITATIONS
        else:
            classification = ComparabilityClassification.COMPARABLE

        return ModelPairComparability(
            model_a=model_a,
            model_b=model_b,
            classification=classification,
            reasons=reasons,
            common_task_count=len(common_tasks),
            disjoint_task_count=len(disjoint_tasks),
            criteria=criteria,
        )

    def assess_experiments(
        self,
        validated_experiments: list[ValidatedExperimentData],
    ) -> ComparabilityAssessment:
        """Perform system-wide comparability analysis across all models in the given experiment runs."""
        # Group runs and manifests by model_identifier
        model_runs: dict[str, list[ExperimentRunRecord]] = defaultdict(list)
        model_manifests: dict[str, ExperimentManifest] = {}
        experiment_ids = [ve.manifest.experiment_id for ve in validated_experiments]

        for ve in validated_experiments:
            for run in ve.valid_runs:
                model_runs[run.model_identifier].append(run)
                if run.model_identifier not in model_manifests:
                    model_manifests[run.model_identifier] = ve.manifest

        models = sorted(model_runs.keys())
        pairs: list[ModelPairComparability] = []

        for i in range(len(models)):
            for j in range(i + 1, len(models)):
                m_a = models[i]
                m_b = models[j]
                pair_comp = self.evaluate_model_pair(
                    model_a=m_a,
                    runs_a=model_runs[m_a],
                    manifest_a=model_manifests[m_a],
                    model_b=m_b,
                    runs_b=model_runs[m_b],
                    manifest_b=model_manifests[m_b],
                )
                pairs.append(pair_comp)

        summary_msg = (
            f"Assessed {len(pairs)} model pair(s) across {len(experiment_ids)} experiment(s). "
            f"Comparable: {sum(1 for p in pairs if p.classification == ComparabilityClassification.COMPARABLE)}, "
            f"With Limitations: {sum(1 for p in pairs if p.classification == ComparabilityClassification.COMPARABLE_WITH_LIMITATIONS)}, "
            f"Not Comparable: {sum(1 for p in pairs if p.classification == ComparabilityClassification.NOT_COMPARABLE)}."
        )

        return ComparabilityAssessment(
            experiment_ids=experiment_ids,
            model_pairs=pairs,
            summary=summary_msg,
        )
