"""Scenario generator orchestrating components, dependencies, evidence, compatibility, and tests."""

from datetime import datetime, timezone
from typing import Optional

from phoenix_eval.generator.compatibility_generator import generate_compatibility_record
from phoenix_eval.generator.component_generator import generate_components_for_domain
from phoenix_eval.generator.config import ArchitectureDomain, GraphComplexity, TaskFamily
from phoenix_eval.generator.dependency_generator import generate_dependencies
from phoenix_eval.generator.evidence_generator import generate_evidence_for_component
from phoenix_eval.generator.seed_manager import SeedManager
from phoenix_eval.schemas.common import MetadataModel
from phoenix_eval.schemas.compatibility import CompatibilityRecord, CompatibilityStatus
from phoenix_eval.schemas.components import CryptographicComponent
from phoenix_eval.schemas.dependencies import DependencyRelationship
from phoenix_eval.schemas.evidence import EvidenceRecord
from phoenix_eval.schemas.scenarios import (
    ConstraintType,
    MigrationConstraint,
    RequiredTest,
    ScenarioModel,
    TestType,
)

DETERMINISTIC_TIMESTAMP = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _get_component_count(complexity: GraphComplexity, seed_mgr: SeedManager) -> int:
    """Determine component count based on complexity tier."""
    if complexity == GraphComplexity.SMALL:
        return seed_mgr.randint(5, 7)
    if complexity == GraphComplexity.LARGE:
        return seed_mgr.randint(15, 20)
    # Default MEDIUM
    return seed_mgr.randint(8, 12)


def _generate_migration_constraints(
    scenario_id: str,
    task_family: TaskFamily,
    domain: ArchitectureDomain,
    components: list[CryptographicComponent],
    dependencies: list[DependencyRelationship],
    required_tests: list[RequiredTest],
    evidence_records: list[EvidenceRecord],
    seed_mgr: SeedManager,
) -> list[MigrationConstraint]:
    """Deterministically synthesize structured migration constraints across all six constraint types."""
    comp_ids = [c.component_id for c in components]
    test_ids = [t.test_id for t in required_tests]
    evid_ids = [e.evidence_id for e in evidence_records]
    suffix = scenario_id[-6:]

    # Extract variant (1, 2, or 3)
    variant = 1
    if "-02" in scenario_id or scenario_id.endswith("-02"):
        variant = 2
    elif "-03" in scenario_id or scenario_id.endswith("-03"):
        variant = 3
    elif "-b" in scenario_id:
        variant = 2

    def make_ordering(evaluable: bool) -> MigrationConstraint:
        if evaluable:
            return MigrationConstraint(
                constraint_id=f"cnstr-order-{suffix}",
                constraint_type=ConstraintType.ORDERING,
                description="Mandatory causal prerequisite ordering: foundational cryptographic providers and sinks must cutover prior to dependents.",
                affected_components=comp_ids[:4] if len(comp_ids) >= 4 else comp_ids,
            )
        return MigrationConstraint(
            constraint_id=f"cnstr-order-unspec-{suffix}",
            constraint_type=ConstraintType.ORDERING,
            description="Causal wave ordering expected for standalone components without recorded dependencies.",
            affected_components=[],
        )

    def make_no_downtime(evaluable: bool) -> MigrationConstraint:
        if evaluable:
            return MigrationConstraint(
                constraint_id=f"cnstr-no-downtime-{suffix}",
                constraint_type=ConstraintType.NO_DOWNTIME,
                description="High-availability zero-downtime requirement: continuous caller-callee availability must be maintained throughout all transitional waves.",
                affected_components=comp_ids[:3] if len(comp_ids) >= 3 else comp_ids,
                requires_dual_stack=True,
                required_interop_tests=test_ids[:1],
                service_availability_sla="99.99% availability during wave cutovers",
                staged_transition_required=True,
            )
        return MigrationConstraint(
            constraint_id=f"cnstr-downtime-unspec-{suffix}",
            constraint_type=ConstraintType.NO_DOWNTIME,
            description="General goal of high availability during migration; detailed SLA and interop specifications omitted.",
            affected_components=comp_ids[:2] if len(comp_ids) >= 2 else comp_ids,
            requires_dual_stack=False,
            required_interop_tests=[],
            service_availability_sla=None,
            staged_transition_required=False,
        )

    def make_backward_compat(evaluable: bool) -> MigrationConstraint:
        if evaluable:
            return MigrationConstraint(
                constraint_id=f"cnstr-backward-compat-{suffix}",
                constraint_type=ConstraintType.BACKWARD_COMPATIBILITY,
                description="Mandatory dual-stack backward compatibility: classical RSA/ECC fallbacks must coexist with PQC algorithms during all transitional phases.",
                affected_components=[comp_ids[0]] if comp_ids else [],
                coexisting_algorithms=["RSA-4096", "ML-KEM-768"],
                preserved_relationships=["CONSUMER_CALLS_PRODUCER"],
                required_compatibility_gate=test_ids[0] if test_ids else None,
            )
        return MigrationConstraint(
            constraint_id=f"cnstr-compat-unspec-{suffix}",
            constraint_type=ConstraintType.BACKWARD_COMPATIBILITY,
            description="Backward compatibility should be maintained where appropriate; specific coexistence pairs not defined.",
            affected_components=[comp_ids[0]] if comp_ids else [],
            coexisting_algorithms=[],
            preserved_relationships=[],
            required_compatibility_gate=None,
        )

    def make_hardware_limit(evaluable: bool) -> MigrationConstraint:
        if evaluable:
            fw_prereqs = {}
            if task_family != TaskFamily.T09_VALID_MIGRATION and comp_ids:
                fw_prereqs = {comp_ids[0]: "FW-v4.2+"}

            return MigrationConstraint(
                constraint_id=f"cnstr-hw-limit-{suffix}",
                constraint_type=ConstraintType.HARDWARE_LIMIT,
                description="Hardware security module and accelerator capacity bounds: limit concurrent cutovers and verify cryptographic coprocessor firmware.",
                affected_components=comp_ids[:3] if len(comp_ids) >= 3 else comp_ids,
                max_concurrent_migrations=3,
                firmware_prerequisites=fw_prereqs,
                required_accelerator="QAT-Gen4",
                component_capacity_limits={comp_ids[0]: 2} if comp_ids else {},
            )
        return MigrationConstraint(
            constraint_id=f"cnstr-hw-unspec-{suffix}",
            constraint_type=ConstraintType.HARDWARE_LIMIT,
            description="Adhere to hardware platform constraints and environmental capacity guidelines.",
            affected_components=comp_ids[:2] if len(comp_ids) >= 2 else comp_ids,
            max_concurrent_migrations=None,
            firmware_prerequisites={},
            required_accelerator=None,
            component_capacity_limits={},
        )

    def make_regulatory(evaluable: bool) -> MigrationConstraint:
        if evaluable:
            return MigrationConstraint(
                constraint_id=f"cnstr-regulatory-{suffix}",
                constraint_type=ConstraintType.REGULATORY_COMPLIANCE,
                description="Regulatory compliance mandate: migration plan and target algorithms must satisfy NIST SP 800-208 / FIPS 203 standards.",
                affected_components=comp_ids[:3] if len(comp_ids) >= 3 else comp_ids,
                policy_id="NIST-SP-800-208",
                required_algorithm="ML-KEM-768",
                required_evidence_ids=evid_ids[:2],
                required_test_ids=test_ids[:1],
            )
        return MigrationConstraint(
            constraint_id=f"cnstr-reg-unspec-{suffix}",
            constraint_type=ConstraintType.REGULATORY_COMPLIANCE,
            description="Compliance with relevant organizational standards required, but no specific policy ID or mandated algorithms are designated.",
            affected_components=comp_ids[:2] if len(comp_ids) >= 2 else comp_ids,
            policy_id="",
            required_algorithm="",
            required_evidence_ids=[],
            required_test_ids=[],
        )

    def make_rollback(evaluable: bool) -> MigrationConstraint:
        if evaluable:
            return MigrationConstraint(
                constraint_id=f"cnstr-rollback-{suffix}",
                constraint_type=ConstraintType.ROLLBACK_CAPABILITY,
                description="Mandatory rollback and contingency procedures: all migration steps must specify triggers, automated recovery, and post-rollback health checks.",
                affected_components=comp_ids[:3] if len(comp_ids) >= 3 else comp_ids,
                is_mandatory_rollback=True,
                required_recovery_mechanism="AUTOMATED_FALLBACK",
                post_rollback_validation_gate=test_ids[0] if test_ids else None,
            )
        return MigrationConstraint(
            constraint_id=f"cnstr-rollback-unspec-{suffix}",
            constraint_type=ConstraintType.ROLLBACK_CAPABILITY,
            description="Rollback procedures should be considered if migration encounters unexpected instability.",
            affected_components=comp_ids[:2] if len(comp_ids) >= 2 else comp_ids,
            is_mandatory_rollback=False,
            required_recovery_mechanism=None,
            post_rollback_validation_gate=None,
        )

    tf = task_family
    if tf == TaskFamily.T01_HIDDEN_DEPENDENCY:
        if variant == 1:
            return [make_ordering(True), make_backward_compat(True)]
        if variant == 2:
            return [make_ordering(True), make_no_downtime(True), make_rollback(True)]
        return [make_no_downtime(True), make_backward_compat(True), make_hardware_limit(False)]

    if tf == TaskFamily.T02_FALSE_DISCOVERY:
        if variant == 1:
            return [make_no_downtime(False), make_regulatory(True)]
        if variant == 2:
            return [make_hardware_limit(True), make_regulatory(True)]
        return [make_ordering(False), make_rollback(True)]

    if tf == TaskFamily.T03_INCOMPATIBLE_CONSUMER:
        if variant == 1:
            return [make_no_downtime(True), make_regulatory(True)]
        if variant == 2:
            return [make_no_downtime(True), make_backward_compat(True), make_rollback(True)]
        return [make_backward_compat(True), make_hardware_limit(False)]

    if tf == TaskFamily.T04_UNKNOWN_PROVIDER:
        if variant == 1:
            return [make_backward_compat(True), make_hardware_limit(True), make_rollback(True)]
        if variant == 2:
            return [make_backward_compat(True), make_regulatory(True)]
        return [make_ordering(False), make_hardware_limit(True), make_rollback(False)]

    if tf == TaskFamily.T05_MIGRATION_ORDERING:
        if variant == 1:
            return [make_ordering(True), make_no_downtime(True), make_rollback(True)]
        if variant == 2:
            return [make_ordering(True), make_no_downtime(True), make_regulatory(True)]
        return [make_ordering(True), make_backward_compat(False), make_rollback(True)]

    if tf == TaskFamily.T06_DEPENDENCY_CYCLE:
        if variant == 1:
            return [make_ordering(True), make_hardware_limit(True)]
        if variant == 2:
            return [make_ordering(True), make_regulatory(False)]
        return [make_ordering(True), make_rollback(True)]

    if tf == TaskFamily.T07_MISSING_VALIDATION:
        if variant == 1:
            return [make_backward_compat(True), make_regulatory(True)]
        if variant == 2:
            return [make_backward_compat(True), make_hardware_limit(True), make_rollback(True)]
        return [make_no_downtime(False), make_hardware_limit(True)]

    if tf == TaskFamily.T08_FAILED_INTEROP:
        if variant == 1:
            return [make_no_downtime(True), make_hardware_limit(True), make_rollback(True)]
        if variant == 2:
            return [make_no_downtime(True), make_regulatory(True)]
        return [make_backward_compat(False), make_rollback(True)]

    if tf == TaskFamily.T09_VALID_MIGRATION:
        if variant == 1:
            return [
                make_ordering(True),
                make_no_downtime(True),
                make_hardware_limit(True),
                make_rollback(False),
            ]
        if variant == 2:
            return [make_ordering(True), make_backward_compat(True), make_hardware_limit(True)]
        return [make_no_downtime(True), make_regulatory(True), make_rollback(True)]

    if tf == TaskFamily.T10_CONDITIONAL_PLAN:
        if variant == 1:
            return [make_ordering(False), make_hardware_limit(True), make_regulatory(False)]
        if variant == 2:
            return [make_no_downtime(True), make_hardware_limit(True), make_regulatory(True)]
        return [make_backward_compat(True), make_regulatory(True)]

    return [make_ordering(True), make_no_downtime(True), make_backward_compat(True)]


def generate_scenario_for_task_family(
    scenario_id: str,
    task_family: TaskFamily,
    domain: ArchitectureDomain,
    seed_mgr: SeedManager,
    complexity: GraphComplexity = GraphComplexity.MEDIUM,
    custom_org: Optional[str] = None,
) -> ScenarioModel:
    """Generate a cohesive ScenarioModel tailored to a specific benchmark task family."""
    comp_count = _get_component_count(complexity, seed_mgr)
    raw_components = generate_components_for_domain(
        domain, seed_mgr, count=comp_count, custom_org=custom_org
    )

    # Tailor topology and facts based on TaskFamily
    create_cycle = task_family == TaskFamily.T06_DEPENDENCY_CYCLE
    hidden_target = (
        raw_components[-1].component_id if task_family == TaskFamily.T01_HIDDEN_DEPENDENCY else None
    )

    dependencies = generate_dependencies(
        components=raw_components,
        seed_mgr=seed_mgr,
        create_cycle=create_cycle,
        hidden_dependency_target=hidden_target,
    )

    evidence_records: list[EvidenceRecord] = []
    compatibility_records: list[CompatibilityRecord] = []
    system_components: list[CryptographicComponent] = []

    # Assign compatibility and generate evidence per component
    for idx, comp in enumerate(raw_components):
        # Determine compatibility status based on task family requirements
        if task_family == TaskFamily.T09_VALID_MIGRATION:
            # Control: All components supported
            status = CompatibilityStatus.SUPPORTED
            is_false = False
            is_unknown = False
            inject_contra = False
        elif task_family == TaskFamily.T02_FALSE_DISCOVERY and idx == 0:
            # First component has false discovery comment in config
            status = CompatibilityStatus.UNSUPPORTED
            is_false = True
            is_unknown = False
            inject_contra = False
        elif task_family == TaskFamily.T03_INCOMPATIBLE_CONSUMER and idx == len(raw_components) - 1:
            # Consumer at sink is unsupported
            status = CompatibilityStatus.UNSUPPORTED
            is_false = False
            is_unknown = False
            inject_contra = False
        elif task_family == TaskFamily.T04_UNKNOWN_PROVIDER and idx == len(raw_components) - 1:
            # External provider is unknown
            status = CompatibilityStatus.UNKNOWN
            is_false = False
            is_unknown = True
            inject_contra = False
        elif task_family == TaskFamily.T10_CONDITIONAL_PLAN and idx == 0:
            # Client fleet at tier 0 has unknown compatibility
            status = CompatibilityStatus.UNKNOWN
            is_false = False
            is_unknown = True
            inject_contra = False
        elif task_family in (
            TaskFamily.T01_HIDDEN_DEPENDENCY,
            TaskFamily.T07_MISSING_VALIDATION,
            TaskFamily.T08_FAILED_INTEROP,
        ):
            # Mix of supported with one downstream blocker/hsm
            if comp.metadata.get("tier", 1) == 3 and idx % 2 == 1:
                status = CompatibilityStatus.UNSUPPORTED
            else:
                status = CompatibilityStatus.SUPPORTED
            is_false = False
            is_unknown = False
            inject_contra = False
        else:
            # General distribution
            status = CompatibilityStatus.SUPPORTED if idx != 2 else CompatibilityStatus.UNSUPPORTED
            is_false = False
            is_unknown = False
            inject_contra = False

        comp_evidence = generate_evidence_for_component(
            comp=comp,
            seed_mgr=seed_mgr,
            is_supported=(status == CompatibilityStatus.SUPPORTED),
            is_unknown=is_unknown,
            inject_contradiction=inject_contra,
            is_false_discovery=is_false,
        )
        evidence_records.extend(comp_evidence)

        compat_rec = generate_compatibility_record(
            comp=comp,
            evidence_records=comp_evidence,
            status=status,
        )
        compatibility_records.append(compat_rec)

        # Update component with evidence references
        updated_comp = CryptographicComponent(
            component_id=comp.component_id,
            component_name=comp.component_name,
            component_type=comp.component_type,
            cryptographic_role=comp.cryptographic_role,
            description=comp.description,
            technology=comp.technology,
            current_algorithms=comp.current_algorithms,
            evidence_references=[e.evidence_id for e in comp_evidence],
            metadata=comp.metadata,
        )
        system_components.append(updated_comp)

    # Attach evidence references to dependency edges where applicable
    updated_dependencies: list[DependencyRelationship] = []
    for dep in dependencies:
        edge_evid = [
            e.evidence_id for e in evidence_records if dep.source_component_id in e.evidence_id
        ]
        if not edge_evid and evidence_records:
            edge_evid = [evidence_records[0].evidence_id]

        updated_dependencies.append(
            DependencyRelationship(
                edge_id=dep.edge_id,
                source_component_id=dep.source_component_id,
                target_component_id=dep.target_component_id,
                relationship_type=dep.relationship_type,
                confidence=dep.confidence,
                criticality=dep.criticality,
                description=dep.description,
                evidence_references=edge_evid[:2],
            )
        )

    # Required verification tests
    required_tests: list[RequiredTest] = []
    if task_family != TaskFamily.T07_MISSING_VALIDATION:
        # T07 intentionally omits or has missing validation evidence
        t1 = RequiredTest(
            test_id=f"test-staging-handshake-{scenario_id[-6:]}",
            test_type=TestType.INTEROPERABILITY,
            description="Staging mTLS handshake verification with hybrid ML-KEM key encapsulation.",
            target_components=[system_components[0].component_id],
        )
        t2 = RequiredTest(
            test_id=f"test-fallback-recovery-{scenario_id[-6:]}",
            test_type=TestType.FALLBACK_VERIFICATION,
            description="Automated cipher downgrade fallback verification to classical algorithms under simulated network drop.",
            target_components=[system_components[0].component_id],
        )
        required_tests.extend([t1, t2])

        if task_family == TaskFamily.T08_FAILED_INTEROP:
            # T08: Add an explicitly failing interoperability test
            t_fail = RequiredTest(
                test_id=f"test-downstream-interop-{scenario_id[-6:]}",
                test_type=TestType.REGRESSION,
                description="Downstream client interoperability test. STATUS: FAILED (ClientHello payload fragmentation error).",
                target_components=[c.component_id for c in system_components[-2:]],
            )
            required_tests.append(t_fail)

    # Migration constraints (balanced across all 6 constraint types with structured telemetry)
    constraints = _generate_migration_constraints(
        scenario_id=scenario_id,
        task_family=task_family,
        domain=domain,
        components=system_components,
        dependencies=updated_dependencies,
        required_tests=required_tests,
        evidence_records=evidence_records,
        seed_mgr=seed_mgr,
    )

    scenario = ScenarioModel(
        scenario_id=scenario_id,
        scenario_name=f"{domain.value.replace('_', ' ').title()} - {task_family.name.replace('_', ' ')}",
        description=f"Synthetic enterprise architecture evaluating cryptographic migration reasoning for {task_family.value}.",
        system_components=system_components,
        dependencies=updated_dependencies,
        compatibility_records=compatibility_records,
        evidence_records=evidence_records,
        migration_constraints=constraints,
        required_tests=required_tests,
        metadata=MetadataModel(
            created_at=DETERMINISTIC_TIMESTAMP,
            author="PHOENIX-EVAL Phase 2 Synthetic Engine",
            tags=[domain.value.lower(), task_family.value.lower(), complexity.value.lower()],
            custom={"domain": domain.value, "task_family": task_family.value},
        ),
    )

    return scenario
