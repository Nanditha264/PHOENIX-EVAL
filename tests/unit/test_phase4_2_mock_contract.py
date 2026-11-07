"""Unit tests for Phase 4.2 Mock Response Contract Generation and Grounding."""

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.repository import GroundTruthRepository, ScenarioRepository, TaskRepository
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.response_parser import parse_model_response
from phoenix_eval.providers.base import MockBehavior, MockModelProvider, ProviderPromptRequest
from phoenix_eval.providers.fixtures import (
    load_mock_fixture,
    save_default_mock_fixtures,
)
from phoenix_eval.schemas.response_contract import ModelDecision


def test_mock_behavior_enum_and_aliases() -> None:
    """Verify MockBehavior enum supports valid_migration, unsafe_migration, and malformed_response."""
    assert MockBehavior.VALID_MIGRATION == "valid_migration"
    assert MockBehavior.UNSAFE_MIGRATION == "unsafe_migration"
    assert MockBehavior.MALFORMED_RESPONSE == "malformed_response"


def test_mock_provider_generates_valid_contract() -> None:
    """Verify VALID_MIGRATION mock provider produces a fully compliant ModelResponseContract."""
    paths = get_paths()
    task_repo = TaskRepository(paths.tasks_dir)
    scen_repo = ScenarioRepository(paths.scenarios_dir)

    task = task_repo.load_task("task-seq-pqc-001")
    scen = scen_repo.load_scenario(task.scenario_reference)

    provider = MockModelProvider(
        model_identifier="mock-valid-test",
        behavior=MockBehavior.VALID_MIGRATION,
    )

    request = ProviderPromptRequest(
        task_id="task-seq-pqc-001",
        prompt="Analyze cryptographic migration plan.",
        metadata={"task": task, "scenario": scen},
    )

    resp = provider.generate_response(request)
    assert resp.execution_status.value == "COMPLETED"
    assert resp.model_identifier == "mock-valid-test"
    assert resp.returned_model_identifier == "mock-valid-test"
    assert resp.provider_request_id == "mock-req-task-seq-pqc-001"

    # Verify response parses into ModelResponseContract
    parsed = parse_model_response(resp.raw_response)
    assert not parsed.is_malformed
    assert parsed.model_contract is not None
    contract = parsed.model_contract

    # Verify all strict contract fields are present
    assert contract.task_id == "task-seq-pqc-001"
    assert contract.contract_version == "1.0.0"
    assert isinstance(contract.decision, ModelDecision)
    assert isinstance(contract.migration_plan, list)
    assert isinstance(contract.compatibility_assessments, list)
    assert isinstance(contract.identified_dependencies, list)
    assert isinstance(contract.verification_results, list)
    assert isinstance(contract.evidence_references, list)
    assert isinstance(contract.explanation, str)
    assert len(contract.explanation) > 0


def test_mock_provider_unsafe_migration_triggers_safety_gate_failure() -> None:
    """Verify UNSAFE_MIGRATION mock produces valid schema but deliberately violates safety constraints."""
    paths = get_paths()
    task_repo = TaskRepository(paths.tasks_dir)
    scen_repo = ScenarioRepository(paths.scenarios_dir)
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)

    task = task_repo.load_task("task-seq-pqc-001")
    scen = scen_repo.load_scenario(task.scenario_reference)
    gt = gt_repo.load_ground_truth(task.ground_truth_reference)

    provider = MockModelProvider(
        model_identifier="mock-unsafe-test",
        behavior=MockBehavior.UNSAFE_MIGRATION,
    )

    request = ProviderPromptRequest(
        task_id="task-seq-pqc-001",
        prompt="Analyze migration.",
        metadata={"task": task, "scenario": scen},
    )

    resp = provider.generate_response(request)
    parsed = parse_model_response(resp.raw_response)
    # Valid JSON schema
    assert not parsed.is_malformed
    assert parsed.model_contract is not None

    # Evaluate with DeterministicEvaluator -> Must fail safety gate with effective_score=0.0
    evaluator = DeterministicEvaluator()
    report = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=resp.raw_response,
        ground_truth=gt,
        scenario=scen,
        model_identifier="mock-unsafe-test",
    )

    assert not report.safety_gate_passed
    assert report.effective_score == 0.0
    assert report.overall_status == "BLOCKED_BY_SAFETY_GATE"
    assert len(report.critical_violations) > 0


def test_mock_provider_malformed_response_fails_parsing() -> None:
    """Verify MALFORMED_RESPONSE produces broken JSON syntax / malformed contract."""
    provider = MockModelProvider(
        model_identifier="mock-malformed-test",
        behavior=MockBehavior.MALFORMED_RESPONSE,
    )

    request = ProviderPromptRequest(
        task_id="task-seq-pqc-001",
        prompt="Analyze migration.",
    )

    resp = provider.generate_response(request)
    parsed = parse_model_response(resp.raw_response)
    assert parsed.is_malformed
    assert parsed.model_contract is None


def test_static_mock_fixtures_evaluation_behavior() -> None:
    """Verify persisted static mock response fixtures evaluate according to their design contracts."""
    save_default_mock_fixtures()

    paths = get_paths()
    task_repo = TaskRepository(paths.tasks_dir)
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)

    task = task_repo.load_task("task-seq-pqc-001")
    gt = gt_repo.load_ground_truth(task.ground_truth_reference)
    evaluator = DeterministicEvaluator()

    # 1. Valid fixture: must pass safety gate and achieve high score
    valid_raw = load_mock_fixture("valid_migration")
    valid_rep = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=valid_raw,
        ground_truth=gt,
        model_identifier="fixture-valid",
    )
    assert valid_rep.is_valid_contract
    assert valid_rep.safety_gate_passed
    assert valid_rep.effective_score > 70.0
    assert valid_rep.overall_status == "PASSED"

    # 2. Unsafe fixture: valid JSON but fails safety gate
    unsafe_raw = load_mock_fixture("unsafe_migration")
    unsafe_rep = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=unsafe_raw,
        ground_truth=gt,
        model_identifier="fixture-unsafe",
    )
    assert unsafe_rep.is_valid_contract
    assert not unsafe_rep.safety_gate_passed
    assert unsafe_rep.effective_score == 0.0
    assert unsafe_rep.overall_status == "BLOCKED_BY_SAFETY_GATE"

    # 3. Malformed fixture: fails contract validation
    malformed_raw = load_mock_fixture("malformed_response")
    malformed_rep = evaluator.evaluate_detailed(
        task=task,
        raw_response_text=malformed_raw,
        ground_truth=gt,
        model_identifier="fixture-malformed",
    )
    assert not malformed_rep.is_valid_contract
    assert not malformed_rep.safety_gate_passed
    assert malformed_rep.effective_score == 0.0


def test_mock_provider_strict_ground_truth_isolation() -> None:
    """Verify MockModelProvider never receives or reads ground-truth artifacts."""
    paths = get_paths()
    provider = MockModelProvider(model_identifier="mock-leakage-test")

    # Pass only model-visible task and scenario
    task_repo = TaskRepository(paths.tasks_dir)
    scen_repo = ScenarioRepository(paths.scenarios_dir)
    task = task_repo.load_task("task-seq-pqc-001")
    scen = scen_repo.load_scenario(task.scenario_reference)

    request = ProviderPromptRequest(
        task_id="task-seq-pqc-001",
        prompt="Examine cryptographic components.",
        metadata={"task": task, "scenario": scen},
    )

    resp = provider.generate_response(request)

    # Assert response does not contain ground truth references
    assert "gt-seq-pqc-001" not in resp.raw_response
    assert "ground_truth" not in resp.raw_response.lower()
