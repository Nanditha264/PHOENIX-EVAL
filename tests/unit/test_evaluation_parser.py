"""Unit tests for response parsing, markdown stripping, and semantic validation."""

import json

from phoenix_eval.evaluation.response_parser import extract_json_payload, parse_model_response
from phoenix_eval.evaluation.response_validator import validate_response_semantics
from phoenix_eval.schemas import (
    ComponentType,
    CryptographicComponent,
    CryptographicRole,
    DependencyCriticality,
    DependencyRelationship,
    EvidenceRecord,
    EvidenceType,
    RelationshipType,
    ScenarioModel,
)
from phoenix_eval.schemas.response_contract import (
    ModelDecision,
    ModelResponseContract,
    ReportedDependency,
    ReportedMigrationStep,
)


def create_minimal_scenario() -> ScenarioModel:
    """Helper to produce a sound minimal scenario for testing."""
    c1 = CryptographicComponent(
        component_id="comp-a",
        component_name="Component A",
        component_type=ComponentType.DATABASE,
        cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
        description="Storage",
        technology="PostgreSQL",
        current_algorithms=["AES-256-GCM"],
    )
    c2 = CryptographicComponent(
        component_id="comp-b",
        component_name="Component B",
        component_type=ComponentType.MICROSERVICE,
        cryptographic_role=CryptographicRole.DATA_ENCRYPTION_IN_TRANSIT,
        description="App",
        technology="Go",
        current_algorithms=["RSA-2048"],
    )
    dep = DependencyRelationship(
        edge_id="edge-b-a",
        source_component_id="comp-b",
        target_component_id="comp-a",
        relationship_type=RelationshipType.CALLS,
        criticality=DependencyCriticality.CRITICAL,
    )
    evid = EvidenceRecord(
        evidence_id="evid-01",
        evidence_type=EvidenceType.STATIC_CODE_ANALYSIS,
        source="scanner",
        description="Clean AST scan",
        observed_value="verified",
        confidence=1.0,
        provenance="scanner",
    )
    return ScenarioModel(
        scenario_id="scen-test-01",
        scenario_name="Test Scenario",
        description="Scenario for unit testing",
        system_components=[c1, c2],
        dependencies=[dep],
        compatibility_records=[],
        required_tests=[],
        evidence_records=[evid],
        migration_constraints=[],
    )


def test_extract_json_payload_plain_json() -> None:
    raw = '{"task_id": "test", "decision": "MIGRATION_READY"}'
    extracted = extract_json_payload(raw)
    assert json.loads(extracted) == {"task_id": "test", "decision": "MIGRATION_READY"}


def test_extract_json_payload_markdown_fenced() -> None:
    raw = """Here is my evaluation:
```json
{
  "task_id": "t-01",
  "decision": "MIGRATION_READY"
}
```
Thank you."""
    extracted = extract_json_payload(raw)
    parsed = json.loads(extracted)
    assert parsed["task_id"] == "t-01"
    assert parsed["decision"] == "MIGRATION_READY"


def test_extract_json_payload_unlabeled_code_fence() -> None:
    raw = """```
{"task_id": "t-02", "decision": "MIGRATION_BLOCKED"}
```"""
    extracted = extract_json_payload(raw)
    parsed = json.loads(extracted)
    assert parsed["task_id"] == "t-02"


def test_parse_model_response_valid_contract() -> None:
    payload = {
        "task_id": "task-test-01",
        "decision": "MIGRATION_READY",
        "identified_dependencies": [
            {"source_component_id": "comp-b", "target_component_id": "comp-a"}
        ],
        "compatibility_assessments": [{"component_id": "comp-a", "status": "SUPPORTED"}],
        "migration_plan": [
            {
                "wave": 1,
                "component_id": "comp-a",
                "preconditions": [],
                "required_validation_gates": [],
            }
        ],
        "blocked_components": [],
        "required_actions": [],
        "verification_results": [],
        "evidence_references": [],
        "assumptions": [],
        "uncertainties": [],
        "explanation": "Valid test response.",
        "contract_version": "1.0.0",
    }
    raw = json.dumps(payload)
    parsed = parse_model_response(raw)

    assert parsed.json_parsed is True
    assert parsed.is_valid_contract is True
    assert parsed.is_malformed is False
    assert parsed.model_contract is not None
    assert parsed.model_contract.decision == ModelDecision.MIGRATION_READY


def test_parse_model_response_malformed_truncated() -> None:
    truncated = '{"task_id": "task-01", "decision": "MIGRATION_READY", "dependencies": ['
    parsed = parse_model_response(truncated)

    assert parsed.json_parsed is False
    assert parsed.is_valid_contract is False
    assert parsed.is_malformed is True
    assert parsed.model_contract is None
    assert len(parsed.errors) > 0


def test_parse_model_response_missing_fields_validation_error() -> None:
    invalid_schema = '{"task_id": "task-01"}'  # missing decision, identified_dependencies, etc.
    parsed = parse_model_response(invalid_schema)

    assert parsed.json_parsed is True
    assert parsed.is_valid_contract is False
    assert parsed.is_malformed is True
    assert parsed.model_contract is None
    assert any("decision" in err for err in parsed.errors)


def test_validate_response_semantics_detects_contradictions() -> None:
    scen = create_minimal_scenario()
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[],
        blocked_components=["comp-a"],  # Contradicts MIGRATION_READY!
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Contradictory plan.",
    )
    result = validate_response_semantics(contract, scen)
    assert result.is_semantically_consistent is False
    assert any("contradiction" in err.lower() for err in result.contradictory_decisions)


def test_validate_response_semantics_detects_unknown_components() -> None:
    scen = create_minimal_scenario()
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_BLOCKED,
        identified_dependencies=[
            ReportedDependency(source_component_id="comp-ghost", target_component_id="comp-a")
        ],
        compatibility_assessments=[],
        migration_plan=[],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Unknown component referenced.",
    )
    result = validate_response_semantics(contract, scen)
    assert result.is_semantically_consistent is False
    assert "comp-ghost" in result.unknown_components


def test_validate_response_semantics_detects_duplicate_steps() -> None:
    scen = create_minimal_scenario()
    contract = ModelResponseContract(
        task_id="task-01",
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[],
        compatibility_assessments=[],
        migration_plan=[
            ReportedMigrationStep(wave=1, component_id="comp-a"),
            ReportedMigrationStep(wave=2, component_id="comp-a"),  # Duplicate!
        ],
        blocked_components=[],
        required_actions=[],
        verification_results=[],
        evidence_references=[],
        assumptions=[],
        uncertainties=[],
        explanation="Duplicate steps plan.",
    )
    result = validate_response_semantics(contract, scen)
    assert result.is_semantically_consistent is False
    assert "comp-a" in result.duplicate_steps
