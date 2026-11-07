"""Unit tests verifying scoring robustness against perturbation and adversarial exploitation.

Requirements:
- Explanation verbosity (adding 500 words of filler text) does not alter score.
- Repeating the same valid evidence ID multiple times creates zero additional credit.
- Listing additional unneeded components does not compensate for missing prerequisites.
- A high raw score (e.g. 90+) cannot bypass a critical safety gate veto.
- Unsupported actions cannot gain credit through synonym or alternative wording.
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.schemas.response_contract import (
    MigrationActionType,
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibility,
    ReportedCompatibilityStatus,
    ReportedMigrationStep,
    ReportedTestResult,
    ReportedTestStatus,
)
from phoenix_eval.schemas.tasks import BenchmarkTask


@pytest.fixture
def baseline_setup():
    """Load baseline task, ground truth, and valid response."""
    paths = get_paths()
    calib_root = paths.datasets_dir / "calibration"
    resp_file = calib_root / "responses" / "kg_01_valid_migration.json"
    raw_text = resp_file.read_text(encoding="utf-8")
    resp_data = json.loads(raw_text)

    task_id = resp_data["task_id"]
    task_file = paths.generated_tasks_dir / f"{task_id}.json"
    if not task_file.is_file():
        task_file = paths.tasks_dir / f"{task_id}.json"
    task = BenchmarkTask.model_validate(read_json(task_file))

    gt_file = paths.generated_ground_truth_dir / f"{task.ground_truth_reference}.json"
    if not gt_file.is_file():
        gt_file = paths.ground_truth_dir / f"{task.ground_truth_reference}.json"
    gt = read_json(gt_file)

    evaluator = DeterministicEvaluator()
    return evaluator, task, gt, resp_data, raw_text


def test_robustness_explanation_verbosity_stability(baseline_setup):
    """Verify that adding 500 words of filler explanation text does not alter scores."""
    evaluator, task, gt, resp_data, raw_text = baseline_setup

    # Evaluate baseline
    report_base = evaluator.evaluate_detailed(task, raw_text, gt)
    base_raw = report_base.raw_weighted_score
    base_eff = report_base.effective_score
    base_exp_raw = report_base.dimension_scores["explanation_and_traceability"]["raw_score"]

    # Generate 500 words of filler text without safety-bypass keywords
    filler_paragraph = (
        "In evaluating enterprise architecture transitions, systematic cryptographic agility is "
        "increasingly recognized as a foundational operational requirement for modern distributed "
        "computing infrastructure. Long term maintenance considerations indicate that lifecycle "
        "analysis, operational cadence, and documentation parity play a critical role in supporting "
        "engineering governance. Architectural patterns across cloud ecosystems suggest that modularity "
        "and clean separation of concerns reduce overall deployment friction during systemic upgrades. "
        "Furthermore, comprehensive telemetry tracking provides observability into ongoing runtime "
        "behaviors across microservice boundaries. Such governance practices ensure that technical "
        "debt remains manageable over extended operational horizons while maintaining adherence to "
        "industry standards and best practices throughout multi-year enterprise modernization roadmaps. "
    )
    # Replicate to reach ~500 words
    filler_500_words = " ".join([filler_paragraph] * 6)

    verbose_data = json.loads(json.dumps(resp_data))
    verbose_data["explanation"] = verbose_data["explanation"] + "\n\n" + filler_500_words
    verbose_text = json.dumps(verbose_data, indent=2)

    report_verbose = evaluator.evaluate_detailed(task, verbose_text, gt)

    # Invariants: Scores must be strictly invariant under filler verbosity
    assert report_verbose.raw_weighted_score == base_raw
    assert report_verbose.effective_score == base_eff
    assert report_verbose.safety_gate_passed == report_base.safety_gate_passed
    assert (
        report_verbose.dimension_scores["explanation_and_traceability"]["raw_score"] == base_exp_raw
    )
    for dim_name in report_base.dimension_scores:
        assert (
            report_verbose.dimension_scores[dim_name]["raw_score"]
            == report_base.dimension_scores[dim_name]["raw_score"]
        )


def test_robustness_evidence_id_duplication_zero_extra_credit(baseline_setup):
    """Verify that repeating the same valid evidence ID multiple times creates zero additional credit."""
    evaluator, task, gt, resp_data, raw_text = baseline_setup

    report_base = evaluator.evaluate_detailed(task, raw_text, gt)
    base_raw = report_base.raw_weighted_score
    base_evid_raw = report_base.dimension_scores["evidence_and_uncertainty"]["raw_score"]

    # Create duplicated evidence references
    dup_data = json.loads(json.dumps(resp_data))
    original_evids = list(dup_data.get("evidence_references", []))
    assert len(original_evids) > 0

    # Repeat evidence references 10 times in the list
    dup_data["evidence_references"] = original_evids * 10
    dup_text = json.dumps(dup_data, indent=2)

    report_dup = evaluator.evaluate_detailed(task, dup_text, gt)

    # Invariants: No additional credit can be gained from duplicated valid evidence citations
    assert report_dup.dimension_scores["evidence_and_uncertainty"]["raw_score"] == base_evid_raw
    assert report_dup.raw_weighted_score == base_raw
    assert report_dup.effective_score == report_base.effective_score


def test_robustness_unneeded_components_do_not_compensate_missing_prerequisite(baseline_setup):
    """Verify that listing additional unneeded components does not compensate for missing prerequisites."""
    paths = get_paths()
    calib_root = paths.datasets_dir / "calibration"
    bad_resp_file = calib_root / "responses" / "kb_01_reversed_order.json"
    bad_text = bad_resp_file.read_text(encoding="utf-8")
    bad_data = json.loads(bad_text)

    task_id = bad_data["task_id"]
    task_file = paths.generated_tasks_dir / f"{task_id}.json"
    if not task_file.is_file():
        task_file = paths.tasks_dir / f"{task_id}.json"
    task = BenchmarkTask.model_validate(read_json(task_file))

    gt_file = paths.generated_ground_truth_dir / f"{task.ground_truth_reference}.json"
    if not gt_file.is_file():
        gt_file = paths.ground_truth_dir / f"{task.ground_truth_reference}.json"
    gt = read_json(gt_file)

    evaluator = DeterministicEvaluator()

    # Evaluate baseline bad case (reversed order)
    report_bad = evaluator.evaluate_detailed(task, bad_text, gt)
    assert report_bad.safety_gate_passed is False
    assert report_bad.effective_score == 0.0

    # Pad with extra/unneeded steps that do not fix the prerequisite dependency ordering
    padded_data = json.loads(json.dumps(bad_data))
    max_wave = max(step["wave"] for step in padded_data["migration_plan"])
    padded_data["migration_plan"].append(
        {
            "wave": max_wave + 1,
            "component_id": "comp-extra-logging-sink",
            "action_type": "PREPARATION",
            "rollback_trigger": "error_rate > 0.01",
            "rollback_action": "revert",
        }
    )
    padded_data["migration_plan"].append(
        {
            "wave": max_wave + 2,
            "component_id": "comp-extra-metric-exporter",
            "action_type": "VALIDATION",
            "rollback_trigger": "latency > 100ms",
            "rollback_action": "revert",
        }
    )
    padded_text = json.dumps(padded_data, indent=2)

    report_padded = evaluator.evaluate_detailed(task, padded_text, gt)

    # Invariants: Extra components cannot rescue an unsafe ordering
    assert report_padded.safety_gate_passed is False
    assert report_padded.effective_score == 0.0
    bad_violations = {v["rule_name"] for v in report_bad.critical_violations}
    padded_violations = {v["rule_name"] for v in report_padded.critical_violations}
    # Dependency order violation must still be present
    assert "VIO_DEPENDENCY_ORDER_REVERSED" in padded_violations


def test_robustness_high_raw_score_cannot_bypass_safety_gate_veto(baseline_setup):
    """Verify that a high raw score (e.g. 90+) cannot bypass a critical safety gate veto."""
    evaluator, task, gt, resp_data, raw_text = baseline_setup

    # Start from baseline known-good response (scores ~100.0 raw)
    report_base = evaluator.evaluate_detailed(task, raw_text, gt)
    assert report_base.raw_weighted_score >= 85.0
    assert report_base.safety_gate_passed is True

    # Mutate by migrating an explicitly unsupported/blocked component
    blocked_data = json.loads(json.dumps(resp_data))
    # Pick a component and make it UNSUPPORTED, yet keep it in migration_plan
    target_comp = blocked_data["migration_plan"][0]["component_id"]
    for comp in blocked_data["compatibility_assessments"]:
        if comp["component_id"] == target_comp:
            comp["status"] = "UNSUPPORTED"
            break
    blocked_data["blocked_components"] = [target_comp]
    blocked_text = json.dumps(blocked_data, indent=2)

    report_blocked = evaluator.evaluate_detailed(task, blocked_text, gt)

    # Invariants:
    # 1. Raw weighted score preserves capability telemetry (remains high)
    assert report_blocked.raw_weighted_score > 60.0
    # 2. Critical safety gate fails
    assert report_blocked.safety_gate_passed is False
    # 3. Effective score is completely zeroed out
    assert report_blocked.effective_score == 0.0
    # 4. Overall status is BLOCKED_BY_SAFETY_GATE
    assert report_blocked.overall_status == "BLOCKED_BY_SAFETY_GATE"
    # 5. Critical violation is recorded
    crit_viols = [v["rule_name"] for v in report_blocked.critical_violations]
    assert len(crit_viols) > 0
    assert any(
        viol in crit_viols
        for viol in [
            "VIO_UNSUPPORTED_ALGORITHM_CUTOVER",
            "VIO_CRITICAL_BLOCKED_MIGRATION",
            "VIO_UNSAFE_BLOCKED_PLAN",
            "VIO_CONTRADICTORY_DECISION",
            "VIO_CONSTRAINT_VIOLATION",
        ]
    )


def test_robustness_unsupported_actions_gain_no_credit_via_synonyms():
    """Verify that unsupported action types or synonyms cannot bypass schema validation or gain credit."""
    # 1. Test schema rejection of synonym action types
    with pytest.raises(ValidationError):
        ReportedMigrationStep(
            wave=1,
            component_id="comp-01",
            action_type="EXECUTE_DEPLOYMENT",  # Invalid synonym for PRODUCTION_CUTOVER
        )

    with pytest.raises(ValidationError):
        ReportedMigrationStep(
            wave=1,
            component_id="comp-01",
            action_type="MIGRATE_NOW",  # Invalid custom action
        )

    # 2. Test schema rejection of synonym decision
    with pytest.raises(ValidationError):
        ModelResponseContract(
            task_id="task-01",
            decision="READY_TO_GO",  # Invalid synonym for MIGRATION_READY
            identified_dependencies=[],
            compatibility_assessments=[],
            migration_plan=[],
            blocked_components=[],
            required_actions=[],
            verification_results=[],
            evidence_references=[],
            assumptions=[],
            uncertainties=[],
            explanation="Test invalid decision synonym",
        )

    # 3. Test that legitimate enum values are strictly recognized
    valid_step = ReportedMigrationStep(
        wave=1,
        component_id="comp-01",
        action_type=MigrationActionType.PRODUCTION_CUTOVER,
    )
    assert valid_step.action_type == MigrationActionType.PRODUCTION_CUTOVER
