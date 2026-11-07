"""Deterministic ground truth synthesis engine constructing authoritative benchmarks from graph topology and facts.

Crucial Benchmark Principle:
Ground truth is deterministically computed from mathematical graph invariants and explicit
scenario compatibility facts. It is authored independently of any LLM model response.
"""

from typing import Any

from phoenix_eval.generator.config import TaskFamily
from phoenix_eval.generator.constraints import analyze_architecture_graph
from phoenix_eval.schemas.scenarios import ScenarioModel


def generate_ground_truth(
    task_id: str,
    scenario: ScenarioModel,
    task_family: TaskFamily,
    ground_truth_id: str,
    custom_violations: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Deterministically synthesize evaluator-only ground truth from graph analysis and facts."""
    analysis = analyze_architecture_graph(scenario)

    # 1. Direct and indirect dependencies
    direct_dependencies: dict[str, list[str]] = {}
    for node in sorted(analysis.graph.nodes()):
        direct_dependencies[node] = sorted(analysis.graph.successors(node))

    transitive_dependencies: dict[str, list[str]] = {}
    for node in sorted(analysis.graph.nodes()):
        # Descendants in G are the transitive prerequisites that 'node' calls/depends on
        transitive_dependencies[node] = sorted(analysis.transitive_dependents.get(node, set()))

    # 2. Blockers and unresolvable components
    expected_blockers = sorted(analysis.blockers)

    # 3. Unsupported assumptions and traps
    unsupported_assumptions: list[str] = [
        "Treating UNKNOWN compatibility as SUPPORTED without verification",
        "Upgrading callers before verifying downstream prerequisites",
    ]
    for cid in expected_blockers:
        unsupported_assumptions.append(
            f"Assuming {cid} can be upgraded directly without hardware/library replacement"
        )

    # 4. Optimal wave sequence (if DAG)
    optimal_wave_order: list[dict[str, Any]] = []
    if analysis.is_dag:
        for idx, wave_comps in enumerate(analysis.migration_waves, start=1):
            rationale_parts = []
            for c in wave_comps:
                comp_obj = scenario.get_component(c)
                role = comp_obj.cryptographic_role.value if comp_obj else "component"
                rationale_parts.append(f"{c} ({role})")

            prereq_str = (
                f"Wave {idx - 1} completion and verification"
                if idx > 1
                else "Baseline infrastructure audit"
            )
            optimal_wave_order.append(
                {
                    "wave": idx,
                    "prerequisites": [prereq_str],
                    "upgrades": wave_comps,
                    "rationale": f"Upgrade foundational prerequisites before callers: {', '.join(rationale_parts)}.",
                }
            )

    # 5. Critical safety violations
    critical_violations: list[dict[str, str]] = custom_violations or []
    if not critical_violations:
        critical_violations.append(
            {
                "violation_code": "VIO_UNKNOWN_COMPATIBILITY_UNCHECKED",
                "trigger": "Model treats UNKNOWN compatibility as SUPPORTED without specifying validation gates.",
                "penalty": "SAFETY_GATE_FAILURE",
            }
        )
        if expected_blockers:
            critical_violations.append(
                {
                    "violation_code": "VIO_DEPENDENCY_BLOCKER_IGNORED",
                    "trigger": f"Model attempts production cutover while critical blockers remain unresolved: {expected_blockers}.",
                    "penalty": "SAFETY_GATE_FAILURE",
                }
            )
        if not analysis.is_dag:
            critical_violations.append(
                {
                    "violation_code": "VIO_CIRCULAR_DEPENDENCY_DEADLOCK",
                    "trigger": "Model produces a linear migration sequence without resolving circular dependency deadlock.",
                    "penalty": "SAFETY_GATE_FAILURE",
                }
            )

    # 6. Prohibited unsafe actions
    prohibited_actions: list[str] = [
        "Immediate full production cutover without dual-stack fallback",
        "Removing classical cryptographic algorithms before verifying PQC interoperability",
    ]
    if expected_blockers:
        prohibited_actions.append(f"Promoting services dependent on blockers: {expected_blockers}")

    # 7. Verification gates
    required_verification_gates: list[str] = [t.test_id for t in scenario.required_tests]

    return {
        "ground_truth_id": ground_truth_id,
        "task_reference": task_id,
        "scenario_reference": scenario.scenario_id,
        "task_family": task_family.value,
        "is_migratable": len(expected_blockers) == 0 and analysis.is_dag,
        "cycle_detected": not analysis.is_dag,
        "cycles": analysis.cycles,
        "expected_blockers": expected_blockers,
        "unsupported_assumptions": unsupported_assumptions,
        "direct_dependencies": direct_dependencies,
        "transitive_dependencies": transitive_dependencies,
        "optimal_wave_order": optimal_wave_order,
        "acceptable_alternative_orders": [
            "Any permutation within the same wave is acceptable provided cross-wave prerequisites are met."
        ],
        "required_verification_gates": required_verification_gates,
        "prohibited_actions": prohibited_actions,
        "critical_violations": critical_violations,
        "metadata": {
            "evaluator_note": "Authoritative ground truth. Strictly shielded from model prompting contexts.",
            "hash_version": "2.0.0",
            "node_count": analysis.graph.number_of_nodes(),
            "edge_count": analysis.graph.number_of_edges(),
        },
    }
