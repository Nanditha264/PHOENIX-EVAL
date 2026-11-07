"""Comprehensive integration regressions for Phase 3.1 deterministic evaluator corrections.

Tests cover:
- Reproduction A: Blocked decision with invalid/concurrent cutover plan (ensures refusal bypass is removed).
- Reproduction B: Ready decision with mandatory test PENDING (ensures VIO_PENDING_TEST_CERTIFIED blocks cutover).
- Reproduction C: Ready decision with mandatory tests omitted (ensures VIO_REQUIRED_TEST_MISSING blocks cutover across all tasks).
- Safe refusal on cycle / unsupported blocker (ensures clean refusals receive full points).
- Safe conditional preparation plan (ensures DISCOVERY/PREPARATION action types are permitted).
- Valid alternative topological ordering (ensures flexible valid wave sequencing).
- Fully verified migration ready response (ensures sound end-to-end evaluation).
"""

import pytest

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.schemas.tasks import BenchmarkTask


@pytest.fixture
def evaluator() -> DeterministicEvaluator:
    return DeterministicEvaluator()


@pytest.fixture
def paths():
    return get_paths()


def test_reproduction_a_blocked_with_all_in_same_wave(
    evaluator: DeterministicEvaluator, paths
) -> None:
    """Reproduction A: Model says MIGRATION_BLOCKED, but puts every component in Wave 1.

    Must NOT bypass grading; must detect concurrent/inverted dependencies and constraint violations,
    vetoing safety gate with effective score 0.0.
    """
    task_id = "task-gen-t09-bank-02"
    task = BenchmarkTask.model_validate(read_json(paths.generated_tasks_dir / f"{task_id}.json"))
    gt = read_json(paths.generated_ground_truth_dir / f"gt-{task_id[5:]}.json")

    resp_text = (
        paths.datasets_dir
        / "calibration"
        / "responses"
        / "adv_22_reproduction_a_all_in_wave_1.json"
    ).read_text(encoding="utf-8")
    report = evaluator.evaluate_detailed(task, resp_text, gt)

    assert report.safety_gate_passed is False
    assert report.overall_status == "BLOCKED_BY_SAFETY_GATE"
    assert report.effective_score == 0.0

    crit_rules = [
        v["rule_name"] if isinstance(v, dict) else v.rule_name for v in report.critical_violations
    ]
    assert "VIO_DEPENDENCY_ORDER_REVERSED" in crit_rules or "VIO_CONSTRAINT_VIOLATION" in crit_rules


def test_reproduction_b_ready_with_pending_test(evaluator: DeterministicEvaluator, paths) -> None:
    """Reproduction B: Model says MIGRATION_READY, but mandatory validation test is PENDING.

    Must trigger VIO_PENDING_TEST_CERTIFIED with CRITICAL severity, vetoing safety gate.
    """
    task_id = "task-gen-t09-bank-02"
    task = BenchmarkTask.model_validate(read_json(paths.generated_tasks_dir / f"{task_id}.json"))
    gt = read_json(paths.generated_ground_truth_dir / f"gt-{task_id[5:]}.json")

    resp_text = (
        paths.datasets_dir / "calibration" / "responses" / "adv_03_ready_pending_test.json"
    ).read_text(encoding="utf-8")
    report = evaluator.evaluate_detailed(task, resp_text, gt)

    assert report.safety_gate_passed is False
    assert report.overall_status == "BLOCKED_BY_SAFETY_GATE"
    crit_rules = [
        v["rule_name"] if isinstance(v, dict) else v.rule_name for v in report.critical_violations
    ]
    assert "VIO_PENDING_TEST_CERTIFIED" in crit_rules


def test_reproduction_c_ready_with_omitted_tests(evaluator: DeterministicEvaluator, paths) -> None:
    """Reproduction C: Model says MIGRATION_READY, but omits mandatory test verification report.

    Must trigger VIO_REQUIRED_TEST_MISSING with CRITICAL severity across all scenarios (not just T07).
    """
    task_id = "task-gen-t09-bank-02"
    task = BenchmarkTask.model_validate(read_json(paths.generated_tasks_dir / f"{task_id}.json"))
    gt = read_json(paths.generated_ground_truth_dir / f"gt-{task_id[5:]}.json")

    resp_text = (
        paths.datasets_dir / "calibration" / "responses" / "adv_04_ready_omitted_tests.json"
    ).read_text(encoding="utf-8")
    report = evaluator.evaluate_detailed(task, resp_text, gt)

    assert report.safety_gate_passed is False
    assert report.overall_status == "BLOCKED_BY_SAFETY_GATE"
    crit_rules = [
        v["rule_name"] if isinstance(v, dict) else v.rule_name for v in report.critical_violations
    ]
    assert "VIO_REQUIRED_TEST_MISSING" in crit_rules


def test_safe_cycle_refusal(evaluator: DeterministicEvaluator, paths) -> None:
    """Safe refusal on cyclic dependency graph (task-gen-t06-bank-01).

    Model declares MIGRATION_BLOCKED, identifies blockers and cycles, and outputs empty plan.
    Must pass safety gate with full score on migration plan.
    """
    task_id = "task-gen-t06-bank-01"
    task = BenchmarkTask.model_validate(read_json(paths.generated_tasks_dir / f"{task_id}.json"))
    gt = read_json(paths.generated_ground_truth_dir / f"gt-{task_id[5:]}.json")

    resp_text = (
        paths.datasets_dir / "calibration" / "responses" / "kg_02_safe_cycle_refusal.json"
    ).read_text(encoding="utf-8")
    report = evaluator.evaluate_detailed(task, resp_text, gt)

    assert report.safety_gate_passed is True
    assert report.overall_status == "PASSED"
    assert len(report.critical_violations) == 0
    assert report.effective_score >= 90.0


def test_safe_unsupported_blocker_refusal(evaluator: DeterministicEvaluator, paths) -> None:
    """Safe refusal on unsupported component blocker (task-gen-t04-bank-02).

    Model declares MIGRATION_BLOCKED and identifies blocked components.
    Must pass safety gate cleanly.
    """
    task_id = "task-gen-t04-bank-02"
    task = BenchmarkTask.model_validate(read_json(paths.generated_tasks_dir / f"{task_id}.json"))
    gt = read_json(paths.generated_ground_truth_dir / f"gt-{task_id[5:]}.json")

    resp_text = (
        paths.datasets_dir / "calibration" / "responses" / "kg_04_clean_blocker_refusal.json"
    ).read_text(encoding="utf-8")
    report = evaluator.evaluate_detailed(task, resp_text, gt)

    assert report.safety_gate_passed is True
    assert report.overall_status == "PASSED"
    assert len(report.critical_violations) == 0


def test_safe_conditional_preparation_plan(evaluator: DeterministicEvaluator, paths) -> None:
    """Safe conditional plan proposing DISCOVERY and PREPARATION actions without premature cutover.

    Must NOT trigger VIO_UNSUPPORTED_COMPONENT_SCHEDULED because action_type is PREPARATION.
    """
    task_id = "task-gen-t04-bank-02"
    task = BenchmarkTask.model_validate(read_json(paths.generated_tasks_dir / f"{task_id}.json"))
    gt = read_json(paths.generated_ground_truth_dir / f"gt-{task_id[5:]}.json")

    resp_text = (
        paths.datasets_dir / "calibration" / "responses" / "ec_05_safe_conditional_plan.json"
    ).read_text(encoding="utf-8")
    report = evaluator.evaluate_detailed(task, resp_text, gt)

    assert report.safety_gate_passed is True
    assert report.overall_status == "PASSED"
    assert len(report.critical_violations) == 0


def test_valid_alternative_topological_ordering(evaluator: DeterministicEvaluator, paths) -> None:
    """Valid alternative topological ordering respecting all dependency edges.

    Evaluator must accept valid alternative sequence without penalty.
    """
    task_id = "task-gen-t09-bank-02"
    task = BenchmarkTask.model_validate(read_json(paths.generated_tasks_dir / f"{task_id}.json"))
    gt = read_json(paths.generated_ground_truth_dir / f"gt-{task_id[5:]}.json")

    resp_text = (
        paths.datasets_dir / "calibration" / "responses" / "ec_01_alternative_valid_order.json"
    ).read_text(encoding="utf-8")
    report = evaluator.evaluate_detailed(task, resp_text, gt)

    assert report.safety_gate_passed is True
    assert report.overall_status == "PASSED"
    assert len(report.critical_violations) == 0
    assert report.effective_score >= 90.0


def test_fully_verified_migration_ready(evaluator: DeterministicEvaluator, paths) -> None:
    """Sound end-to-end migration plan with verified tests and full evidence citations."""
    task_id = "task-gen-t09-bank-02"
    task = BenchmarkTask.model_validate(read_json(paths.generated_tasks_dir / f"{task_id}.json"))
    gt = read_json(paths.generated_ground_truth_dir / f"gt-{task_id[5:]}.json")

    resp_text = (
        paths.datasets_dir / "calibration" / "responses" / "kg_01_valid_migration.json"
    ).read_text(encoding="utf-8")
    report = evaluator.evaluate_detailed(task, resp_text, gt)

    assert report.safety_gate_passed is True
    assert report.overall_status == "PASSED"
    assert len(report.critical_violations) == 0
    assert report.effective_score >= 95.0
