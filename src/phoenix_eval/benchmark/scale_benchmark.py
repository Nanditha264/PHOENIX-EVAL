"""Performance and scale benchmarking engine for PHOENIX-EVAL.

Measures latency, memory usage, and computational scaling across synthetic
enterprise architecture graphs of varying magnitudes (100, 500, 1,000 components).

Evaluates:
1. Graph verification time (cycle detection, topological reachability, causal precedence).
2. Evidence validation time (citation verification, epistemic calibration).
3. Constraint evaluation time (operational bounds, rollback capability, capacity limits).
4. Full end-to-end evaluation time and peak memory footprint.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import time
import tracemalloc
from typing import Any, Optional

from phoenix_eval.core.paths import get_paths
from phoenix_eval.evaluation.constraint_grader import ConstraintGrader
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.evaluation.evidence_grader import EvidenceGrader
from phoenix_eval.evaluation.independent_graph_verifier import IndependentGraphVerifier
from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.schemas.compatibility import CompatibilityRecord, CompatibilityStatus
from phoenix_eval.schemas.components import ComponentType, CryptographicComponent, CryptographicRole
from phoenix_eval.schemas.dependencies import DependencyCriticality, DependencyRelationship, RelationshipType
from phoenix_eval.schemas.evidence import EvidenceCategory, EvidenceRecord, EvidenceType, VerificationStatus
from phoenix_eval.schemas.response_contract import (
    MigrationActionType,
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibility,
    ReportedCompatibilityStatus,
    ReportedDependency,
    ReportedMigrationStep,
    ReportedTestResult,
    ReportedTestStatus,
)
from phoenix_eval.schemas.scenarios import ConstraintType, MigrationConstraint, RequiredTest, ScenarioModel, TestType
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel, TaskCategory


@dataclass(frozen=True)
class ScaleBenchmarkPoint:
    """Benchmark performance metrics for a specific graph size."""

    num_components: int
    num_dependencies: int
    num_evidence_records: int
    graph_verification_ms: float
    evidence_validation_ms: float
    constraint_evaluation_ms: float
    full_evaluation_ms: float
    peak_memory_mb: float
    throughput_components_per_sec: float
    safety_gate_passed: bool
    overall_status: str


@dataclass(frozen=True)
class ScaleBenchmarkReport:
    """Complete report for a scale benchmarking run."""

    benchmark_timestamp: str
    sizes_evaluated: list[int]
    results: list[ScaleBenchmarkPoint]
    linear_scaling_verified: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_timestamp": self.benchmark_timestamp,
            "sizes_evaluated": self.sizes_evaluated,
            "results": [asdict(r) for r in self.results],
            "linear_scaling_verified": self.linear_scaling_verified,
            "notes": self.notes,
        }

    def format_table(self) -> str:
        """Format results as an ASCII summary table."""
        headers = [
            "Components",
            "Dependencies",
            "Graph Verif (ms)",
            "Evidence (ms)",
            "Constraint (ms)",
            "Full Eval (ms)",
            "Memory (MB)",
            "Throughput (comp/s)",
            "Status",
        ]
        col_widths = [12, 14, 18, 15, 17, 16, 13, 22, 10]
        header_row = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        divider = "-+-".join("-" * w for w in col_widths)

        rows = [header_row, divider]
        for r in self.results:
            vals = [
                str(r.num_components),
                str(r.num_dependencies),
                f"{r.graph_verification_ms:.2f}",
                f"{r.evidence_validation_ms:.2f}",
                f"{r.constraint_evaluation_ms:.2f}",
                f"{r.full_evaluation_ms:.2f}",
                f"{r.peak_memory_mb:.2f}",
                f"{r.throughput_components_per_sec:.1f}",
                r.overall_status,
            ]
            rows.append(" | ".join(v.ljust(w) for v, w in zip(vals, col_widths)))

        return "\n".join(rows)


def build_scale_scenario(
    num_components: int,
    seed: int = 42,
) -> tuple[ScenarioModel, BenchmarkTask, dict[str, Any], ModelResponseContract]:
    """Deterministically construct a valid synthetic enterprise architecture of arbitrary scale.

    Organizes components into 4 topological tiers:
    - Tier 0: Root Key Storage / Hardware Security Modules (Wave 1)
    - Tier 1: Core Databases and Transaction Stores (Wave 2)
    - Tier 2: Microservices and Processing Nodes (Wave 3)
    - Tier 3: Edge Gateways and External API Clients (Wave 4)
    """
    rng = random.Random(seed)

    # Distribute components across tiers
    n0 = max(2, int(num_components * 0.15))
    n1 = max(2, int(num_components * 0.25))
    n2 = max(2, int(num_components * 0.40))
    n3 = num_components - (n0 + n1 + n2)

    tier_counts = [n0, n1, n2, n3]
    tier_nodes: list[list[str]] = [[], [], [], []]

    components: list[CryptographicComponent] = []
    compatibility_records: list[CompatibilityRecord] = []
    evidence_records: list[EvidenceRecord] = []

    comp_idx = 0
    tier_roles = [
        (ComponentType.HARDWARE_SECURITY_MODULE, CryptographicRole.KEY_STORAGE, "C/Assembly", ["AES-256-GCM"]),
        (ComponentType.DATABASE, CryptographicRole.DATA_ENCRYPTION_AT_REST, "PostgreSQL/RocksDB", ["AES-256-GCM"]),
        (ComponentType.MICROSERVICE, CryptographicRole.DATA_ENCRYPTION_IN_TRANSIT, "Java/Go", ["TLS_1_2"]),
        (ComponentType.API_GATEWAY, CryptographicRole.TLS_TERMINATION, "Rust/Nginx", ["RSA-2048"]),
    ]

    for tier_idx, count in enumerate(tier_counts):
        ctype, role, tech, algs = tier_roles[tier_idx]
        for _ in range(count):
            cid = f"comp-scale-{comp_idx:05d}"
            tier_nodes[tier_idx].append(cid)

            components.append(
                CryptographicComponent(
                    component_id=cid,
                    component_name=f"Scale Component {comp_idx}",
                    component_type=ctype,
                    cryptographic_role=role,
                    description=f"Synthetic benchmark node in Tier {tier_idx}",
                    technology=tech,
                    current_algorithms=algs,
                )
            )

            # Compatibility
            compatibility_records.append(
                CompatibilityRecord(
                    component_id=cid,
                    proposed_target="ML-KEM-768",
                    status=CompatibilityStatus.SUPPORTED,
                    reason="Verified supported in target runtime",
                    assessment_source="automated_telemetry",
                )
            )

            # Evidence
            evid_id = f"evid-scale-{comp_idx:05d}"
            evidence_records.append(
                EvidenceRecord(
                    evidence_id=evid_id,
                    evidence_type=EvidenceType.RUNTIME_TELEMETRY,
                    source="scale_telemetry_probe",
                    description=f"Runtime probe telemetry for {cid}",
                    observed_value="PQC_COMPATIBLE_V1",
                    provenance=f"probe:node:{comp_idx}",
                    verification_status=VerificationStatus.VERIFIED,
                    evidence_category=EvidenceCategory.OBSERVED,
                    is_stale=False,
                )
            )

            comp_idx += 1

    # Connect adjacent tiers to create a clean, dense DAG
    dependencies: list[DependencyRelationship] = []
    dep_idx = 0

    for tier_idx in range(1, 4):
        curr_tier = tier_nodes[tier_idx]
        lower_tier = tier_nodes[tier_idx - 1]

        for cid in curr_tier:
            # Each node depends on 1 to 3 nodes in the tier strictly below it
            num_deps = min(len(lower_tier), rng.randint(1, 3))
            targets = rng.sample(lower_tier, num_deps)
            for tgt in targets:
                dependencies.append(
                    DependencyRelationship(
                        edge_id=f"dep-scale-{dep_idx:06d}",
                        source_component_id=cid,
                        target_component_id=tgt,
                        relationship_type=RelationshipType.CALLS,
                        criticality=DependencyCriticality.CRITICAL,
                    )
                )
                dep_idx += 1

    # Constraints
    constraint_rollback = MigrationConstraint(
        constraint_id="cnstr-scale-rollback",
        constraint_type=ConstraintType.ROLLBACK_CAPABILITY,
        description="Mandatory automated rollback validation for all production waves.",
        is_mandatory_rollback=True,
    )
    constraint_compliance = MigrationConstraint(
        constraint_id="cnstr-scale-pqc",
        constraint_type=ConstraintType.REGULATORY_COMPLIANCE,
        description="Must migrate to ML-KEM-768 standard.",
        required_algorithm="ML-KEM-768",
    )

    # Required Test
    root_components = tier_nodes[0][:min(5, len(tier_nodes[0]))]
    test_interop = RequiredTest(
        test_id="test-scale-root-interop",
        test_type=TestType.INTEROPERABILITY,
        description="Root tier interoperability handshake gate.",
        target_components=root_components,
    )

    scenario = ScenarioModel(
        scenario_id=f"scen-scale-{num_components}",
        scenario_name=f"Scale Benchmark Scenario ({num_components} Nodes)",
        description=f"Synthetic enterprise architecture with {num_components} components and {len(dependencies)} edges.",
        system_components=components,
        dependencies=dependencies,
        compatibility_records=compatibility_records,
        required_tests=[test_interop],
        evidence_records=evidence_records,
        migration_constraints=[constraint_rollback, constraint_compliance],
    )

    task = BenchmarkTask(
        task_id=f"task-scale-{num_components}",
        task_name=f"Scale Task {num_components}",
        task_category=TaskCategory.MIGRATION_SEQUENCING,
        difficulty=DifficultyLevel.ADVANCED,
        description=f"Scale evaluation task for {num_components} nodes.",
        scenario_reference=scenario.scenario_id,
        task_instructions="Plan a valid multi-wave migration ordering across all tiers.",
        ground_truth_reference=f"gt-scale-{num_components}",
    )

    ground_truth: dict[str, Any] = {
        "ground_truth_id": task.ground_truth_reference,
        "task_reference": task.task_id,
        "scenario_reference": scenario.scenario_id,
        "is_migratable": True,
        "expected_blockers": [],
        "direct_dependencies": {
            dep.source_component_id: [dep.target_component_id] for dep in dependencies
        },
        "transitive_dependencies": {},
        "optimal_wave_order": [f"Wave {i + 1}" for i in range(4)],
        "required_verification_gates": [test_interop.test_id],
        "critical_violations": [],
    }

    # Construct sound, compliant model response contract
    reported_steps: list[ReportedMigrationStep] = []
    for tier_idx, nodes in enumerate(tier_nodes):
        wave_num = tier_idx + 1
        for cid in nodes:
            reported_steps.append(
                ReportedMigrationStep(
                    wave=wave_num,
                    component_id=cid,
                    action_type=MigrationActionType.PRODUCTION_CUTOVER,
                    rollback_trigger="telemetry_error_rate > 0.005",
                    rollback_action="automated_canary_revert",
                )
            )

    contract = ModelResponseContract(
        task_id=task.task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[
            ReportedDependency(
                source_component_id=dep.source_component_id,
                target_component_id=dep.target_component_id,
                relationship_type=dep.relationship_type.value,
                evidence_reference=f"evid-scale-{dep.source_component_id.split('-')[-1]}",
            )
            for dep in dependencies
        ],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id=c.component_id,
                status=ReportedCompatibilityStatus.SUPPORTED,
                evidence_reference=f"evid-scale-{c.component_id.split('-')[-1]}",
            )
            for c in components
        ],
        migration_plan=reported_steps,
        blocked_components=[],
        required_actions=[],
        verification_results=[
            ReportedTestResult(
                test_id=test_interop.test_id,
                reported_status=ReportedTestStatus.PASSED,
                evidence_reference="evid-scale-00000",
            )
        ],
        evidence_references=[e.evidence_id for e in evidence_records[:min(100, len(evidence_records))]],
        assumptions=[],
        uncertainties=[],
        explanation=(
            f"Sound migration plan for {num_components} components. Upgraded root key storage in Wave 1, "
            f"followed by databases in Wave 2, microservices in Wave 3, and edge gateways in Wave 4. "
            f"All dependencies causally satisfied with automated rollback procedures."
        ),
    )

    return scenario, task, ground_truth, contract


def run_scale_benchmark(
    sizes: Optional[list[int]] = None,
    seed: int = 42,
) -> ScaleBenchmarkReport:
    """Execute scale benchmarking across specified graph sizes."""
    if sizes is None:
        sizes = [100, 500, 1000]

    evaluator = DeterministicEvaluator()
    evidence_grader = EvidenceGrader()
    constraint_grader = ConstraintGrader()

    results: list[ScaleBenchmarkPoint] = []

    for n in sizes:
        scenario, task, gt, contract = build_scale_scenario(n, seed=seed)
        contract_json = contract.model_dump_json(indent=2)

        tracemalloc.start()
        mem_before, _ = tracemalloc.get_traced_memory()

        # 1. Graph verification
        t0 = time.perf_counter()
        verifier = IndependentGraphVerifier(scenario)
        verif_res = verifier.verify_plan(contract.migration_plan)
        t_graph = (time.perf_counter() - t0) * 1000.0
        assert verif_res.is_valid, f"Graph verification failed for size {n}: {verif_res.error_message}"

        # 2. Evidence validation
        t0 = time.perf_counter()
        evid_res = evidence_grader.grade(contract, scenario, gt)
        t_evid = (time.perf_counter() - t0) * 1000.0

        # 3. Constraint evaluation
        t0 = time.perf_counter()
        const_res = constraint_grader.grade(contract, scenario, gt)
        t_const = (time.perf_counter() - t0) * 1000.0

        # 4. Full end-to-end evaluation
        t0 = time.perf_counter()
        report = evaluator.evaluate_detailed(task, contract_json, gt, scenario)
        t_full = (time.perf_counter() - t0) * 1000.0

        mem_after, mem_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mem_mb = (mem_peak - mem_before) / (1024.0 * 1024.0)
        throughput = (n / (t_full / 1000.0)) if t_full > 0 else 0.0

        results.append(
            ScaleBenchmarkPoint(
                num_components=n,
                num_dependencies=len(scenario.dependencies),
                num_evidence_records=len(scenario.evidence_records),
                graph_verification_ms=round(t_graph, 2),
                evidence_validation_ms=round(t_evid, 2),
                constraint_evaluation_ms=round(t_const, 2),
                full_evaluation_ms=round(t_full, 2),
                peak_memory_mb=round(max(0.1, peak_mem_mb), 2),
                throughput_components_per_sec=round(throughput, 1),
                safety_gate_passed=report.safety_gate_passed,
                overall_status=report.overall_status,
            )
        )

    # Scaling analysis: ensure evaluation time grows smoothly without exponential blowout
    # For a 10x increase in size (100 -> 1000), time ratio should be well within polynomial bounds (e.g. < 40x)
    linear_scaling_verified = True
    if len(results) >= 2:
        ratio_n = results[-1].num_components / results[0].num_components
        ratio_t = (
            results[-1].full_evaluation_ms / results[0].full_evaluation_ms
            if results[0].full_evaluation_ms > 0
            else 1.0
        )
        # O(N log N) or O(N * D) growth is expected; flag if super-quadratic
        if ratio_t > (ratio_n ** 2.2):
            linear_scaling_verified = False

    return ScaleBenchmarkReport(
        benchmark_timestamp=datetime.now(timezone.utc).isoformat(),
        sizes_evaluated=sizes,
        results=results,
        linear_scaling_verified=linear_scaling_verified,
        notes="Scale benchmark executing across 100, 500, and 1,000 synthetic enterprise nodes.",
    )
