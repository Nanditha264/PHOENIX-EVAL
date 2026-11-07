"""Unit tests for independent graph verifier: Kahn's cycle detection and alternative topological orders."""

from phoenix_eval.evaluation.independent_graph_verifier import IndependentGraphVerifier
from phoenix_eval.schemas import (
    ComponentType,
    CryptographicComponent,
    CryptographicRole,
    DependencyCriticality,
    DependencyRelationship,
    RelationshipType,
    ScenarioModel,
)
from phoenix_eval.schemas.response_contract import ReportedMigrationStep


def build_scenario_from_edges(edges: list[tuple[str, str]]) -> ScenarioModel:
    """Helper to construct scenario with specific dependency edges."""
    node_ids = sorted({n for edge in edges for n in edge})
    components = [
        CryptographicComponent(
            component_id=nid,
            component_name=f"Name {nid}",
            component_type=ComponentType.MICROSERVICE,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
            description="Service",
            technology="Go",
            current_algorithms=["RSA-2048"],
        )
        for nid in node_ids
    ]
    deps = [
        DependencyRelationship(
            edge_id=f"edge-{u}-{v}",
            source_component_id=u,
            target_component_id=v,
            relationship_type=RelationshipType.CALLS,
            criticality=DependencyCriticality.CRITICAL,
        )
        for u, v in edges
    ]
    return ScenarioModel(
        scenario_id="scen-verifier-test",
        scenario_name="Verifier Test Scenario",
        description="Testing independent graph verification",
        system_components=components,
        dependencies=deps,
        compatibility_records=[],
        required_tests=[],
        evidence_records=[],
        migration_constraints=[],
    )


def test_independent_graph_verifier_dag_detection() -> None:
    # A -> B -> C (A calls B, B calls C: C is foundation, B depends on C, A depends on B)
    # Prerequisite order: C must be upgraded before B, B before A
    edges = [("comp-a", "comp-b"), ("comp-b", "comp-c")]
    scen = build_scenario_from_edges(edges)
    verifier = IndependentGraphVerifier(scen)

    assert verifier.is_dag is True
    assert len(verifier.cycles) == 0


def test_independent_graph_verifier_cycle_detection() -> None:
    # Circular dependency: A -> B -> C -> A
    edges = [("comp-a", "comp-b"), ("comp-b", "comp-c"), ("comp-c", "comp-a")]
    scen = build_scenario_from_edges(edges)
    verifier = IndependentGraphVerifier(scen)

    assert verifier.is_dag is False
    assert len(verifier.cycles) > 0


def test_independent_graph_verifier_accepts_alternative_topological_sorts() -> None:
    # Diamond graph:
    # comp-app calls comp-auth and comp-pay
    # comp-auth calls comp-db
    # comp-pay calls comp-db
    # Foundational prerequisites: comp-db must be wave 1.
    # Independent branches: comp-auth and comp-pay can be upgraded in either order!
    edges = [
        ("comp-app", "comp-auth"),
        ("comp-app", "comp-pay"),
        ("comp-auth", "comp-db"),
        ("comp-pay", "comp-db"),
    ]
    scen = build_scenario_from_edges(edges)
    verifier = IndependentGraphVerifier(scen)

    # Order 1: auth in wave 2, pay in wave 3
    plan_order_1 = [
        ReportedMigrationStep(wave=1, component_id="comp-db"),
        ReportedMigrationStep(wave=2, component_id="comp-auth"),
        ReportedMigrationStep(wave=3, component_id="comp-pay"),
        ReportedMigrationStep(wave=4, component_id="comp-app"),
    ]
    res_1 = verifier.verify_plan(plan_order_1)
    assert res_1.is_valid is True
    assert len(res_1.causal_violations) == 0

    # Order 2: pay in wave 2, auth in wave 3 (valid alternative interleaving)
    plan_order_2 = [
        ReportedMigrationStep(wave=1, component_id="comp-db"),
        ReportedMigrationStep(wave=2, component_id="comp-pay"),
        ReportedMigrationStep(wave=3, component_id="comp-auth"),
        ReportedMigrationStep(wave=4, component_id="comp-app"),
    ]
    res_2 = verifier.verify_plan(plan_order_2)
    assert res_2.is_valid is True
    assert len(res_2.causal_violations) == 0

    # Order 3: auth and pay concurrently in wave 2
    plan_order_3 = [
        ReportedMigrationStep(wave=1, component_id="comp-db"),
        ReportedMigrationStep(wave=2, component_id="comp-auth"),
        ReportedMigrationStep(wave=2, component_id="comp-pay"),
        ReportedMigrationStep(wave=3, component_id="comp-app"),
    ]
    res_3 = verifier.verify_plan(plan_order_3)
    assert res_3.is_valid is True
    assert len(res_3.causal_violations) == 0


def test_independent_graph_verifier_detects_causal_violations() -> None:
    # Caller comp-app upgraded in wave 1 before target comp-db in wave 2
    edges = [("comp-app", "comp-db")]
    scen = build_scenario_from_edges(edges)
    verifier = IndependentGraphVerifier(scen)

    inverted_plan = [
        ReportedMigrationStep(wave=1, component_id="comp-app"),
        ReportedMigrationStep(wave=2, component_id="comp-db"),
    ]
    res = verifier.verify_plan(inverted_plan)
    assert res.is_valid is False
    assert len(res.causal_violations) > 0
    assert any(v[0] == "comp-app" and v[1] == "comp-db" for v in res.causal_violations)


def test_independent_graph_verifier_detects_same_wave_causal_conflict() -> None:
    # Caller comp-app and dependency comp-db in the exact same wave
    edges = [("comp-app", "comp-db")]
    scen = build_scenario_from_edges(edges)
    verifier = IndependentGraphVerifier(scen)

    same_wave_plan = [
        ReportedMigrationStep(wave=1, component_id="comp-app"),
        ReportedMigrationStep(wave=1, component_id="comp-db"),
    ]
    res = verifier.verify_plan(same_wave_plan)
    assert res.is_valid is False
    assert len(res.causal_violations) > 0
