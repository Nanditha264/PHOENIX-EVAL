"""Unit tests for the evaluation calibration suite runner and false-positive/negative rates."""

from phoenix_eval.core.paths import get_paths
from phoenix_eval.evaluation.calibration import CalibrationRunner


def test_calibration_runner_execution_and_metrics() -> None:
    paths = get_paths()
    calib_dir = paths.datasets_dir / "calibration"
    assert calib_dir.is_dir(), f"Calibration directory not found: {calib_dir}"

    runner = CalibrationRunner(calibration_dir=calib_dir)
    summary = runner.run_all()

    assert summary.total_cases == 42
    assert summary.passed_cases == 42
    assert summary.all_passed is True

    # Critical calibration invariants:
    assert summary.false_positives == 0, f"False positives detected: {summary.false_positives}"
    assert summary.false_negatives == 0, f"False negatives detected: {summary.false_negatives}"
    assert summary.precision == 1.0
    assert summary.recall == 1.0
    assert summary.specificity == 1.0
    assert summary.accuracy == 1.0


def test_calibration_detects_individual_test_cases() -> None:
    paths = get_paths()
    calib_dir = paths.datasets_dir / "calibration"
    runner = CalibrationRunner(calibration_dir=calib_dir)
    summary = runner.run_all()

    case_ids = {c.case_id for c in summary.cases}
    assert "kg-01-valid-migration" in case_ids
    assert "kb-01-reversed-order" in case_ids
    assert "kb-02-ignored-cycle" in case_ids
    assert "kb-03-ignored-failed-test" in case_ids
    assert "ec-01-alternative-valid-order" in case_ids
    assert "ec-04-contradictory-decision" in case_ids

    # Verify individual case results
    for case in summary.cases:
        assert case.matches_expected is True, f"Case {case.case_id} failed: {case.message}"
