"""Unit tests for NetworkX graph conversion, topological analysis, and cycle detection."""

import networkx as nx

from phoenix_eval.data.validators import analyze_scenario_graph
from phoenix_eval.schemas.components import ComponentType, CryptographicComponent, CryptographicRole
from phoenix_eval.schemas.dependencies import DependencyRelationship, RelationshipType
from phoenix_eval.schemas.scenarios import ScenarioModel


def test_scenario_to_networkx_graph(sample_scenario: ScenarioModel) -> None:
    """Verify conversion of ScenarioModel to a directed NetworkX graph."""
    graph = sample_scenario.to_networkx_graph()

    assert isinstance(graph, nx.DiGraph)
    assert graph.number_of_nodes() == len(sample_scenario.system_components)
    assert graph.number_of_edges() == len(sample_scenario.dependencies)

    # Check node attributes
    for comp in sample_scenario.system_components:
        assert comp.component_id in graph
        assert graph.nodes[comp.component_id]["role"] == comp.cryptographic_role.value

    # Check edge attributes
    for dep in sample_scenario.dependencies:
        assert graph.has_edge(dep.source_component_id, dep.target_component_id)
        assert (
            graph.edges[dep.source_component_id, dep.target_component_id]["relationship_type"]
            == dep.relationship_type.value
        )


def test_graph_cycle_detection() -> None:
    """Verify that circular dependencies (A -> B -> C -> A) are detected."""
    c1 = CryptographicComponent(
        component_id="comp-a",
        component_name="Comp A",
        component_type=ComponentType.SERVICE,
        cryptographic_role=CryptographicRole.TLS_TERMINATION,
        description="A",
        technology="Java",
    )
    c2 = CryptographicComponent(
        component_id="comp-b",
        component_name="Comp B",
        component_type=ComponentType.SERVICE,
        cryptographic_role=CryptographicRole.KEY_EXCHANGE,
        description="B",
        technology="Java",
    )
    c3 = CryptographicComponent(
        component_id="comp-c",
        component_name="Comp C",
        component_type=ComponentType.SERVICE,
        cryptographic_role=CryptographicRole.DIGITAL_SIGNATURE,
        description="C",
        technology="Java",
    )

    # Circular chain: A -> B -> C -> A
    e1 = DependencyRelationship(
        edge_id="e1",
        source_component_id="comp-a",
        target_component_id="comp-b",
        relationship_type=RelationshipType.CALLS,
    )
    e2 = DependencyRelationship(
        edge_id="e2",
        source_component_id="comp-b",
        target_component_id="comp-c",
        relationship_type=RelationshipType.CALLS,
    )
    e3 = DependencyRelationship(
        edge_id="e3",
        source_component_id="comp-c",
        target_component_id="comp-a",
        relationship_type=RelationshipType.CALLS,
    )

    cyclic_scenario = ScenarioModel(
        scenario_id="scen-cyclic-01",
        scenario_name="Cyclic Scenario",
        description="Architecture with mutual circular dependency.",
        system_components=[c1, c2, c3],
        dependencies=[e1, e2, e3],
    )

    analysis = analyze_scenario_graph(cyclic_scenario)
    assert analysis["is_dag"] is False
    assert analysis["has_circular_dependencies"] is True
    assert len(analysis["circular_dependency_cycles"]) > 0


def test_migration_blocker_detection(sample_scenario: ScenarioModel) -> None:
    """Verify that components with UNSUPPORTED or UNKNOWN compatibility are identified as blockers."""
    analysis = analyze_scenario_graph(sample_scenario)
    blockers = analysis["identified_blockers"]

    # comp-auth-svc-01 has UNKNOWN compatibility in sample_scenario
    assert any(b["component_id"] == "comp-auth-svc-01" for b in blockers)
