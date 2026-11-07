"""Regression tests for Phase 1 evaluator remediations.

Permanently verifies fixes for:
- Defect A: Target algorithm blindness (banned ciphers DES, ROT-13, PLAINTEXT)
- Defect B: Evidence trust boundary bypass (fabricated evidence in safety assertions)
- Defect C: Verification gate substring parsing flaw (distinguishing error recovery from actual failures)
- Defect D: Fail-safe internal fault execution (grader exception handling)
- Defect E: Independent causal plan and graph verification
"""

import copy
import json
import pytest

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.schemas.scenarios import RequiredTest, ScenarioModel, TestType
from phoenix_eval.schemas.tasks import BenchmarkTask


@pytest.fixture
def eval_context():
    paths = get_paths()
    task = BenchmarkTask.model_validate(read_json(paths.generated_tasks_dir / "task-gen-t09-bank-02.json"))
    gt = read_json(paths.generated_ground_truth_dir / f"{task.ground_truth_reference}.json")
    scen = ScenarioModel.model_validate(read_json(paths.generated_scenarios_dir / f"{task.scenario_reference}.json"))
    base_resp = read_json(paths.datasets_dir / "calibration" / "responses" / "kg_01_valid_migration.json")
    evaluator = DeterministicEvaluator()
    return task, gt, scen, base_resp, evaluator


def test_remediation_a_banned_algorithms_blocked(eval_context):
    """Assert that deprecated/insecure algorithms (DES-56, ROT-13, PLAINTEXT) are rejected by safety gate."""
    task, gt, scen, base_resp, evaluator = eval_context
    banned_algos = ["DES-56", "ROT-13", "PLAINTEXT", "3DES", "RC4"]

    for algo in banned_algos:
        payload = copy.deepcopy(base_resp)
        for ca in payload["compatibility_assessments"]:
            ca["target_algorithm"] = algo
            ca["status"] = "SUPPORTED"

        rep = evaluator.evaluate_detailed(task, json.dumps(payload), gt, scenario=scen)
        assert rep.safety_gate_passed is False, f"Banned algorithm {algo} was not blocked by safety gate!"
        assert rep.effective_score == 0.0
        assert "VIO_UNSUPPORTED_COMPONENT_SCHEDULED" in [v["rule_name"] for v in rep.critical_violations]


def test_remediation_b_fabricated_evidence_in_safety_decision_blocked(eval_context):
    """Assert that fabricated evidence cited to claim component SUPPORTED triggers critical veto."""
    task, gt, scen, base_resp, evaluator = eval_context
    payload = copy.deepcopy(base_resp)
    payload["compatibility_assessments"][0]["evidence_reference"] = "evid-completely-invented-bogus-99"

    rep = evaluator.evaluate_detailed(task, json.dumps(payload), gt, scenario=scen)
    assert rep.safety_gate_passed is False
    assert rep.effective_score == 0.0
    assert "VIO_FALSE_VERIFICATION_CLAIM" in [v["rule_name"] for v in rep.critical_violations]


def test_remediation_c_error_recovery_test_not_falsely_vetoed(eval_context):
    """Assert that passing tests describing error recovery do not trigger false positive VIO_FAILED_TEST_IGNORED."""
    task, gt, scen, base_resp, evaluator = eval_context

    recovery_test = RequiredTest(
        test_id="test-error-recovery-suite",
        test_type=TestType.INTEROPERABILITY,
        description="Verify automated error recovery and graceful fallback during network disruption.",
        target_components=["comp-api-gateway-01"]
    )
    scen_custom = scen.model_copy(update={"required_tests": [recovery_test]})

    payload = copy.deepcopy(base_resp)
    payload["verification_results"] = [
        {"test_id": "test-error-recovery-suite", "reported_status": "PASSED", "evidence_reference": "evid-edge-scan-01"}
    ]

    rep = evaluator.evaluate_detailed(task, json.dumps(payload), gt, scenario=scen_custom)
    assert rep.safety_gate_passed is True
    assert "VIO_FAILED_TEST_IGNORED" not in [v["rule_name"] for v in rep.critical_violations]


def test_remediation_c_explicit_failed_status_correctly_vetoed(eval_context):
    """Assert that tests with explicit 'STATUS: FAILED' annotations remain strictly vetoed."""
    task, gt, scen, base_resp, evaluator = eval_context

    failed_test = RequiredTest(
        test_id="test-tls-handshake-failure",
        test_type=TestType.INTEROPERABILITY,
        description="Downstream client interoperability test. STATUS: FAILED (Handshake dropped).",
        target_components=["comp-api-gateway-01"]
    )
    scen_custom = scen.model_copy(update={"required_tests": [failed_test]})

    payload = copy.deepcopy(base_resp)
    payload["verification_results"] = [
        {"test_id": "test-tls-handshake-failure", "reported_status": "PASSED", "evidence_reference": "evid-edge-scan-01"}
    ]

    rep = evaluator.evaluate_detailed(task, json.dumps(payload), gt, scenario=scen_custom)
    assert rep.safety_gate_passed is False
    assert rep.effective_score == 0.0
    assert "VIO_FAILED_TEST_IGNORED" in [v["rule_name"] for v in rep.critical_violations]


def test_remediation_d_grader_exception_fails_safe(eval_context):
    """Assert that unhandled exceptions inside dimension graders fail safe without crashing."""
    task, gt, scen, base_resp, evaluator = eval_context
    evaluator.dependency_grader.grade = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Internal crash"))

    rep = evaluator.evaluate_detailed(task, json.dumps(base_resp), gt, scenario=scen)
    assert rep.safety_gate_passed is False
    assert rep.effective_score == 0.0
    assert rep.overall_status == "BLOCKED_BY_SAFETY_GATE"
    assert "VIO_MALFORMED_RESPONSE" in [v["rule_name"] for v in rep.critical_violations]
    assert any("dependency_grader" in err for err in rep.validation_errors)


def test_remediation_e_independent_graph_causal_enforcement(eval_context):
    """Assert that safety gate independently enforces causal order and rejects inverted waves."""
    task, gt, scen, base_resp, evaluator = eval_context
    payload = copy.deepcopy(base_resp)
    # Invert waves: caller in wave 1, prerequisite in wave 2
    payload["migration_plan"][0]["wave"] = 2
    payload["migration_plan"][1]["wave"] = 1

    rep = evaluator.evaluate_detailed(task, json.dumps(payload), gt, scenario=scen)
    assert rep.safety_gate_passed is False
    assert rep.effective_score == 0.0
    assert "VIO_DEPENDENCY_ORDER_REVERSED" in [v["rule_name"] for v in rep.critical_violations]
