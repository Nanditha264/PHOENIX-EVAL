"""Graph and cross-artifact integrity validators for PHOENIX-EVAL."""

from typing import Any

import networkx as nx

from phoenix_eval.schemas.compatibility import CompatibilityStatus
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask


def analyze_scenario_graph(scenario: ScenarioModel) -> dict[str, Any]:
    """Perform graph-theoretic analysis on a Scenario's dependency network.

    Returns:
        Dictionary containing topological status, cycles, roots, leaves, and migration blockers.
    """
    g = scenario.to_networkx_graph()

    is_dag = nx.is_directed_acyclic_graph(g)
    cycles = list(nx.simple_cycles(g)) if not is_dag else []

    roots = [n for n, d in g.in_degree() if d == 0]
    leaves = [n for n, d in g.out_degree() if d == 0]
    isolated = list(nx.isolates(g))

    # Identify migration blockers: components with UNSUPPORTED or UNKNOWN compatibility
    # that have dependent components relying on them.
    compat_map = {c.component_id: c.status for c in scenario.compatibility_records}
    blockers = []
    for node in g.nodes():
        status = compat_map.get(node, CompatibilityStatus.UNKNOWN)
        in_degree = g.in_degree(node)
        if status in (CompatibilityStatus.UNSUPPORTED, CompatibilityStatus.UNKNOWN):
            blockers.append(
                {
                    "component_id": node,
                    "status": status.value,
                    "dependents_count": in_degree,
                    "severity": "CRITICAL" if in_degree > 0 else "LOW",
                }
            )

    return {
        "scenario_id": scenario.scenario_id,
        "node_count": g.number_of_nodes(),
        "edge_count": g.number_of_edges(),
        "is_dag": is_dag,
        "has_circular_dependencies": len(cycles) > 0,
        "circular_dependency_cycles": cycles,
        "root_components": roots,
        "leaf_components": leaves,
        "isolated_components": isolated,
        "identified_blockers": blockers,
    }


def validate_cross_artifact_integrity(
    scenarios: dict[str, ScenarioModel],
    tasks: dict[str, BenchmarkTask],
    ground_truth_ids: set[str],
) -> list[str]:
    """Validate referential integrity between tasks, scenarios, and ground-truth artifacts.

    Returns:
        List of error messages. Empty list if integrity is completely valid.
    """
    errors: list[str] = []

    for task_id, task in tasks.items():
        if task.scenario_reference not in scenarios:
            errors.append(
                f"Task '{task_id}' references unknown scenario '{task.scenario_reference}'."
            )
        if task.ground_truth_reference not in ground_truth_ids:
            errors.append(
                f"Task '{task_id}' references missing ground truth '{task.ground_truth_reference}'."
            )

    return errors
