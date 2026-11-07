"""Unit tests validating cryptographic dependency graph semantics and prerequisite ordering invariants."""

import networkx as nx

from phoenix_eval.generator.config import ArchitectureDomain, GraphComplexity, TaskFamily
from phoenix_eval.generator.constraints import (
    analyze_architecture_graph,
    verify_migration_wave_ordering,
)
from phoenix_eval.generator.scenario_generator import generate_scenario_for_task_family
from phoenix_eval.generator.seed_manager import SeedManager
from phoenix_eval.schemas.compatibility import CompatibilityStatus


def test_edge_direction_semantics() -> None:
    """Verify that edge (u, v) means u is dependent/caller and v is prerequisite/callee."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-edge-dir",
        task_family=TaskFamily.T05_MIGRATION_ORDERING,
        domain=ArchitectureDomain.BANKING_PAYMENTS,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    analysis = analyze_architecture_graph(scenario)

    # In G, edges run from caller to prerequisite
    for dep in scenario.dependencies:
        src = dep.source_component_id
        tgt = dep.target_component_id
        assert analysis.graph.has_edge(src, tgt)

        # In g_rev, edges run from prerequisite to caller
        g_rev = analysis.graph.reverse()
        assert g_rev.has_edge(tgt, src)


def test_prerequisite_migration_wave_ordering() -> None:
    """Verify that topological waves upgrade foundational prerequisites before callers."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-waves",
        task_family=TaskFamily.T05_MIGRATION_ORDERING,
        domain=ArchitectureDomain.ENTERPRISE_SERVICES,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    analysis = analyze_architecture_graph(scenario)
    assert analysis.is_dag is True
    assert len(analysis.migration_waves) > 0

    # Verify that the generated waves pass formal wave ordering verification
    is_valid, err = verify_migration_wave_ordering(analysis.graph, analysis.migration_waves)
    assert is_valid is True
    assert err is None


def test_migration_wave_ordering_breach_detection() -> None:
    """Verify that attempting to upgrade a caller before its prerequisite triggers a breach."""
    graph = nx.DiGraph()
    # Edge A -> B: A depends on B (B is prerequisite)
    graph.add_edge("comp-caller-A", "comp-prereq-B")

    # Inverted wave order: Caller A in Wave 1, Prerequisite B in Wave 2
    inverted_waves = [["comp-caller-A"], ["comp-prereq-B"]]
    is_valid, err = verify_migration_wave_ordering(graph, inverted_waves)
    assert is_valid is False
    assert "Dependency breach" in (err or "")

    # Valid wave order: Prerequisite B in Wave 1, Caller A in Wave 2
    valid_waves = [["comp-prereq-B"], ["comp-caller-A"]]
    is_valid, err = verify_migration_wave_ordering(graph, valid_waves)
    assert is_valid is True
    assert err is None


def test_cycle_detection_prevents_wave_generation() -> None:
    """Verify that cyclic architectures cannot produce linear migration waves."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-cycle",
        task_family=TaskFamily.T06_DEPENDENCY_CYCLE,
        domain=ArchitectureDomain.TELECOM_NETWORK,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    analysis = analyze_architecture_graph(scenario)
    assert analysis.is_dag is False
    assert len(analysis.cycles) > 0
    assert len(analysis.migration_waves) == 0


def test_blocker_detection_on_unsupported_components() -> None:
    """Verify that components with UNSUPPORTED or UNKNOWN status are identified as blockers."""
    seed_mgr = SeedManager(42)
    scenario = generate_scenario_for_task_family(
        scenario_id="scen-test-blocker",
        task_family=TaskFamily.T03_INCOMPATIBLE_CONSUMER,
        domain=ArchitectureDomain.CLOUD_IDENTITY,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    analysis = analyze_architecture_graph(scenario)
    assert len(analysis.blockers) > 0

    # Ensure all identified blockers indeed have UNSUPPORTED or UNKNOWN status
    compat_map = {c.component_id: c.status for c in scenario.compatibility_records}
    for b in analysis.blockers:
        assert compat_map[b] in (CompatibilityStatus.UNSUPPORTED, CompatibilityStatus.UNKNOWN)
