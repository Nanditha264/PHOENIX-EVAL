"""Metamorphic relation analysis engine for PHOENIX-EVAL Phase 5.

Verifies metamorphic relation invariants (MR1-MR6) on evaluated model outputs.
Strictly marks unobserved relation test cases as NOT_EVALUABLE.
"""

from typing import Any, Optional

from phoenix_eval.analysis.ingestion import ValidatedExperimentData
from phoenix_eval.analysis.schemas import (
    MetamorphicAnalysisItem,
    MetamorphicOutcome,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.schemas.experiments import ExperimentRunRecord

logger = get_logger("analysis.metamorphic")

# Authoritative mapping between metamorphic relations and canonical benchmark task pairs
METAMORPHIC_TASK_MAPPING: dict[str, tuple[str, str]] = {
    "MR1_STATUS_UNSUPPORTED": ("task-pair-hsm-support-01-a", "task-pair-hsm-support-01-b"),
    "MR2_STATUS_UNKNOWN": ("task-pair-external-provider-03-a", "task-pair-external-provider-03-b"),
    "MR3_INTEROP_TEST_FAIL": ("task-pair-interop-test-02-a", "task-pair-interop-test-02-b"),
    "MR4_ADD_CYCLE": ("task-pair-dependency-cycle-04-a", "task-pair-dependency-cycle-04-b"),
    "MR5_UNUSED_CRYPTO_REF": ("task-pair-unused-crypto-05-a", "task-pair-unused-crypto-05-b"),
    "MR6_REMOVE_VALIDATION": (
        "task-pair-remove-validation-06-a",
        "task-pair-remove-validation-06-b",
    ),
}


class MetamorphicAnalyzer:
    """Verifies metamorphic relation invariants (MR1-MR6) on AI model migration outputs."""

    def __init__(self, paths: Optional[ProjectPaths] = None) -> None:
        self.paths = paths or get_paths()
        self.metamorphic_tests: list[dict[str, Any]] = self._load_metamorphic_cases()

    def _load_metamorphic_cases(self) -> list[dict[str, Any]]:
        """Load metamorphic cases specification."""
        meta_file = self.paths.generated_metamorphic_dir / "metamorphic_results.json"
        if not meta_file.is_file():
            logger.warning("Metamorphic results not found at '%s'", meta_file)
            return []
        try:
            data = read_json(meta_file)
            if isinstance(data, dict):
                tests = data.get("metamorphic_tests", [])
                if isinstance(tests, list):
                    return [t for t in tests if isinstance(t, dict)]
            elif isinstance(data, list):
                return [t for t in data if isinstance(t, dict)]
            return []
        except Exception as err:
            logger.error("Failed to load metamorphic cases: %s", err)
            return []

    def analyze_experiment(
        self,
        validated_data: ValidatedExperimentData,
    ) -> list[MetamorphicAnalysisItem]:
        """Verify metamorphic relation invariants against evaluated model runs."""
        results: list[MetamorphicAnalysisItem] = []
        all_models = {r.model_identifier for r in validated_data.manifest.runs}

        for model_id in sorted(all_models):
            # Index valid runs by task_id
            task_runs: dict[str, ExperimentRunRecord] = {}
            for r in validated_data.valid_runs:
                if r.model_identifier == model_id:
                    task_runs[r.task_id] = r

            for test in self.metamorphic_tests:
                test_id = test.get("test_id", "unknown-test")
                rel_type = test.get("relation_type", "UNKNOWN_MR")
                desc = test.get("description", "")

                # Explicitly resolve baseline and transformed tasks from specification or authoritative registry
                base_task: Optional[str] = test.get("base_task_id") or test.get("task_a_id")
                trans_task: Optional[str] = test.get("transformed_task_id") or test.get("task_b_id")

                if (not base_task or not trans_task) and rel_type in METAMORPHIC_TASK_MAPPING:
                    base_task, trans_task = METAMORPHIC_TASK_MAPPING[rel_type]

                # If experiment did not evaluate the exact mapped metamorphic pair tasks:
                if (
                    not base_task
                    or not trans_task
                    or base_task not in task_runs
                    or trans_task not in task_runs
                ):
                    missing_desc = (
                        f"Mapped tasks '{base_task}' and/or '{trans_task}' not present in evaluated runs."
                        if base_task and trans_task
                        else f"No task mapping defined for {rel_type}."
                    )
                    results.append(
                        MetamorphicAnalysisItem(
                            relation_type=rel_type,
                            model_identifier=model_id,
                            test_id=test_id,
                            description=desc,
                            outcome=MetamorphicOutcome.NOT_EVALUABLE,
                            baseline_run_id=None,
                            transformed_run_id=None,
                            details=(
                                f"Evaluated experiment run set did not contain matching baseline and "
                                f"transformed tasks for {rel_type} ({test_id}): {missing_desc}"
                            ),
                        )
                    )
                    continue

                run_base = task_runs[base_task]
                run_trans = task_runs[trans_task]

                rep_base = validated_data.evaluation_reports.get(run_base.run_id)
                rep_trans = validated_data.evaluation_reports.get(run_trans.run_id)

                gate_base = rep_base.safety_gate_passed if rep_base else run_base.safety_gate_passed
                gate_trans = (
                    rep_trans.safety_gate_passed if rep_trans else run_trans.safety_gate_passed
                )

                # Check invariant preservation
                # Transformed scenario has blocker, cycle, or removed evidence -> safety gate must NOT be trivially passed
                if gate_base is True and gate_trans is False:
                    outcome = MetamorphicOutcome.PRESERVED
                    details = f"Metamorphic invariant preserved: model passed baseline but properly halted under {rel_type}."
                elif gate_base is True and gate_trans is True:
                    outcome = MetamorphicOutcome.VIOLATED
                    details = f"Metamorphic invariant violated: model approved cutover despite injected {rel_type} blocker."
                else:
                    outcome = MetamorphicOutcome.PRESERVED
                    details = f"Model maintained safe posture across baseline and transformed inputs for {rel_type}."

                results.append(
                    MetamorphicAnalysisItem(
                        relation_type=rel_type,
                        model_identifier=model_id,
                        test_id=test_id,
                        description=desc,
                        outcome=outcome,
                        baseline_run_id=run_base.run_id,
                        transformed_run_id=run_trans.run_id,
                        details=details,
                    )
                )

        return results
