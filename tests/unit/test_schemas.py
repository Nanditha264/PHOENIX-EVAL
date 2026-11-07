"""Unit tests for PHOENIX-EVAL data contracts and Pydantic schemas."""

import pytest
from pydantic import ValidationError

from phoenix_eval.core.exceptions import ScenarioError, SchemaValidationError
from phoenix_eval.schemas.common import ExecutionStatus, SafetyGateStatus, TokenUsage
from phoenix_eval.schemas.compatibility import CompatibilityRecord, CompatibilityStatus
from phoenix_eval.schemas.components import ComponentType, CryptographicComponent, CryptographicRole
from phoenix_eval.schemas.dependencies import (
    DependencyRelationship,
    RelationshipType,
)
from phoenix_eval.schemas.evaluation import (
    CriticalViolation,
    EvaluationResult,
    ViolationSeverity,
)
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.schemas.scenarios import ScenarioModel


def test_valid_cryptographic_component(sample_component: CryptographicComponent) -> None:
    """Verify that a well-formed component passes validation."""
    assert sample_component.component_id == "comp-auth-svc-01"
    assert sample_component.component_type == ComponentType.MICROSERVICE
    assert sample_component.cryptographic_role == CryptographicRole.AUTHENTICATION_TOKEN
    assert "RSA-2048" in sample_component.current_algorithms


def test_invalid_component_id_rejected() -> None:
    """Verify that invalid identifiers (e.g. whitespace, symbols) are rejected."""
    with pytest.raises((SchemaValidationError, ValidationError)):
        CryptographicComponent(
            component_id="invalid id with spaces!",
            component_name="Bad ID Component",
            component_type=ComponentType.SERVICE,
            cryptographic_role=CryptographicRole.TLS_TERMINATION,
            description="Test description",
            technology="Test Tech",
        )


def test_invalid_enum_rejected() -> None:
    """Verify that unsupported enum values are rejected."""
    with pytest.raises(ValidationError):
        CryptographicComponent(
            component_id="comp-valid-01",
            component_name="Invalid Role Comp",
            component_type=ComponentType.SERVICE,
            cryptographic_role="NON_EXISTENT_ROLE",  # type: ignore[arg-type]
            description="Test description",
            technology="Test Tech",
        )


def test_self_referential_dependency_rejected() -> None:
    """Verify that a dependency relationship where source equals target is rejected."""
    with pytest.raises(ValueError, match="Self-referential dependency not allowed"):
        DependencyRelationship(
            edge_id="edge-loop-01",
            source_component_id="comp-service-a",
            target_component_id="comp-service-a",
            relationship_type=RelationshipType.CALLS,
        )


def test_compatibility_unknown_semantics() -> None:
    """Verify that UNKNOWN compatibility remains UNKNOWN and does not allow unsafe assumptions."""
    rec = CompatibilityRecord(
        component_id="comp-test-01",
        proposed_target="ML-KEM-768",
        status=CompatibilityStatus.UNKNOWN,
        evidence_references=[],
        reason="Needs testing in lab.",
        assessment_source="Audit Team",
    )
    assert rec.status == CompatibilityStatus.UNKNOWN
    assert rec.is_safe_to_migrate is False

    # Attempting to associate UNKNOWN status with verified support claims must fail validation
    with pytest.raises(ValueError, match="Contradiction"):
        CompatibilityRecord(
            component_id="comp-test-01",
            proposed_target="ML-KEM-768",
            status=CompatibilityStatus.UNKNOWN,
            evidence_references=["evid-verified_support-01"],
            reason="Unverified claim",
            assessment_source="Contradictory Source",
        )


def test_compatibility_unsupported_requires_reason() -> None:
    """Verify that UNSUPPORTED status requires a justification reason."""
    with pytest.raises(ValidationError):
        CompatibilityRecord(
            component_id="comp-test-01",
            proposed_target="ML-KEM-768",
            status=CompatibilityStatus.UNSUPPORTED,
            evidence_references=[],
            reason="   ",  # Blank reason
            assessment_source="Lab",
        )


def test_scenario_detects_duplicate_component_ids(sample_component: CryptographicComponent) -> None:
    """Verify that duplicate component IDs in a scenario are detected and rejected."""
    with pytest.raises(ScenarioError, match="Duplicate component IDs"):
        ScenarioModel(
            scenario_id="scen-dup-01",
            scenario_name="Duplicate Scenario",
            description="Test description",
            system_components=[sample_component, sample_component],  # Duplicate!
            dependencies=[],
        )


def test_scenario_detects_dangling_dependency_edges(
    sample_component: CryptographicComponent,
) -> None:
    """Verify that dependency edges referencing non-existent components are rejected."""
    edge = DependencyRelationship(
        edge_id="edge-dangling-01",
        source_component_id=sample_component.component_id,
        target_component_id="comp-non-existent-99",  # Dangling!
        relationship_type=RelationshipType.CALLS,
    )
    with pytest.raises(ScenarioError, match="references unknown target"):
        ScenarioModel(
            scenario_id="scen-dangling-01",
            scenario_name="Dangling Scenario",
            description="Test description",
            system_components=[sample_component],
            dependencies=[edge],
        )


def test_scenario_detects_missing_evidence(sample_component: CryptographicComponent) -> None:
    """Verify that components or edges referencing non-existent evidence IDs are rejected."""
    # sample_component references "evid-auth-scan-01"
    # When evidence_records is empty, it must raise ScenarioError
    with pytest.raises(ScenarioError, match="references unknown evidence"):
        ScenarioModel(
            scenario_id="scen-missing-evid-01",
            scenario_name="Missing Evidence Scenario",
            description="Test description",
            system_components=[sample_component],
            dependencies=[],
            evidence_records=[],  # Missing "evid-auth-scan-01"!
        )


def test_model_response_and_token_usage() -> None:
    """Verify ModelResponse structure and TokenUsage validation."""
    resp = ModelResponse(
        response_id="resp-test-001",
        task_id="task-test-001",
        model_provider="mock",
        model_identifier="mock-model-v1",
        model_version="1.0",
        raw_response="Migration wave plan...",
        execution_status=ExecutionStatus.COMPLETED,
        token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        execution_duration=0.45,
        prompt_hash="abc123hash",
    )
    assert resp.token_usage is not None
    assert resp.token_usage.total_tokens == 150
    assert resp.execution_duration == 0.45


def test_evaluation_result_safety_gate_blocking() -> None:
    """Verify that a critical violation properly forces safety gate failure and status."""
    violation = CriticalViolation(
        violation_id="viol-01",
        rule_name="HSM_DEPENDENCY_BREACH",
        description="Attempted to migrate auth service without replacing legacy HSM.",
        severity=ViolationSeverity.CRITICAL,
        evidence="Model proposed direct upgrade of auth service in Wave 1.",
    )
    result = EvaluationResult(
        evaluation_id="eval-test-01",
        task_id="task-test-01",
        response_id="resp-test-01",
        criterion_scores=[],
        raw_score=0.0,
        safety_gate_status=SafetyGateStatus.FAILED,
        critical_violations=[violation],
        false_positive_count=1,
        final_status="BLOCKED_BY_SAFETY_GATE",
    )
    assert result.safety_gate_status == SafetyGateStatus.FAILED
    assert result.final_status == "BLOCKED_BY_SAFETY_GATE"
    assert len(result.critical_violations) == 1
