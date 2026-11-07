"""Evidence generator synthesizing multi-source cryptographic discovery evidence."""

from datetime import datetime, timezone

from phoenix_eval.generator.seed_manager import SeedManager
from phoenix_eval.schemas.components import CryptographicComponent
from phoenix_eval.schemas.evidence import (
    EvidenceCategory,
    EvidenceRecord,
    EvidenceType,
    VerificationStatus,
)

DETERMINISTIC_TIMESTAMP = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def generate_evidence_for_component(
    comp: CryptographicComponent,
    seed_mgr: SeedManager,
    is_supported: bool,
    is_unknown: bool = False,
    inject_contradiction: bool = False,
    is_false_discovery: bool = False,
) -> list[EvidenceRecord]:
    """Generate realistic discovery evidence records for a component."""
    evidence_list: list[EvidenceRecord] = []
    target_alg = comp.metadata.get("target_pqc_algorithm", "ML-KEM-768")
    cid = comp.component_id

    # 1. Primary discovery evidence (SBOM or Config or Code Analysis)
    if is_false_discovery:
        # T02: Reference appears only in a commented-out config or inactive doc
        ev1 = EvidenceRecord(
            evidence_id=f"evid-code-comment-{cid.replace('comp-', '')}",
            evidence_type=EvidenceType.STATIC_CODE_ANALYSIS,
            source=f"src/config/templates/{cid}.conf.bak",
            description=f"Commented-out reference to '{target_alg}' in legacy backup template.",
            observed_value=f"# TODO: migrate cipher suite to {target_alg}",
            confidence=0.4,
            timestamp=DETERMINISTIC_TIMESTAMP,
            provenance="git:repo-audit/commit-7f41a8",
            evidence_category=EvidenceCategory.ASSUMPTION,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        evidence_list.append(ev1)

        # Contradicting active runtime telemetry proving only classical algorithms are negotiated
        ev2 = EvidenceRecord(
            evidence_id=f"evid-telemetry-active-{cid.replace('comp-', '')}",
            evidence_type=EvidenceType.RUNTIME_TELEMETRY,
            source=f"telemetry/ebpf/probes/{cid}.json",
            description=f"Active eBPF socket monitoring confirms zero execution of '{target_alg}'.",
            observed_value={"active_ciphers": comp.current_algorithms, "pqc_invocations": 0},
            confidence=0.98,
            timestamp=DETERMINISTIC_TIMESTAMP,
            provenance="sensor:ebpf-cluster/trace-9912",
            evidence_category=EvidenceCategory.OBSERVED,
            verification_status=VerificationStatus.VERIFIED,
        )
        evidence_list.append(ev2)
        return evidence_list

    if is_unknown:
        # T04 / Unknown: Conflicting or unverified claims without authoritative telemetry
        ev1 = EvidenceRecord(
            evidence_id=f"evid-vendor-claim-{cid.replace('comp-', '')}",
            evidence_type=EvidenceType.VENDOR_CAPABILITY_STATEMENT,
            source=f"vendor/datasheets/{cid}-preliminary.pdf",
            description=f"Third-party vendor unverified claim of '{target_alg}' roadmap support.",
            observed_value=f"Vendor roadmap indicates planned {target_alg} support in future release.",
            confidence=0.35,
            timestamp=DETERMINISTIC_TIMESTAMP,
            provenance="portal:vendor-rfp/doc-3312",
            evidence_category=EvidenceCategory.ASSUMPTION,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        evidence_list.append(ev1)
        return evidence_list

    if inject_contradiction:
        # Contradictory evidence: Marketing doc claims support, but runtime scan reveals older version
        ev1 = EvidenceRecord(
            evidence_id=f"evid-arch-doc-{cid.replace('comp-', '')}",
            evidence_type=EvidenceType.ARCHITECTURE_DOCUMENTATION,
            source=f"docs/architecture/spec-{cid}.md",
            description=f"Architecture documentation claims component supports '{target_alg}'.",
            observed_value=f"Certified for {target_alg} under corporate PQC initiative.",
            confidence=0.6,
            timestamp=DETERMINISTIC_TIMESTAMP,
            provenance="wiki:arch-portal/rev-45",
            evidence_category=EvidenceCategory.INFERRED,
            verification_status=VerificationStatus.CONFLICTING,
        )
        ev2 = EvidenceRecord(
            evidence_id=f"evid-cipher-scan-{cid.replace('comp-', '')}",
            evidence_type=EvidenceType.CIPHER_SCAN,
            source=f"audit/scans/testssl-{cid}.log",
            description=f"Live cipher scan reveals component library rejects '{target_alg}' ClientHello.",
            observed_value={
                "handshake_status": "FATAL_ILLEGAL_PARAMETER",
                "supported_curves": ["secp256r1", "x25519"],
            },
            confidence=0.99,
            timestamp=DETERMINISTIC_TIMESTAMP,
            provenance="tool:testssl/scan-8812",
            evidence_category=EvidenceCategory.OBSERVED,
            verification_status=VerificationStatus.DISPROVEN,
        )
        evidence_list.extend([ev1, ev2])
        return evidence_list

    # Standard case: Supported vs Unsupported
    if is_supported:
        ev1 = EvidenceRecord(
            evidence_id=f"evid-sbom-{cid.replace('comp-', '')}",
            evidence_type=EvidenceType.SBOM_INSPECTION,
            source=f"cyclonedx/{cid}.bom.json",
            description=f"Verified software bill of materials confirms runtime '{comp.technology}' with PQC modules.",
            observed_value={"technology": comp.technology, "pqc_provider": "Enabled"},
            confidence=0.95,
            timestamp=DETERMINISTIC_TIMESTAMP,
            provenance="ci:cd-build/sbom-artifact-9041",
            evidence_category=EvidenceCategory.OBSERVED,
            verification_status=VerificationStatus.VERIFIED,
        )
        ev2 = EvidenceRecord(
            evidence_id=f"evid-telemetry-{cid.replace('comp-', '')}",
            evidence_type=EvidenceType.RUNTIME_TELEMETRY,
            source=f"telemetry/traces/{cid}.log",
            description=f"Runtime telemetry confirms successful staging handshake using '{target_alg}'.",
            observed_value={"target_algorithm": target_alg, "negotiation": "SUCCESS"},
            confidence=0.98,
            timestamp=DETERMINISTIC_TIMESTAMP,
            provenance="staging:tls-probe/session-5412",
            evidence_category=EvidenceCategory.OBSERVED,
            verification_status=VerificationStatus.VERIFIED,
        )
        evidence_list.extend([ev1, ev2])
    else:
        # Unsupported case
        ev1 = EvidenceRecord(
            evidence_id=f"evid-hw-audit-{cid.replace('comp-', '')}",
            evidence_type=EvidenceType.HARDWARE_ATTESTATION,
            source=f"security/attestation/{cid}.attest",
            description=f"Firmware attestation confirms legacy hardware constraints preventing '{target_alg}'.",
            observed_value={"firmware_version": comp.technology, "pqc_supported": False},
            confidence=1.0,
            timestamp=DETERMINISTIC_TIMESTAMP,
            provenance="audit:fips-attestation/log-1102",
            evidence_category=EvidenceCategory.OBSERVED,
            verification_status=VerificationStatus.VERIFIED,
        )
        evidence_list.append(ev1)

    return evidence_list
