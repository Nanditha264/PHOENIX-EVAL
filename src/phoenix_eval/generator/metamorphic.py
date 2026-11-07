"""Metamorphic testing engine validating mathematical and architectural benchmark invariants."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from phoenix_eval.generator.config import ArchitectureDomain, GraphComplexity, TaskFamily
from phoenix_eval.generator.constraints import analyze_architecture_graph
from phoenix_eval.generator.ground_truth_generator import generate_ground_truth
from phoenix_eval.generator.scenario_generator import generate_scenario_for_task_family
from phoenix_eval.generator.seed_manager import SeedManager
from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.schemas.compatibility import CompatibilityRecord, CompatibilityStatus
from phoenix_eval.schemas.dependencies import (
    DependencyCriticality,
    DependencyRelationship,
    RelationshipType,
)
from phoenix_eval.schemas.evidence import (
    EvidenceCategory,
    EvidenceRecord,
    EvidenceType,
    VerificationStatus,
)
from phoenix_eval.schemas.scenarios import RequiredTest, ScenarioModel, TestType


class MetamorphicRelationType(StrEnum):
    """The six core metamorphic relations evaluated in PHOENIX-EVAL."""

    MR1_STATUS_UNSUPPORTED = (
        "MR1_STATUS_UNSUPPORTED"  # SUPPORTED -> UNSUPPORTED on dependency => becomes blocker
    )
    MR2_STATUS_UNKNOWN = (
        "MR2_STATUS_UNKNOWN"  # SUPPORTED -> UNKNOWN => must not treat as verified safe
    )
    MR3_INTEROP_TEST_FAIL = (
        "MR3_INTEROP_TEST_FAIL"  # Test PASS -> FAIL => production promotion blocked
    )
    MR4_ADD_CYCLE = "MR4_ADD_CYCLE"  # Add back-edge => DAG invalid, cycle detected
    MR5_UNUSED_CRYPTO_REF = (
        "MR5_UNUSED_CRYPTO_REF"  # Add commented reference => active inventory unchanged
    )
    MR6_REMOVE_VALIDATION = (
        "MR6_REMOVE_VALIDATION"  # Remove validation test => verification cannot complete
    )


@dataclass(frozen=True)
class MetamorphicTestResult:
    """Outcome of evaluating a metamorphic invariant transformation."""

    relation_type: MetamorphicRelationType
    test_id: str
    description: str
    passed: bool
    baseline_value: Any
    transformed_value: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Export result as structured dictionary."""
        return {
            "test_id": self.test_id,
            "relation_type": self.relation_type.value,
            "description": self.description,
            "passed": self.passed,
            "baseline_value": str(self.baseline_value),
            "transformed_value": str(self.transformed_value),
            "message": self.message,
        }


def run_metamorphic_test(
    relation_type: MetamorphicRelationType,
    test_id: str,
    seed_mgr: SeedManager,
    domain: ArchitectureDomain = ArchitectureDomain.BANKING_PAYMENTS,
) -> MetamorphicTestResult:
    """Execute a single metamorphic transformation and assert that the expected relation holds."""
    # Base scenario: Clean, valid migration
    base_scen = generate_scenario_for_task_family(
        scenario_id=f"scen-meta-{test_id}-base",
        task_family=TaskFamily.T09_VALID_MIGRATION,
        domain=domain,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )
    base_gt = generate_ground_truth(
        "task-meta-base", base_scen, TaskFamily.T09_VALID_MIGRATION, "gt-meta-base"
    )

    if relation_type == MetamorphicRelationType.MR1_STATUS_UNSUPPORTED:
        # Transformation: Change one component with dependents from SUPPORTED to UNSUPPORTED
        # Invariant: The component MUST appear in expected_blockers of ground truth
        comp_to_modify = base_scen.system_components[-1].component_id
        new_records = []
        for r in base_scen.compatibility_records:
            if r.component_id == comp_to_modify:
                new_records.append(
                    CompatibilityRecord(
                        component_id=comp_to_modify,
                        proposed_target=r.proposed_target,
                        status=CompatibilityStatus.UNSUPPORTED,
                        evidence_references=r.evidence_references,
                        reason="Metamorphic mutation: downgraded to UNSUPPORTED.",
                        assessment_source="mutation-engine",
                    )
                )
            else:
                new_records.append(r)

        mutated_scen = ScenarioModel(
            scenario_id=f"scen-meta-{test_id}-mut",
            scenario_name=base_scen.scenario_name,
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=base_scen.dependencies,
            compatibility_records=new_records,
            evidence_records=base_scen.evidence_records,
            migration_constraints=base_scen.migration_constraints,
            required_tests=base_scen.required_tests,
            metadata=base_scen.metadata,
        )
        mut_gt = generate_ground_truth(
            "task-meta-mut", mutated_scen, TaskFamily.T03_INCOMPATIBLE_CONSUMER, "gt-meta-mut"
        )
        passed = comp_to_modify in mut_gt["expected_blockers"]
        return MetamorphicTestResult(
            relation_type=relation_type,
            test_id=test_id,
            description="Downgrading component to UNSUPPORTED must cause it to be identified as a migration blocker.",
            passed=passed,
            baseline_value=base_gt["expected_blockers"],
            transformed_value=mut_gt["expected_blockers"],
            message=f"Component {comp_to_modify} successfully flagged in blockers: {passed}.",
        )

    if relation_type == MetamorphicRelationType.MR2_STATUS_UNKNOWN:
        # Transformation: Change component from SUPPORTED to UNKNOWN
        # Invariant: is_migratable must become False
        comp_to_modify = base_scen.system_components[-1].component_id
        new_records = []
        for r in base_scen.compatibility_records:
            if r.component_id == comp_to_modify:
                new_records.append(
                    CompatibilityRecord(
                        component_id=comp_to_modify,
                        proposed_target=r.proposed_target,
                        status=CompatibilityStatus.UNKNOWN,
                        evidence_references=r.evidence_references,
                        reason="Metamorphic mutation: status changed to UNKNOWN.",
                        assessment_source="mutation-engine",
                    )
                )
            else:
                new_records.append(r)

        mutated_scen = ScenarioModel(
            scenario_id=f"scen-meta-{test_id}-mut",
            scenario_name=base_scen.scenario_name,
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=base_scen.dependencies,
            compatibility_records=new_records,
            evidence_records=base_scen.evidence_records,
            migration_constraints=base_scen.migration_constraints,
            required_tests=base_scen.required_tests,
            metadata=base_scen.metadata,
        )
        mut_gt = generate_ground_truth(
            "task-meta-mut", mutated_scen, TaskFamily.T04_UNKNOWN_PROVIDER, "gt-meta-mut"
        )
        passed = mut_gt["is_migratable"] is False
        return MetamorphicTestResult(
            relation_type=relation_type,
            test_id=test_id,
            description="Changing component to UNKNOWN must cause overall migration to be unverified/non-migratable.",
            passed=passed,
            baseline_value=base_gt["is_migratable"],
            transformed_value=mut_gt["is_migratable"],
            message=f"Migration readiness correctly revoked upon UNKNOWN status: {passed}.",
        )

    if relation_type == MetamorphicRelationType.MR3_INTEROP_TEST_FAIL:
        # Transformation: Add a failed interoperability test
        # Invariant: critical_violations or is_migratable flags blocked gate
        failing_test = RequiredTest(
            test_id="test-meta-failing-interop",
            test_type=TestType.INTEROPERABILITY,
            description="STATUS: FAILED (Cipher handshake dropped).",
            target_components=[base_scen.system_components[0].component_id],
        )
        mutated_scen = ScenarioModel(
            scenario_id=f"scen-meta-{test_id}-mut",
            scenario_name=base_scen.scenario_name,
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=base_scen.dependencies,
            compatibility_records=base_scen.compatibility_records,
            evidence_records=base_scen.evidence_records,
            migration_constraints=base_scen.migration_constraints,
            required_tests=[*base_scen.required_tests, failing_test],
            metadata=base_scen.metadata,
        )
        mut_gt = generate_ground_truth(
            "task-meta-mut", mutated_scen, TaskFamily.T08_FAILED_INTEROP, "gt-meta-mut"
        )
        passed = "test-meta-failing-interop" in mut_gt["required_verification_gates"]
        return MetamorphicTestResult(
            relation_type=relation_type,
            test_id=test_id,
            description="Adding a failing interoperability test must require explicit verification gate resolution.",
            passed=passed,
            baseline_value=len(base_scen.required_tests),
            transformed_value=len(mutated_scen.required_tests),
            message=f"Failing test recorded in required verification gates: {passed}.",
        )

    if relation_type == MetamorphicRelationType.MR4_ADD_CYCLE:
        # Transformation: Add back-edge creating cycle
        # Invariant: cycle_detected must be True, optimal_wave_order must be empty
        edge_back = DependencyRelationship(
            edge_id="edge-meta-cycle-back",
            source_component_id=base_scen.dependencies[0].target_component_id,
            target_component_id=base_scen.dependencies[0].source_component_id,
            relationship_type=RelationshipType.CALLS,
            criticality=DependencyCriticality.CRITICAL,
            description="Circular back-edge.",
        )
        mutated_scen = ScenarioModel(
            scenario_id=f"scen-meta-{test_id}-mut",
            scenario_name=base_scen.scenario_name,
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=[*base_scen.dependencies, edge_back],
            compatibility_records=base_scen.compatibility_records,
            evidence_records=base_scen.evidence_records,
            migration_constraints=base_scen.migration_constraints,
            required_tests=base_scen.required_tests,
            metadata=base_scen.metadata,
        )
        mut_gt = generate_ground_truth(
            "task-meta-mut", mutated_scen, TaskFamily.T06_DEPENDENCY_CYCLE, "gt-meta-mut"
        )
        passed = (mut_gt["cycle_detected"] is True) and (len(mut_gt["optimal_wave_order"]) == 0)
        return MetamorphicTestResult(
            relation_type=relation_type,
            test_id=test_id,
            description="Adding a circular dependency must invalidate the DAG and prevent linear wave ordering.",
            passed=passed,
            baseline_value=base_gt["cycle_detected"],
            transformed_value=mut_gt["cycle_detected"],
            message=f"Circular deadlock successfully detected and wave ordering prevented: {passed}.",
        )

    if relation_type == MetamorphicRelationType.MR5_UNUSED_CRYPTO_REF:
        # Transformation: Add commented-out crypto reference in evidence
        # Invariant: The actual dependency graph topology and nodes remain unchanged
        ev_comment = EvidenceRecord(
            evidence_id="evid-meta-comment",
            evidence_type=EvidenceType.STATIC_CODE_ANALYSIS,
            source="src/main/resources/application.properties.bak",
            description="# TODO: support ML-KEM-1024 in future",
            observed_value="# unused comment",
            confidence=0.1,
            timestamp=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            provenance="git:repo-review/commit-1103",
            evidence_category=EvidenceCategory.ASSUMPTION,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        mutated_scen = ScenarioModel(
            scenario_id=f"scen-meta-{test_id}-mut",
            scenario_name=base_scen.scenario_name,
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=base_scen.dependencies,
            compatibility_records=base_scen.compatibility_records,
            evidence_records=[*base_scen.evidence_records, ev_comment],
            migration_constraints=base_scen.migration_constraints,
            required_tests=base_scen.required_tests,
            metadata=base_scen.metadata,
        )
        mut_analysis = analyze_architecture_graph(mutated_scen)
        base_analysis = analyze_architecture_graph(base_scen)
        passed = (
            mut_analysis.graph.number_of_nodes() == base_analysis.graph.number_of_nodes()
        ) and (mut_analysis.graph.number_of_edges() == base_analysis.graph.number_of_edges())
        return MetamorphicTestResult(
            relation_type=relation_type,
            test_id=test_id,
            description="Superficial commented-out crypto references must not alter active dependency graph topology.",
            passed=passed,
            baseline_value=base_analysis.graph.number_of_edges(),
            transformed_value=mut_analysis.graph.number_of_edges(),
            message=f"Active dependency topology strictly unaffected by superficial comments: {passed}.",
        )

    # MetamorphicRelationType.MR6_REMOVE_VALIDATION
    mutated_scen = ScenarioModel(
        scenario_id=f"scen-meta-{test_id}-mut",
        scenario_name=base_scen.scenario_name,
        description=base_scen.description,
        system_components=base_scen.system_components,
        dependencies=base_scen.dependencies,
        compatibility_records=base_scen.compatibility_records,
        evidence_records=base_scen.evidence_records,
        migration_constraints=base_scen.migration_constraints,
        required_tests=[],  # Stripped tests
        metadata=base_scen.metadata,
    )
    mut_gt = generate_ground_truth(
        "task-meta-mut", mutated_scen, TaskFamily.T07_MISSING_VALIDATION, "gt-meta-mut"
    )
    passed = len(mut_gt["required_verification_gates"]) == 0
    return MetamorphicTestResult(
        relation_type=relation_type,
        test_id=test_id,
        description="Removing validation evidence must result in zero satisfied verification gates.",
        passed=passed,
        baseline_value=len(base_gt["required_verification_gates"]),
        transformed_value=len(mut_gt["required_verification_gates"]),
        message=f"Missing validation gates reflected in ground truth: {passed}.",
    )
