"""Unit tests for safety gate enforcement, critical violation detection, and separate raw score reporting."""

import pytest

from phoenix_eval.evaluation.safety_gate import SafetyGateEngine
from phoenix_eval.evaluation.scoring_engine import (
    ScoringEngine,
    ScoringWeights,
)
from phoenix_eval.schemas import (
    ComponentType,
    CryptographicComponent,
    CryptographicRole,
)
from phoenix_eval.schemas.evaluation import CriticalViolation, ViolationSeverity
from phoenix_eval.schemas.response_contract import (
    ModelDecision,
    ModelResponseContract,
)
from phoenix_eval.schemas.scenarios import ScenarioModel


def empty_scenario() -> ScenarioModel:
    comp = CryptographicComponent(
        component_id="comp-dummy",
        component_name="Dummy Component",
        component_type=ComponentType.MICROSERVICE,
        cryptographic_role=CryptographicRole.TLS_TERMINATION,
        description="Dummy",
        technology="Python",
        current_algorithms=["AES-256-GCM"],
    )
    return ScenarioModel(
        scenario_id="scen-empty",
        scenario_name="Empty Scenario",
        description="Empty",
        system_components=[comp],
        dependencies=[],
        compatibility_records=[],
        required_tests=[],
        evidence_records=[],
        migration_constraints=[],
    )


def test_safety_gate_passes_when_clean() -> None:
    engine = SafetyGateEngine()
    scen = empty_scenario()
    contract = ModelResponseContract(
        task_id="t-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Clean response.",
    )
    res = engine.evaluate(
        contract=contract,
        scenario=scen,
        collected_violations=[],
        is_dag=True,
        readiness_blocked_by_gates=False,
    )
    assert res.safety_gate_passed is True
    assert res.readiness_decision == ModelDecision.MIGRATION_READY.value
    assert len(res.critical_violations) == 0


def test_safety_gate_veto_on_critical_violation() -> None:
    engine = SafetyGateEngine()
    scen = empty_scenario()
    crit_viol = CriticalViolation(
        violation_id="viol-01",
        rule_name="VIO_DEPENDENCY_ORDER_REVERSED",
        description="Critical causal inversion.",
        severity=ViolationSeverity.CRITICAL,
        evidence="comp-app before comp-db",
    )
    res = engine.evaluate(
        contract=None,
        scenario=scen,
        collected_violations=[crit_viol],
        is_dag=True,
        readiness_blocked_by_gates=False,
    )
    assert res.safety_gate_passed is False
    assert len(res.critical_violations) == 1


def test_safety_gate_veto_on_contradictory_decision() -> None:
    engine = SafetyGateEngine()
    scen = empty_scenario()
    contract = ModelResponseContract(
        task_id="t-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[],
        blocked_components=["comp-hsm-01"],  # Contradicts ready!
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Contradictory formulation.",
    )
    res = engine.evaluate(
        contract=contract,
        scenario=scen,
        collected_violations=[],
        is_dag=True,
        readiness_blocked_by_gates=False,
    )
    assert res.safety_gate_passed is False
    assert any(v.rule_name == "VIO_CONTRADICTORY_DECISION" for v in res.critical_violations)


def test_scoring_engine_preserves_raw_score_while_zeroing_effective_score() -> None:
    engine = ScoringEngine()

    # Create dimension results with total raw score = 85.0
    dim_results = {
        "dependency_identification": type(
            "DummyRes",
            (),
            {
                "dimension_name": "dependency_identification",
                "raw_score": 18.0,
                "max_score": 20.0,
                "normalized_score": 0.9,
                "deductions": [(2.0, "Minor omission")],
            },
        )(),
        "compatibility_reasoning": type(
            "DummyRes",
            (),
            {
                "dimension_name": "compatibility_reasoning",
                "raw_score": 20.0,
                "max_score": 20.0,
                "normalized_score": 1.0,
                "deductions": [],
            },
        )(),
        "migration_plan_correctness": type(
            "DummyRes",
            (),
            {
                "dimension_name": "migration_plan_correctness",
                "raw_score": 20.0,
                "max_score": 20.0,
                "normalized_score": 1.0,
                "deductions": [],
            },
        )(),
        "evidence_and_uncertainty": type(
            "DummyRes",
            (),
            {
                "dimension_name": "evidence_and_uncertainty",
                "raw_score": 12.0,
                "max_score": 15.0,
                "normalized_score": 0.8,
                "deductions": [],
            },
        )(),
        "validation_and_safety_gates": type(
            "DummyRes",
            (),
            {
                "dimension_name": "validation_and_safety_gates",
                "raw_score": 15.0,
                "max_score": 15.0,
                "normalized_score": 1.0,
                "deductions": [],
            },
        )(),
        "explanation_and_traceability": type(
            "DummyRes",
            (),
            {
                "dimension_name": "explanation_and_traceability",
                "raw_score": 10.0,
                "max_score": 10.0,
                "normalized_score": 1.0,
                "deductions": [],
            },
        )(),
    }

    # Case 1: Safety Gate Passed
    score_pass = engine.calculate_score(dim_results, safety_gate_passed=True)
    assert score_pass.safety_gate_passed is True
    assert score_pass.raw_weighted_score == 95.0
    assert score_pass.effective_score == 95.0
    assert score_pass.overall_status == "PASSED"

    # Case 2: Safety Gate Failed (Critical Violation)
    score_fail = engine.calculate_score(dim_results, safety_gate_passed=False)
    assert score_fail.safety_gate_passed is False
    assert score_fail.raw_weighted_score == 95.0  # PRESERVED for analysis!
    assert score_fail.effective_score == 0.0  # ZEROED OUT for safety!
    assert score_fail.overall_status == "BLOCKED_BY_SAFETY_GATE"


def test_scoring_weights_validation_sum_must_be_100() -> None:
    with pytest.raises(ValueError, match="must sum to exactly 100.0"):
        ScoringWeights(dependency_identification=30.0)  # total would be 110.0
