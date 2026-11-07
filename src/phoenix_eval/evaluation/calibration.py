"""Calibration suite runner for validating deterministic evaluator precision and recall.

Defines an explicit confusion matrix where:
    - Positive Class = Unsafe response detected
    - True Positive (TP) = Unsafe response correctly blocked
    - False Positive (FP) = Safe response incorrectly blocked
    - False Negative (FN) = Unsafe response incorrectly accepted
    - True Negative (TN) = Safe response correctly accepted
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.schemas.tasks import BenchmarkTask


class CalibrationCaseDef(BaseModel):
    """Specification of an expected calibration test case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    case_category: str  # KNOWN_GOOD, KNOWN_BAD, EDGE_CASE, CONTRADICTORY, ADVERSARIAL
    task_id: str
    file_name: str
    description: str
    expected_safety_gate_passed: bool
    expected_status: str
    expected_violations: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class CalibrationCaseResult:
    """Outcome of evaluating a single calibration case."""

    case_id: str
    category: str
    passed: bool
    expected_safety_gate_passed: bool
    actual_safety_gate_passed: bool
    expected_status: str
    actual_status: str
    expected_violations: list[str]
    actual_violations: list[str]
    raw_score: float
    effective_score: float
    message: str

    @property
    def matches_expected(self) -> bool:
        return self.passed

    @property
    def safety_gate_passed(self) -> bool:
        return self.actual_safety_gate_passed

    @property
    def failure_reasons(self) -> list[str]:
        return [self.message] if not self.passed else []


@dataclass(frozen=True)
class CalibrationSummary:
    """Aggregate statistics and confusion matrix for an entire calibration suite run.

    Explicit positive class definition:
        Positive = Unsafe response detected
        True Positive (TP) = Unsafe response correctly blocked
        False Positive (FP) = Safe response incorrectly blocked
        False Negative (FN) = Unsafe response incorrectly accepted
        True Negative (TN) = Safe response correctly accepted
    """

    total_cases: int
    passed_cases: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    known_good_total: int
    known_good_accepted: int
    known_bad_total: int
    known_bad_detected: int
    results_by_violation: dict[str, dict[str, int]]
    case_results: list[CalibrationCaseResult]
    evaluator_version: str = "3.0.0"

    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP): Proportion of blocked responses that were genuinely unsafe."""
        denom = self.true_positives + self.false_positives
        return round(self.true_positives / denom, 4) if denom > 0 else 1.0

    @property
    def recall(self) -> float:
        """Recall (Sensitivity) = TP / (TP + FN): Proportion of unsafe responses successfully caught and blocked."""
        denom = self.true_positives + self.false_negatives
        return round(self.true_positives / denom, 4) if denom > 0 else 1.0

    @property
    def specificity(self) -> float:
        """Specificity = TN / (TN + FP): Proportion of genuinely safe responses correctly passed."""
        denom = self.true_negatives + self.false_positives
        return round(self.true_negatives / denom, 4) if denom > 0 else 1.0

    @property
    def accuracy(self) -> float:
        """Overall classification accuracy = (TP + TN) / Total."""
        denom = self.total_cases
        return round((self.true_positives + self.true_negatives) / denom, 4) if denom > 0 else 1.0

    @property
    def all_passed(self) -> bool:
        return self.passed_cases == self.total_cases and self.total_cases > 0

    @property
    def cases(self) -> list[CalibrationCaseResult]:
        return self.case_results

    @staticmethod
    def calculate_metrics_from_matrix(tp: int, fp: int, tn: int, fn: int) -> dict[str, float]:
        """Compute standard confusion matrix rates from raw counts."""
        total = tp + fp + tn + fn
        prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 1.0
        rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 1.0
        spec = round(tn / (tn + fp), 4) if (tn + fp) > 0 else 1.0
        acc = round((tp + tn) / total, 4) if total > 0 else 1.0
        return {
            "precision": prec,
            "recall": rec,
            "specificity": spec,
            "accuracy": acc,
        }


class CalibrationRunner:
    """Executes the calibration suite to detect false positives, false negatives, and grader bias."""

    def __init__(
        self,
        evaluator: Optional[DeterministicEvaluator] = None,
        calibration_dir: Optional[Path] = None,
    ) -> None:
        self.evaluator = evaluator or DeterministicEvaluator()
        self.calibration_dir = calibration_dir

    def run_all(self) -> CalibrationSummary:
        """Run all calibration cases."""
        return self.run(self.calibration_dir)

    def run(self, calibration_dir: Optional[Path] = None) -> CalibrationSummary:
        """Run all calibration test cases and produce a detailed calibration summary."""
        paths = get_paths()
        calib_root = (
            calibration_dir or self.calibration_dir or (paths.root / "datasets" / "calibration")
        )
        index_file = calib_root / "calibration_cases.json"
        resp_dir = calib_root / "responses"

        if not index_file.is_file():
            raise FileNotFoundError(f"Calibration index not found: {index_file}")

        index_data = read_json(index_file)
        raw_cases = index_data.get("cases", [])
        cases = [CalibrationCaseDef.model_validate(c) for c in raw_cases]

        case_results: list[CalibrationCaseResult] = []
        kg_total = 0
        kg_accepted = 0
        kb_total = 0
        kb_detected = 0
        tp = 0
        fp = 0
        tn = 0
        fn = 0
        violations_map: dict[str, dict[str, int]] = {}

        for case in cases:
            resp_file = resp_dir / case.file_name
            raw_text = resp_file.read_text(encoding="utf-8")

            # Load task
            task_file = paths.generated_tasks_dir / f"{case.task_id}.json"
            if not task_file.is_file():
                task_file = paths.tasks_dir / f"{case.task_id}.json"
            task = BenchmarkTask.model_validate(read_json(task_file))

            # Load ground truth
            gt_file = paths.generated_ground_truth_dir / f"{task.ground_truth_reference}.json"
            if not gt_file.is_file():
                gt_file = paths.ground_truth_dir / f"{task.ground_truth_reference}.json"
            gt = read_json(gt_file)

            # Evaluate
            report = self.evaluator.evaluate_detailed(
                task=task,
                raw_response_text=raw_text,
                ground_truth=gt,
                model_identifier=case.case_id,
            )

            actual_passed = report.safety_gate_passed
            actual_status = report.overall_status
            actual_viols = [v["rule_name"] for v in report.critical_violations] + [
                v["rule_name"] for v in report.non_critical_violations
            ]

            # Invariant checks
            gate_match = actual_passed == case.expected_safety_gate_passed
            status_match = actual_status == case.expected_status
            viols_match = set(case.expected_violations).issubset(set(actual_viols))

            case_passed = gate_match and status_match and viols_match

            # Explicit Confusion Matrix Tracking
            # Positive class: Unsafe response (expected_safety_gate_passed == False)
            # Negative class: Safe response (expected_safety_gate_passed == True)
            is_expected_unsafe = not case.expected_safety_gate_passed
            is_actual_blocked = not actual_passed

            if is_expected_unsafe:
                kb_total += 1
                if is_actual_blocked:
                    tp += 1
                    kb_detected += 1
                else:
                    fn += 1
            else:
                kg_total += 1
                if not is_actual_blocked:
                    tn += 1
                    kg_accepted += 1
                else:
                    fp += 1

            for exp_v in case.expected_violations:
                stat_entry = violations_map.setdefault(exp_v, {"expected": 0, "detected": 0})
                stat_entry["expected"] += 1
                if exp_v in actual_viols:
                    stat_entry["detected"] += 1

            msg = (
                "OK"
                if case_passed
                else f"Mismatch: expected gate={case.expected_safety_gate_passed}, status={case.expected_status}; got gate={actual_passed}, status={actual_status}"
            )

            case_results.append(
                CalibrationCaseResult(
                    case_id=case.case_id,
                    category=case.case_category,
                    passed=case_passed,
                    expected_safety_gate_passed=case.expected_safety_gate_passed,
                    actual_safety_gate_passed=actual_passed,
                    expected_status=case.expected_status,
                    actual_status=actual_status,
                    expected_violations=case.expected_violations,
                    actual_violations=actual_viols,
                    raw_score=report.raw_weighted_score,
                    effective_score=report.effective_score,
                    message=msg,
                )
            )

        passed_count = sum(1 for r in case_results if r.passed)

        return CalibrationSummary(
            total_cases=len(cases),
            passed_cases=passed_count,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            known_good_total=kg_total,
            known_good_accepted=kg_accepted,
            known_bad_total=kb_total,
            known_bad_detected=kb_detected,
            results_by_violation=violations_map,
            case_results=case_results,
        )
