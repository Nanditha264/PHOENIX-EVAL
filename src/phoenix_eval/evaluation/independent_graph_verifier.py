"""Independently structured graph and causal precedence verification engine.

IMPORTANT EVALUATION PRINCIPLE (Rule B & Rule C):
This module is authored completely independently from the synthetic generator's
constraints.py and analyze_architecture_graph() oracle. It computes dependency
closures and validates migration wave orderings based on fundamental causal
precedence:

    If u depends on v, prerequisite v MUST be upgraded strictly prior to u.

It explicitly accepts alternative valid topological orderings and inter-branch
interleavings while rejecting causal inversions and cyclic deadlocks.
"""

from dataclasses import dataclass
from typing import Optional

from phoenix_eval.schemas.response_contract import ReportedMigrationStep
from phoenix_eval.schemas.scenarios import ScenarioModel


@dataclass(frozen=True)
class PlanVerificationResult:
    """Outcome of independently verifying a model's proposed migration plan."""

    is_valid: bool
    is_dag: bool
    causal_violations: list[tuple[str, str, int, int]]  # (caller, prereq, caller_wave, prereq_wave)
    omitted_components: list[str]
    duplicated_components: list[str]
    unknown_components: list[str]
    cycles_detected: list[list[str]]
    error_message: Optional[str] = None


class IndependentGraphVerifier:
    """Evaluator-side graph verifier independent of generator constraint logic."""

    def __init__(self, scenario: ScenarioModel) -> None:
        self.scenario_id = scenario.scenario_id
        self.all_component_ids: set[str] = {c.component_id for c in scenario.system_components}

        # Direct prerequisites: u depends on v => prereqs[u] contains v
        self.prereqs: dict[str, set[str]] = {cid: set() for cid in self.all_component_ids}
        # Direct dependents: u depends on v => callers[v] contains u
        self.callers: dict[str, set[str]] = {cid: set() for cid in self.all_component_ids}

        for edge in scenario.dependencies:
            src = edge.source_component_id
            tgt = edge.target_component_id
            if src in self.prereqs and tgt in self.all_component_ids:
                self.prereqs[src].add(tgt)
            if tgt in self.callers and src in self.all_component_ids:
                self.callers[tgt].add(src)

        # Transitive prerequisite closure computed via iterative reachability
        self.transitive_prereqs: dict[str, set[str]] = {}
        for cid in self.all_component_ids:
            visited: set[str] = set()
            stack = list(self.prereqs[cid])
            while stack:
                curr = stack.pop()
                if curr not in visited:
                    visited.add(curr)
                    stack.extend(self.prereqs.get(curr, set()) - visited)
            self.transitive_prereqs[cid] = visited

        # Independent Cycle Detection via Kahn's algorithm
        self._is_dag, self._cycles = self._detect_cycles_independently()

    @property
    def is_dag(self) -> bool:
        """Whether the scenario dependency graph is strictly acyclic."""
        return self._is_dag

    @property
    def cycles(self) -> list[list[str]]:
        """List of detected cycle paths, if any."""
        return self._cycles

    def _detect_cycles_independently(self) -> tuple[bool, list[list[str]]]:
        """Detect cycles using independent in-degree reduction and DFS path extraction."""
        in_degrees = {cid: len(self.prereqs[cid]) for cid in self.all_component_ids}
        queue = [cid for cid, deg in in_degrees.items() if deg == 0]
        processed_count = 0

        # Note: here in_degree in prereq graph means number of unmigrated prerequisites
        adj = {cid: set(self.callers[cid]) for cid in self.all_component_ids}
        prereq_counts = dict(in_degrees)

        while queue:
            curr = queue.pop(0)
            processed_count += 1
            for dependent in adj[curr]:
                prereq_counts[dependent] -= 1
                if prereq_counts[dependent] == 0:
                    queue.append(dependent)

        if processed_count == len(self.all_component_ids):
            return True, []

        # Find exact cycle paths using DFS among remaining nodes
        cycle_nodes = {cid for cid, count in prereq_counts.items() if count > 0}
        detected_cycles: list[list[str]] = []
        visited: set[str] = set()

        def dfs(node: str, path: list[str]) -> None:
            if node in path:
                cycle_start = path.index(node)
                cycle_path = path[cycle_start:] + [node]
                if cycle_path not in detected_cycles:
                    detected_cycles.append(cycle_path)
                return
            if node in visited:
                return

            visited.add(node)
            for neighbor in self.prereqs.get(node, set()):
                if neighbor in cycle_nodes:
                    dfs(neighbor, path + [node])

        for c in cycle_nodes:
            dfs(c, [])

        return False, detected_cycles

    def compute_independent_waves(self) -> list[list[str]]:
        """Compute independent baseline migration waves using pure set operations."""
        if not self._is_dag:
            return []

        migrated: set[str] = set()
        remaining = set(self.all_component_ids)
        waves: list[list[str]] = []

        while remaining:
            # Current wave consists of all components whose prerequisites are completely satisfied
            current_wave = sorted(
                [cid for cid in remaining if self.prereqs[cid].issubset(migrated)]
            )
            if not current_wave:
                # Should not happen if is_dag is True
                break
            waves.append(current_wave)
            migrated.update(current_wave)
            remaining.difference_update(current_wave)

        return waves

    def verify_plan(self, steps: list[ReportedMigrationStep]) -> PlanVerificationResult:
        """Verify that a proposed sequence of migration steps strictly respects causal prerequisites.

        Accepts:
            - Valid alternative topological orderings.
            - Interleaved independent dependency branches.
            - Valid alternative wave partitions where prerequisites precede callers.

        Rejects:
            - Any step where a caller is scheduled in a wave <= prerequisite wave.
            - Linear plans on cyclic graphs.
            - Plans with missing, duplicate, or unknown component IDs.
        """
        if not steps:
            return PlanVerificationResult(
                is_valid=False,
                is_dag=self._is_dag,
                causal_violations=[],
                omitted_components=sorted(self.all_component_ids),
                duplicated_components=[],
                unknown_components=[],
                cycles_detected=self._cycles,
                error_message="Migration plan is empty.",
            )

        # 1. Cyclic Graph Check
        if not self._is_dag:
            return PlanVerificationResult(
                is_valid=False,
                is_dag=False,
                causal_violations=[],
                omitted_components=[],
                duplicated_components=[],
                unknown_components=[],
                cycles_detected=self._cycles,
                error_message=f"Dependency graph contains directed cycles {self._cycles}; linear migration sequence is impossible.",
            )

        # 2. Extract scheduled components and waves
        step_wave_map: dict[str, int] = {}
        duplicated: set[str] = set()
        unknown: set[str] = set()

        for step in steps:
            cid = step.component_id
            if cid not in self.all_component_ids:
                unknown.add(cid)
            if cid in step_wave_map:
                duplicated.add(cid)
            step_wave_map[cid] = step.wave

        scheduled_comps = set(step_wave_map.keys()) - unknown
        omitted = self.all_component_ids - scheduled_comps

        # 3. Check Causal Precedence
        # For every edge (u, v) where u depends on v:
        # wave(v) MUST be strictly less than wave(u)
        causal_violations: list[tuple[str, str, int, int]] = []
        for caller, prereq_set in self.prereqs.items():
            if caller not in step_wave_map:
                continue
            caller_wave = step_wave_map[caller]
            for prereq in prereq_set:
                if prereq not in step_wave_map:
                    continue
                prereq_wave = step_wave_map[prereq]
                if prereq_wave >= caller_wave:
                    causal_violations.append((caller, prereq, caller_wave, prereq_wave))

        # Check Transitive Causal Closure
        for caller, trans_set in self.transitive_prereqs.items():
            if caller not in step_wave_map:
                continue
            caller_wave = step_wave_map[caller]
            for prereq in trans_set:
                if prereq in step_wave_map:
                    prereq_wave = step_wave_map[prereq]
                    if prereq_wave >= caller_wave:
                        viol = (caller, prereq, caller_wave, prereq_wave)
                        if viol not in causal_violations:
                            causal_violations.append(viol)

        is_valid = (
            len(causal_violations) == 0
            and len(omitted) == 0
            and len(duplicated) == 0
            and len(unknown) == 0
        )

        err_parts: list[str] = []
        if causal_violations:
            err_parts.append(
                f"{len(causal_violations)} causal ordering violations (e.g. caller '{causal_violations[0][0]}' in wave {causal_violations[0][2]} <= prerequisite '{causal_violations[0][1]}' in wave {causal_violations[0][3]})."
            )
        if omitted:
            err_parts.append(
                f"{len(omitted)} required components omitted from plan: {sorted(omitted)[:5]}."
            )
        if duplicated:
            err_parts.append(f"Components duplicated across multiple steps: {sorted(duplicated)}.")
        if unknown:
            err_parts.append(f"Unknown component IDs in plan: {sorted(unknown)}.")

        return PlanVerificationResult(
            is_valid=is_valid,
            is_dag=True,
            causal_violations=causal_violations,
            omitted_components=sorted(omitted),
            duplicated_components=sorted(duplicated),
            unknown_components=sorted(unknown),
            cycles_detected=[],
            error_message="; ".join(err_parts) if err_parts else None,
        )
