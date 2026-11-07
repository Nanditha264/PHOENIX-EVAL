"""Graph semantics, topological constraint verification, and migration wave analysis using NetworkX.

Edge Direction Convention (MANDATORY & UNAMBIGUOUS):
In PHOENIX-EVAL, every directed dependency edge (u, v) is defined as:
    u = source_component_id  (CALLER / DEPENDENT / CONSUMER)
    v = target_component_id  (DEPENDENCY / PREREQUISITE / PROVIDER)

Prerequisite Rule:
Because u depends on v, component v is a PREREQUISITE for component u.
In any cryptographic transition, prerequisite v must be upgraded prior to or concurrently
with dependent u (in dual-stack hybrid mode).

Topological Sorting & Wave Calculation:
To compute the valid migration wave sequence:
1. Construct the dependency graph G where edges represent (caller -> prerequisite).
2. The reversed graph G_rev = G.reverse() has edges (prerequisite -> caller).
3. Topological generations on G_rev yield the optimal wave sequence:
   - Wave 1: Sinks of G (out-degree 0 in G; e.g. HSM, DB, foundational CAs).
   - Wave 2: Middle-tier microservices that depend on Wave 1 sinks.
   - Wave 3: Ingress API gateways and client fleets that depend on Wave 2.
"""

from typing import Any, Optional

import networkx as nx

from phoenix_eval.schemas.compatibility import CompatibilityRecord, CompatibilityStatus
from phoenix_eval.schemas.scenarios import ScenarioModel


class GraphAnalysisResult:
    """Encapsulates structural and topological properties of an architectural scenario."""

    def __init__(
        self,
        graph: nx.DiGraph,
        is_dag: bool,
        cycles: list[list[str]],
        root_callers: list[str],
        leaf_prerequisites: list[str],
        migration_waves: list[list[str]],
        blockers: list[str],
        transitive_dependents: dict[str, set[str]],
    ) -> None:
        self.graph = graph
        self.is_dag = is_dag
        self.cycles = cycles
        self.root_callers = root_callers
        self.leaf_prerequisites = leaf_prerequisites
        self.migration_waves = migration_waves
        self.blockers = blockers
        self.transitive_dependents = transitive_dependents

    def to_dict(self) -> dict[str, Any]:
        """Export analysis as a structured dictionary."""
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "is_dag": self.is_dag,
            "cycles": self.cycles,
            "root_callers": self.root_callers,
            "leaf_prerequisites": self.leaf_prerequisites,
            "migration_waves": self.migration_waves,
            "blockers": self.blockers,
        }


def analyze_architecture_graph(scenario: ScenarioModel) -> GraphAnalysisResult:
    """Perform comprehensive topological and migration prerequisite analysis over a scenario."""
    graph = scenario.to_networkx_graph()

    # Cycle detection
    is_dag = nx.is_directed_acyclic_graph(graph)
    cycles: list[list[str]] = []
    if not is_dag:
        cycles = [list(c) for c in nx.simple_cycles(graph)]

    # Ingress callers (in-degree == 0 in G: nobody calls them, they initiate calls)
    root_callers = sorted([n for n, deg in graph.in_degree() if deg == 0])

    # Leaf prerequisites (out-degree == 0 in G: they do not depend on anything further down)
    leaf_prerequisites = sorted([n for n, deg in graph.out_degree() if deg == 0])

    # Calculate transitive dependents:
    # If u -> ... -> v in G, then u depends on v, so u is a dependent of v.
    # In G_rev, path is v -> ... -> u.
    g_rev = graph.reverse()
    transitive_dependents: dict[str, set[str]] = {}
    for node in graph.nodes():
        # Nodes reachable from 'node' in g_rev are components that depend on 'node'
        transitive_dependents[node] = nx.descendants(g_rev, node)

    # Blocker analysis
    # A component is a blocker if its target compatibility is UNSUPPORTED or UNKNOWN,
    # as this prevents verified, unblocked migration to the target cryptographic state.
    blockers: list[str] = []
    compat_map: dict[str, CompatibilityRecord] = {
        c.component_id: c for c in scenario.compatibility_records
    }

    for comp in scenario.system_components:
        cid = comp.component_id
        record = compat_map.get(cid)
        if record and record.status in (
            CompatibilityStatus.UNSUPPORTED,
            CompatibilityStatus.UNKNOWN,
        ):
            blockers.append(cid)

    # Migration wave calculation
    # Only possible if graph is a DAG
    migration_waves: list[list[str]] = []
    if is_dag:
        # Topological generations on reversed graph (prerequisites first)
        for gen in nx.topological_generations(g_rev):
            migration_waves.append(sorted(gen))

    return GraphAnalysisResult(
        graph=graph,
        is_dag=is_dag,
        cycles=cycles,
        root_callers=root_callers,
        leaf_prerequisites=leaf_prerequisites,
        migration_waves=migration_waves,
        blockers=sorted(set(blockers)),
        transitive_dependents=transitive_dependents,
    )


def verify_migration_wave_ordering(
    graph: nx.DiGraph,
    proposed_waves: list[list[str]],
) -> tuple[bool, Optional[str]]:
    """Verify that a proposed sequence of migration waves strictly respects dependency prerequisites.

    Returns:
        (is_valid, error_reason)
    """
    seen: set[str] = set()
    node_to_wave: dict[str, int] = {}

    for wave_idx, wave in enumerate(proposed_waves):
        for comp in wave:
            if comp in seen:
                return False, f"Component '{comp}' appears in multiple migration waves."
            seen.add(comp)
            node_to_wave[comp] = wave_idx

    # All nodes in graph must be accounted for
    missing = set(graph.nodes()) - seen
    if missing:
        return False, f"Proposed migration plan is missing components: {sorted(missing)}"

    # Check every edge (u, v): u depends on v, so v must be in wave <= u
    for u, v in graph.edges():
        wave_u = node_to_wave[u]
        wave_v = node_to_wave[v]
        if wave_v > wave_u:
            return (
                False,
                f"Dependency breach: Dependent component '{u}' (wave {wave_u + 1}) "
                f"is scheduled before its prerequisite '{v}' (wave {wave_v + 1}).",
            )

    return True, None
