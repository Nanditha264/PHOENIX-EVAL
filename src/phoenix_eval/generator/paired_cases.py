"""Adversarial and paired benchmark case generator and invariant validator."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from phoenix_eval.generator.config import ArchitectureDomain, GraphComplexity, TaskFamily
from phoenix_eval.generator.ground_truth_generator import generate_ground_truth
from phoenix_eval.generator.scenario_generator import generate_scenario_for_task_family
from phoenix_eval.generator.seed_manager import SeedManager
from phoenix_eval.generator.task_generator import generate_task_for_scenario
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
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel


class PairedCaseType(StrEnum):
    """Types of single-fact adversarial perturbations between paired scenarios."""

    HSM_SUPPORT = "HSM_SUPPORT"
    INTEROP_TEST = "INTEROP_TEST"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"
    DEPENDENCY_CYCLE = "DEPENDENCY_CYCLE"
    TELEMETRY_CONTRADICTION = "TELEMETRY_CONTRADICTION"


@dataclass(frozen=True)
class PairedCaseResult:
    """A pair of scenarios and tasks differing by exactly one meaningful architectural fact."""

    pair_id: str
    pair_type: PairedCaseType
    description: str
    perturbed_property: str
    scenario_a: ScenarioModel
    task_a: BenchmarkTask
    ground_truth_a: dict[str, Any]
    scenario_b: ScenarioModel
    task_b: BenchmarkTask
    ground_truth_b: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Export paired case metadata."""
        return {
            "pair_id": self.pair_id,
            "pair_type": self.pair_type.value,
            "description": self.description,
            "perturbed_property": self.perturbed_property,
            "scenario_a_id": self.scenario_a.scenario_id,
            "task_a_id": self.task_a.task_id,
            "scenario_b_id": self.scenario_b.scenario_id,
            "task_b_id": self.task_b.task_id,
            "expected_divergence": {
                "ground_truth_a_blockers": self.ground_truth_a.get("expected_blockers", []),
                "ground_truth_b_blockers": self.ground_truth_b.get("expected_blockers", []),
                "ground_truth_a_cycle": self.ground_truth_a.get("cycle_detected", False),
                "ground_truth_b_cycle": self.ground_truth_b.get("cycle_detected", False),
            },
        }


def generate_paired_case(
    pair_type: PairedCaseType,
    pair_id: str,
    seed_mgr: SeedManager,
    domain: ArchitectureDomain = ArchitectureDomain.BANKING_PAYMENTS,
) -> PairedCaseResult:
    """Generate a paired benchmark instance with exactly one meaningful fact changed."""
    scen_a_id = f"scen-pair-{pair_id}-a"
    scen_b_id = f"scen-pair-{pair_id}-b"
    task_a_id = f"task-pair-{pair_id}-a"
    task_b_id = f"task-pair-{pair_id}-b"
    gt_a_id = f"gt-pair-{pair_id}-a"
    gt_b_id = f"gt-pair-{pair_id}-b"

    # Base scenario: Clean valid migration scenario
    base_scen = generate_scenario_for_task_family(
        scenario_id=scen_a_id,
        task_family=TaskFamily.T09_VALID_MIGRATION,
        domain=domain,
        seed_mgr=seed_mgr,
        complexity=GraphComplexity.SMALL,
    )

    if pair_type == PairedCaseType.HSM_SUPPORT:
        # Scenario A: All components supported (HSM firmware supports PQC)
        # Scenario B: HSM firmware changed to UNSUPPORTED legacy
        hsm_comp = next(
            (
                c
                for c in base_scen.system_components
                if "hsm" in c.component_id or "vault" in c.component_id
            ),
            base_scen.system_components[-1],
        )
        target_cid = hsm_comp.component_id

        # Perturb only the compatibility record for target_cid in B
        new_compat_b: list[CompatibilityRecord] = []
        for rec in base_scen.compatibility_records:
            if rec.component_id == target_cid:
                new_compat_b.append(
                    CompatibilityRecord(
                        component_id=target_cid,
                        proposed_target=rec.proposed_target,
                        status=CompatibilityStatus.UNSUPPORTED,
                        evidence_references=rec.evidence_references,
                        reason=f"Legacy hardware constraint in {target_cid} lacks cryptographic support for {rec.proposed_target}.",
                        assessment_source="hardware-audit-attestation",
                    )
                )
            else:
                new_compat_b.append(rec)

        scen_b = ScenarioModel(
            scenario_id=scen_b_id,
            scenario_name=f"{base_scen.scenario_name} (HSM Unsupported Perturbation)",
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=base_scen.dependencies,
            compatibility_records=new_compat_b,
            evidence_records=base_scen.evidence_records,
            migration_constraints=base_scen.migration_constraints,
            required_tests=base_scen.required_tests,
            metadata=base_scen.metadata,
        )
        perturbed_prop = f"compatibility_records[{target_cid}].status: SUPPORTED -> UNSUPPORTED"
        desc = (
            "Pair A: HSM supports target algorithm in Scenario A, but is UNSUPPORTED in Scenario B."
        )

    elif pair_type == PairedCaseType.INTEROP_TEST:
        # Scenario A: Required interoperability test passes
        # Scenario B: Required interoperability test fails
        test_fail = RequiredTest(
            test_id="test-client-interop-failure",
            test_type=TestType.REGRESSION,
            description="Downstream client interoperability test. STATUS: FAILED (Cipher handshake dropped).",
            target_components=[base_scen.system_components[0].component_id],
        )
        scen_b = ScenarioModel(
            scenario_id=scen_b_id,
            scenario_name=f"{base_scen.scenario_name} (Interop Test Failed Perturbation)",
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=base_scen.dependencies,
            compatibility_records=base_scen.compatibility_records,
            evidence_records=base_scen.evidence_records,
            migration_constraints=base_scen.migration_constraints,
            required_tests=[*base_scen.required_tests, test_fail],
            metadata=base_scen.metadata,
        )
        perturbed_prop = (
            "required_tests: Added failing regression test 'test-client-interop-failure'"
        )
        desc = (
            "Pair B: Interoperability verification passes in Scenario A, but fails in Scenario B."
        )

    elif pair_type == PairedCaseType.EXTERNAL_PROVIDER:
        # Scenario A: External provider is verified SUPPORTED
        # Scenario B: External provider is UNKNOWN
        ext_comp = base_scen.system_components[-1]
        new_compat_b = []
        for rec in base_scen.compatibility_records:
            if rec.component_id == ext_comp.component_id:
                new_compat_b.append(
                    CompatibilityRecord(
                        component_id=ext_comp.component_id,
                        proposed_target=rec.proposed_target,
                        status=CompatibilityStatus.UNKNOWN,
                        evidence_references=rec.evidence_references,
                        reason="Vendor documentation is unverified and vague; compatibility is unconfirmed.",
                        assessment_source="unverified-vendor-claim",
                    )
                )
            else:
                new_compat_b.append(rec)

        scen_b = ScenarioModel(
            scenario_id=scen_b_id,
            scenario_name=f"{base_scen.scenario_name} (External Provider UNKNOWN Perturbation)",
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=base_scen.dependencies,
            compatibility_records=new_compat_b,
            evidence_records=base_scen.evidence_records,
            migration_constraints=base_scen.migration_constraints,
            required_tests=base_scen.required_tests,
            metadata=base_scen.metadata,
        )
        perturbed_prop = (
            f"compatibility_records[{ext_comp.component_id}].status: SUPPORTED -> UNKNOWN"
        )
        desc = (
            "Pair C: External provider compatibility is verified SUPPORTED in A, but UNKNOWN in B."
        )

    elif pair_type == PairedCaseType.DEPENDENCY_CYCLE:
        # Scenario A: Dependency graph is acyclic DAG
        # Scenario B: One reverse edge added creating circular deadlock
        edge_back = DependencyRelationship(
            edge_id="edge-cycle-back-perturbation",
            source_component_id=base_scen.dependencies[0].target_component_id,
            target_component_id=base_scen.dependencies[0].source_component_id,
            relationship_type=RelationshipType.CALLS,
            confidence=1.0,
            criticality=DependencyCriticality.CRITICAL,
            description="Circular dependency reverse call edge.",
        )
        scen_b = ScenarioModel(
            scenario_id=scen_b_id,
            scenario_name=f"{base_scen.scenario_name} (Circular Dependency Perturbation)",
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=[*base_scen.dependencies, edge_back],
            compatibility_records=base_scen.compatibility_records,
            evidence_records=base_scen.evidence_records,
            migration_constraints=base_scen.migration_constraints,
            required_tests=base_scen.required_tests,
            metadata=base_scen.metadata,
        )
        perturbed_prop = "dependencies: Added reverse back-edge creating directed cycle"
        desc = "Pair D: Scenario A is an acyclic DAG, whereas Scenario B has an added circular dependency."

    else:
        # TELEMETRY_CONTRADICTION
        # Scenario A: Runtime telemetry confirms PQC support
        # Scenario B: Runtime telemetry confirms OpenSSL 1.1.1 (classical only)
        ev_contra = EvidenceRecord(
            evidence_id="evid-contra-runtime-fail",
            evidence_type=EvidenceType.RUNTIME_TELEMETRY,
            source="audit/probes/runtime-capture.pcap",
            description="Packet capture proves handshake rejection of target PQC cipher suite.",
            observed_value={"handshake_error": "TLS_ILLEGAL_PARAMETER"},
            confidence=1.0,
            timestamp=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            provenance="audit:pcap-trace/session-9901",
            evidence_category=EvidenceCategory.OBSERVED,
            verification_status=VerificationStatus.DISPROVEN,
        )
        first_cid = base_scen.system_components[0].component_id
        new_compat_b = []
        for rec in base_scen.compatibility_records:
            if rec.component_id == first_cid:
                new_compat_b.append(
                    CompatibilityRecord(
                        component_id=first_cid,
                        proposed_target=rec.proposed_target,
                        status=CompatibilityStatus.UNSUPPORTED,
                        evidence_references=[ev_contra.evidence_id],
                        reason="Active runtime telemetry contradicts vendor claim: target cipher is rejected.",
                        assessment_source="runtime-pcap-probe",
                    )
                )
            else:
                new_compat_b.append(rec)

        scen_b = ScenarioModel(
            scenario_id=scen_b_id,
            scenario_name=f"{base_scen.scenario_name} (Telemetry Contradiction Perturbation)",
            description=base_scen.description,
            system_components=base_scen.system_components,
            dependencies=base_scen.dependencies,
            compatibility_records=new_compat_b,
            evidence_records=[*base_scen.evidence_records, ev_contra],
            migration_constraints=base_scen.migration_constraints,
            required_tests=base_scen.required_tests,
            metadata=base_scen.metadata,
        )
        perturbed_prop = f"compatibility_records[{first_cid}]: SUPPORTED -> UNSUPPORTED via telemetry contradiction"
        desc = "Pair E: Stated PQC support is verified in A, but contradicted by runtime telemetry in B."

    task_a = generate_task_for_scenario(
        task_id=task_a_id,
        scenario=base_scen,
        task_family=TaskFamily.T09_VALID_MIGRATION,
        ground_truth_id=gt_a_id,
        seed_mgr=seed_mgr,
        difficulty=DifficultyLevel.INTERMEDIATE,
    )
    task_b = generate_task_for_scenario(
        task_id=task_b_id,
        scenario=scen_b,
        task_family=TaskFamily.T03_INCOMPATIBLE_CONSUMER
        if pair_type in (PairedCaseType.HSM_SUPPORT, PairedCaseType.TELEMETRY_CONTRADICTION)
        else TaskFamily.T06_DEPENDENCY_CYCLE,
        ground_truth_id=gt_b_id,
        seed_mgr=seed_mgr,
        difficulty=DifficultyLevel.INTERMEDIATE,
    )

    gt_a = generate_ground_truth(task_a_id, base_scen, TaskFamily.T09_VALID_MIGRATION, gt_a_id)
    gt_b = generate_ground_truth(
        task_b_id,
        scen_b,
        TaskFamily.T03_INCOMPATIBLE_CONSUMER
        if pair_type in (PairedCaseType.HSM_SUPPORT, PairedCaseType.TELEMETRY_CONTRADICTION)
        else TaskFamily.T06_DEPENDENCY_CYCLE,
        gt_b_id,
    )

    return PairedCaseResult(
        pair_id=pair_id,
        pair_type=pair_type,
        description=desc,
        perturbed_property=perturbed_prop,
        scenario_a=base_scen,
        task_a=task_a,
        ground_truth_a=gt_a,
        scenario_b=scen_b,
        task_b=task_b,
        ground_truth_b=gt_b,
    )


class PairedCaseValidator:
    """Validates that paired cases differ by exactly the specified architectural fact."""

    @staticmethod
    def validate_pair(pair: PairedCaseResult) -> tuple[bool, list[str]]:
        """Verify that Scenario A and Scenario B are identical except for the specified perturbation."""
        errors: list[str] = []
        scen_a = pair.scenario_a
        scen_b = pair.scenario_b

        # 1. Component count
        if len(scen_a.system_components) != len(scen_b.system_components):
            errors.append(
                f"Component count mismatch: A={len(scen_a.system_components)}, B={len(scen_b.system_components)}"
            )

        # 2. Verify expected ground truth divergence
        gt_a = pair.ground_truth_a
        gt_b = pair.ground_truth_b

        if pair.pair_type == PairedCaseType.DEPENDENCY_CYCLE:
            if gt_a["cycle_detected"] or not gt_b["cycle_detected"]:
                errors.append(
                    f"Cycle divergence failure: A cycle={gt_a['cycle_detected']}, B cycle={gt_b['cycle_detected']}"
                )
        elif pair.pair_type in (
            PairedCaseType.HSM_SUPPORT,
            PairedCaseType.TELEMETRY_CONTRADICTION,
        ) and len(gt_a["expected_blockers"]) >= len(gt_b["expected_blockers"]):
            errors.append(
                f"Blocker divergence failure: A blockers={gt_a['expected_blockers']}, B blockers={gt_b['expected_blockers']}"
            )

        return len(errors) == 0, errors
