"""Unit tests verifying generation and distinct reasoning invariants for all ten task families."""

import pytest

from phoenix_eval.generator.config import ArchitectureDomain, GraphComplexity, TaskFamily
from phoenix_eval.generator.ground_truth_generator import generate_ground_truth
from phoenix_eval.generator.scenario_generator import generate_scenario_for_task_family
from phoenix_eval.generator.seed_manager import SeedManager
from phoenix_eval.generator.task_generator import generate_task_for_scenario
from phoenix_eval.schemas.compatibility import CompatibilityStatus


@pytest.mark.parametrize("task_family", list(TaskFamily))
def test_generate_all_ten_task_families(task_family: TaskFamily) -> None:
    """Verify that every task family generates valid Scenario, Task, and Ground Truth models."""
    seed_mgr = SeedManager(100 + hash(task_family.value) % 1000)
    scen_id = f"scen-test-{task_family.value.lower()}"
    task_id = f"task-test-{task_family.value.lower()}"
    gt_id = f"gt-test-{task_family.value.lower()}"

    scenario = generate_scenario_for_task_family(
        scenario_id=scen_id,
        task_family=task_family,
        domain=ArchitectureDomain.BANKING_PAYMENTS,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    task = generate_task_for_scenario(
        task_id=task_id,
        scenario=scenario,
        task_family=task_family,
        ground_truth_id=gt_id,
        seed_mgr=seed_mgr,
    )
    gt = generate_ground_truth(
        task_id=task_id,
        scenario=scenario,
        task_family=task_family,
        ground_truth_id=gt_id,
    )

    # Core integrity
    assert scenario.scenario_id == scen_id
    assert task.task_id == task_id
    assert task.task_family == task_family.value
    assert task.scenario_reference == scen_id
    assert task.ground_truth_reference == gt_id
    assert gt["ground_truth_id"] == gt_id
    assert gt["task_reference"] == task_id
    assert gt["scenario_reference"] == scen_id
    assert len(task.evaluation_criteria) >= 2


def test_t01_hidden_dependency_properties() -> None:
    """Verify T01 introduces an indirect prerequisite path."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-t01",
        task_family=TaskFamily.T01_HIDDEN_DEPENDENCY,
        domain=ArchitectureDomain.BANKING_PAYMENTS,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    gt = generate_ground_truth("task-t01", scenario, TaskFamily.T01_HIDDEN_DEPENDENCY, "gt-t01")
    assert "transitive_dependencies" in gt
    # At least one component has multiple transitive prerequisites
    has_transitive = any(len(deps) > 1 for deps in gt["transitive_dependencies"].values())
    assert has_transitive is True


def test_t02_false_discovery_properties() -> None:
    """Verify T02 contains false discovery evidence contradicted by active telemetry."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-t02",
        task_family=TaskFamily.T02_FALSE_DISCOVERY,
        domain=ArchitectureDomain.ENTERPRISE_SERVICES,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    # Check that inactive comment evidence exists alongside active telemetry
    comment_evids = [e for e in scenario.evidence_records if "comment" in e.evidence_id]
    telemetry_evids = [e for e in scenario.evidence_records if "telemetry" in e.evidence_id]
    assert len(comment_evids) > 0
    assert len(telemetry_evids) > 0


def test_t06_dependency_cycle_properties() -> None:
    """Verify T06 scenario contains circular deadlock and ground truth flags cycle_detected."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-t06",
        task_family=TaskFamily.T06_DEPENDENCY_CYCLE,
        domain=ArchitectureDomain.CLOUD_IDENTITY,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    gt = generate_ground_truth("task-t06", scenario, TaskFamily.T06_DEPENDENCY_CYCLE, "gt-t06")
    assert gt["cycle_detected"] is True
    assert len(gt["cycles"]) > 0
    assert len(gt["optimal_wave_order"]) == 0


def test_t07_missing_validation_properties() -> None:
    """Verify T07 intentionally omits required validation evidence."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-t07",
        task_family=TaskFamily.T07_MISSING_VALIDATION,
        domain=ArchitectureDomain.GOVERNMENT_CRITICAL,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    assert len(scenario.required_tests) == 0
    gt = generate_ground_truth("task-t07", scenario, TaskFamily.T07_MISSING_VALIDATION, "gt-t07")
    assert len(gt["required_verification_gates"]) == 0


def test_t08_failed_interoperability_properties() -> None:
    """Verify T08 scenario contains a failing interoperability test."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-t08",
        task_family=TaskFamily.T08_FAILED_INTEROP,
        domain=ArchitectureDomain.TELECOM_NETWORK,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    failing_tests = [t for t in scenario.required_tests if "FAILED" in t.description]
    assert len(failing_tests) > 0


def test_t09_valid_migration_control_properties() -> None:
    """Verify T09 control scenario has all SUPPORTED components and is fully migratable."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-t09",
        task_family=TaskFamily.T09_VALID_MIGRATION,
        domain=ArchitectureDomain.BANKING_PAYMENTS,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    # All components must be SUPPORTED
    for c in scenario.compatibility_records:
        assert c.status == CompatibilityStatus.SUPPORTED

    gt = generate_ground_truth("task-t09", scenario, TaskFamily.T09_VALID_MIGRATION, "gt-t09")
    assert gt["is_migratable"] is True
    assert len(gt["expected_blockers"]) == 0
    assert len(gt["optimal_wave_order"]) > 0
