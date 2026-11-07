"""Automated cross-artifact seed dataset integrity tests for PHOENIX-EVAL Phase 1."""

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.repository import GroundTruthRepository, ScenarioRepository, TaskRepository
from phoenix_eval.data.validators import analyze_scenario_graph
from phoenix_eval.schemas.compatibility import CompatibilityStatus


def test_seed_dataset_cross_referential_integrity() -> None:
    """Verify referential integrity across seed scenario, task, and ground-truth artifacts."""
    paths = get_paths()
    scen_repo = ScenarioRepository(paths.scenarios_dir)
    task_repo = TaskRepository(paths.tasks_dir)
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)

    # 1. Load seed scenario
    scenario = scen_repo.load_scenario("scen-pqc-tls-banking-001")
    assert scenario.scenario_id == "scen-pqc-tls-banking-001"

    comp_ids = {c.component_id for c in scenario.system_components}
    assert len(comp_ids) == len(scenario.system_components), "Duplicate component IDs in scenario"

    evid_ids = {e.evidence_id for e in scenario.evidence_records}
    assert len(evid_ids) == len(scenario.evidence_records), "Duplicate evidence IDs in scenario"

    # 2. Verify all dependency edges reference valid components and evidence
    for dep in scenario.dependencies:
        assert dep.source_component_id in comp_ids, (
            f"Dependency edge '{dep.edge_id}' source '{dep.source_component_id}' not found"
        )
        assert dep.target_component_id in comp_ids, (
            f"Dependency edge '{dep.edge_id}' target '{dep.target_component_id}' not found"
        )
        for ref in dep.evidence_references:
            assert ref in evid_ids, (
                f"Dependency edge '{dep.edge_id}' references unknown evidence '{ref}'"
            )

    # 3. Verify all component evidence references exist
    for comp in scenario.system_components:
        for ref in comp.evidence_references:
            assert ref in evid_ids, (
                f"Component '{comp.component_id}' references unknown evidence '{ref}'"
            )

    # 4. Verify all compatibility records reference valid components and evidence
    for cp in scenario.compatibility_records:
        assert cp.component_id in comp_ids, (
            f"Compatibility record references unknown component '{cp.component_id}'"
        )
        for ref in cp.evidence_references:
            assert ref in evid_ids, (
                f"Compatibility record for '{cp.component_id}' references unknown evidence '{ref}'"
            )

    # 5. Verify constraints and tests reference valid components
    for cnstr in scenario.migration_constraints:
        for aff in cnstr.affected_components:
            assert aff in comp_ids, (
                f"Constraint '{cnstr.constraint_id}' references unknown component '{aff}'"
            )

    for test in scenario.required_tests:
        for tgt in test.target_components:
            assert tgt in comp_ids, (
                f"RequiredTest '{test.test_id}' references unknown component '{tgt}'"
            )

    # 6. Verify task references
    task = task_repo.load_task("task-seq-pqc-001")
    assert task.scenario_reference == scenario.scenario_id, (
        "Task scenario_reference does not match scenario ID"
    )
    assert gt_repo.has_ground_truth(task.ground_truth_reference), (
        f"Task ground_truth_reference '{task.ground_truth_reference}' not found on disk"
    )

    # 7. Verify ground truth references
    gt_data = gt_repo.load_ground_truth(task.ground_truth_reference)
    assert gt_data["task_reference"] == task.task_id, (
        "Ground truth task_reference does not match task ID"
    )
    assert gt_data["scenario_reference"] == scenario.scenario_id, (
        "Ground truth scenario_reference does not match scenario ID"
    )


def test_seed_dataset_no_ground_truth_leakage_in_task() -> None:
    """Verify that the task does not leak ground-truth answers in its description, instructions, or criteria."""
    paths = get_paths()
    task_repo = TaskRepository(paths.tasks_dir)
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)

    task = task_repo.load_task("task-seq-pqc-001")
    gt = gt_repo.load_ground_truth(task.ground_truth_reference)

    expected_blockers = set(gt["expected_blockers"])  # {'comp-hsm-legacy-03', 'comp-edge-gw-01'}

    # Check criteria descriptions: they must describe the rubric objective without giving away the exact blocker list
    for crit in task.evaluation_criteria:
        for blocker in expected_blockers:
            assert blocker not in crit.description, (
                f"Ground truth blocker '{blocker}' leaked in criterion '{crit.criterion_id}' description!"
            )

    # Check task description and instructions
    assert "gt-seq-pqc-001" not in task.description
    assert "gt-seq-pqc-001" not in task.task_instructions


def test_seed_dataset_topological_consistency() -> None:
    """Verify that optimal migration wave sequence respects the scenario dependency graph."""
    paths = get_paths()
    scen_repo = ScenarioRepository(paths.scenarios_dir)
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)

    scenario = scen_repo.load_scenario("scen-pqc-tls-banking-001")
    gt = gt_repo.load_ground_truth("gt-seq-pqc-001")

    graph_analysis = analyze_scenario_graph(scenario)
    assert graph_analysis["is_dag"] is True, "Seed banking scenario must be a DAG"

    # Verify blockers in ground truth match graph analysis identified blockers
    identified_blocker_ids = {b["component_id"] for b in graph_analysis["identified_blockers"]}
    for expected_b in gt["expected_blockers"]:
        assert expected_b in identified_blocker_ids, (
            f"Expected blocker '{expected_b}' not identified by graph analysis"
        )

    # Verify wave ordering respects dependencies:
    # Wave 1: Edge GW and HSM
    # Wave 2: Auth Service (calls HSM)
    # Wave 3: Mobile Client (calls Edge GW)
    waves = gt["optimal_wave_order"]
    assert len(waves) == 3
    wave1_comps = set(waves[0]["upgrades"])
    wave2_comps = set(waves[1]["upgrades"])
    wave3_comps = set(waves[2]["upgrades"])

    assert "comp-edge-gw-01" in wave1_comps
    assert "comp-hsm-legacy-03" in wave1_comps
    assert "comp-auth-svc-02" in wave2_comps
    assert "comp-mobile-sdk-05" in wave3_comps


def test_seed_dataset_unknown_compatibility_semantics() -> None:
    """Verify that UNKNOWN compatibility records in seed scenario are not safe to migrate."""
    paths = get_paths()
    scen_repo = ScenarioRepository(paths.scenarios_dir)
    scenario = scen_repo.load_scenario("scen-pqc-tls-banking-001")

    unknown_records = [
        c for c in scenario.compatibility_records if c.status == CompatibilityStatus.UNKNOWN
    ]
    assert len(unknown_records) == 2  # comp-auth-svc-02 and comp-mobile-sdk-05

    for rec in unknown_records:
        assert rec.is_safe_to_migrate is False
        assert rec.status == CompatibilityStatus.UNKNOWN
