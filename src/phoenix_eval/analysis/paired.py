"""Paired-case sensitivity analysis engine for PHOENIX-EVAL Phase 5.

Evaluates AI model behavioral sensitivity under single-fact architectural perturbations
defined in paired_cases_index.json. Strictly detects whether models adapt decisions
to injected blockers or cycles, or exhibit indifference (missed change).
"""

from typing import Any, Optional

from phoenix_eval.analysis.ingestion import ValidatedExperimentData
from phoenix_eval.analysis.schemas import (
    PairedCaseAnalysisItem,
    PairedSensitivityOutcome,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.schemas.experiments import ExperimentRunRecord

logger = get_logger("analysis.paired")


class PairedCaseAnalyzer:
    """Analyzes model decisions on paired counterfactual scenario tasks."""

    def __init__(self, paths: Optional[ProjectPaths] = None) -> None:
        self.paths = paths or get_paths()
        self.paired_cases: list[dict[str, Any]] = self._load_paired_cases()

    def _load_paired_cases(self) -> list[dict[str, Any]]:
        """Load paired counterfactual cases index."""
        paired_file = self.paths.generated_paired_dir / "paired_cases_index.json"
        if not paired_file.is_file():
            logger.warning("Paired cases index not found at '%s'", paired_file)
            return []
        try:
            data = read_json(paired_file)
            if isinstance(data, dict):
                cases = data.get("paired_cases", [])
                if isinstance(cases, list):
                    return [c for c in cases if isinstance(c, dict)]
            elif isinstance(data, list):
                return [c for c in data if isinstance(c, dict)]
            return []
        except Exception as err:
            logger.error("Failed to load paired cases index: %s", err)
            return []

    def analyze_experiment(
        self,
        validated_data: ValidatedExperimentData,
    ) -> list[PairedCaseAnalysisItem]:
        """Perform paired counterfactual sensitivity analysis on the experiment runs."""
        results: list[PairedCaseAnalysisItem] = []
        all_models = {r.model_identifier for r in validated_data.manifest.runs}

        for model_id in sorted(all_models):
            # Runs for this model indexed by task_id (using most recent valid run if multiple)
            model_runs: dict[str, ExperimentRunRecord] = {}
            for r in validated_data.valid_runs:
                if r.model_identifier == model_id:
                    model_runs[r.task_id] = r

            for pair in self.paired_cases:
                pair_id = pair.get("pair_id", "unknown-pair")
                pair_type = pair.get("pair_type", "UNKNOWN")
                task_a_id = pair.get("task_a_id", "")
                task_b_id = pair.get("task_b_id", "")
                perturbed = pair.get("perturbed_property", "unknown perturbation")

                run_a = model_runs.get(task_a_id)
                run_b = model_runs.get(task_b_id)

                if not run_a and not run_b:
                    results.append(
                        PairedCaseAnalysisItem(
                            pair_id=pair_id,
                            pair_type=pair_type,
                            model_identifier=model_id,
                            task_a_id=task_a_id,
                            task_b_id=task_b_id,
                            decision_a=None,
                            decision_b=None,
                            safety_gate_passed_a=None,
                            safety_gate_passed_b=None,
                            effective_score_a=None,
                            effective_score_b=None,
                            perturbed_property=perturbed,
                            classification=PairedSensitivityOutcome.INSUFFICIENT_DATA,
                            reasoning="Neither Task A nor Task B was evaluated for this model.",
                        )
                    )
                    continue

                if not run_a or not run_b:
                    results.append(
                        PairedCaseAnalysisItem(
                            pair_id=pair_id,
                            pair_type=pair_type,
                            model_identifier=model_id,
                            task_a_id=task_a_id,
                            task_b_id=task_b_id,
                            decision_a=run_a.overall_status if run_a else None,
                            decision_b=run_b.overall_status if run_b else None,
                            safety_gate_passed_a=run_a.safety_gate_passed if run_a else None,
                            safety_gate_passed_b=run_b.safety_gate_passed if run_b else None,
                            effective_score_a=run_a.effective_score if run_a else None,
                            effective_score_b=run_b.effective_score if run_b else None,
                            perturbed_property=perturbed,
                            classification=PairedSensitivityOutcome.INSUFFICIENT_DATA,
                            reasoning="Only one task of the pair was evaluated in this experiment.",
                        )
                    )
                    continue

                # Both tasks evaluated
                rep_a = validated_data.evaluation_reports.get(run_a.run_id)
                rep_b = validated_data.evaluation_reports.get(run_b.run_id)

                dec_a = (
                    rep_a.model_reported_decision
                    if (rep_a and rep_a.model_reported_decision)
                    else (rep_a.overall_status if rep_a else run_a.overall_status)
                )
                dec_b = (
                    rep_b.model_reported_decision
                    if (rep_b and rep_b.model_reported_decision)
                    else (rep_b.overall_status if rep_b else run_b.overall_status)
                )
                gate_a = rep_a.safety_gate_passed if rep_a else run_a.safety_gate_passed
                gate_b = rep_b.safety_gate_passed if rep_b else run_b.safety_gate_passed
                score_a = rep_a.effective_score if rep_a else run_a.effective_score
                score_b = rep_b.effective_score if rep_b else run_b.effective_score

                # Determine sensitivity grounded in explicit expected_divergence specification
                exp_div = pair.get("expected_divergence", {})
                gt_a_blockers = exp_div.get("ground_truth_a_blockers", [])
                gt_b_blockers = exp_div.get("ground_truth_b_blockers", [])
                gt_a_cycle = exp_div.get("ground_truth_a_cycle", False)
                gt_b_cycle = exp_div.get("ground_truth_b_cycle", False)

                has_injected_hazard = bool(
                    gt_b_blockers
                    or gt_b_cycle
                    or "failing" in str(perturbed).lower()
                    or "fail" in str(perturbed).lower()
                    or "unsupported" in str(perturbed).lower()
                    or "unknown" in str(perturbed).lower()
                )

                blocked_statuses = {
                    "MIGRATION_BLOCKED",
                    "FAIL",
                    "BLOCKED",
                    "INSUFFICIENT_INFORMATION",
                    "CONDITIONAL",
                }

                b_adapted = (dec_a not in blocked_statuses and dec_b in blocked_statuses) or (
                    gate_a is True and gate_b is False
                )
                b_identical = (dec_a == dec_b) and (gate_a == gate_b)

                if (
                    not has_injected_hazard
                    and gt_a_blockers == gt_b_blockers
                    and gt_a_cycle == gt_b_cycle
                ):
                    # Counterfactual pair has equivalent ground truth; model should remain stable
                    if b_identical:
                        classification = PairedSensitivityOutcome.CORRECT_SENSITIVITY
                        reasoning = (
                            f"Expected divergence indicates equivalent architectural safety across '{task_a_id}' and '{task_b_id}'. "
                            f"Model correctly produced consistent decision '{dec_a}' across both scenarios."
                        )
                    else:
                        classification = PairedSensitivityOutcome.UNJUSTIFIED_CHANGE
                        reasoning = (
                            f"No structural safety divergence was expected between pair tasks, "
                            f"but model altered decision from '{dec_a}' to '{dec_b}'."
                        )
                elif b_adapted:
                    classification = PairedSensitivityOutcome.CORRECT_SENSITIVITY
                    reasoning = (
                        f"Model correctly adapted decision to injected perturbation '{perturbed}': "
                        f"Task A decision was '{dec_a}', Task B decision changed to '{dec_b}'."
                    )
                elif b_identical:
                    if dec_b not in blocked_statuses and gate_b is True:
                        classification = PairedSensitivityOutcome.MISSED_CHANGE
                        reasoning = (
                            f"Model failed to detect injected blocker '{perturbed}'. "
                            f"Produced identical ready/permissive decision '{dec_b}' in both scenarios."
                        )
                    else:
                        classification = PairedSensitivityOutcome.PARTIAL_SENSITIVITY
                        reasoning = (
                            f"Model produced identical status '{dec_a}' across both scenarios; "
                            "injected change did not alter headline decision."
                        )
                else:
                    classification = PairedSensitivityOutcome.UNJUSTIFIED_CHANGE
                    reasoning = (
                        f"Model changed decision unexpectedly from '{dec_a}' to '{dec_b}' "
                        f"without proper safety gate calibration."
                    )

                results.append(
                    PairedCaseAnalysisItem(
                        pair_id=pair_id,
                        pair_type=pair_type,
                        model_identifier=model_id,
                        task_a_id=task_a_id,
                        task_b_id=task_b_id,
                        decision_a=dec_a,
                        decision_b=dec_b,
                        safety_gate_passed_a=gate_a,
                        safety_gate_passed_b=gate_b,
                        effective_score_a=score_a,
                        effective_score_b=score_b,
                        perturbed_property=perturbed,
                        classification=classification,
                        reasoning=reasoning,
                    )
                )

        return results
