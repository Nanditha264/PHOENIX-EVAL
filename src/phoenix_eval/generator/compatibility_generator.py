"""Compatibility generator constructing explicit cryptographic upgrade assessments."""

from typing import Optional

from phoenix_eval.schemas.compatibility import (
    CompatibilityRecord,
    CompatibilityStatus,
)
from phoenix_eval.schemas.components import CryptographicComponent
from phoenix_eval.schemas.evidence import EvidenceRecord


def generate_compatibility_record(
    comp: CryptographicComponent,
    evidence_records: list[EvidenceRecord],
    status: CompatibilityStatus,
    reason: Optional[str] = None,
    assessment_source: str = "cryptographic-readiness-scanner-v2.1",
) -> CompatibilityRecord:
    """Construct an explicit CompatibilityRecord for a component based on evidence."""
    target_alg = comp.metadata.get("target_pqc_algorithm", "ML-KEM-768")
    evid_refs = [e.evidence_id for e in evidence_records]

    if reason is None:
        if status == CompatibilityStatus.SUPPORTED:
            reason = f"Runtime environment '{comp.technology}' supports '{target_alg}' verified via active telemetry."
        elif status == CompatibilityStatus.UNSUPPORTED:
            reason = f"Legacy runtime or firmware in '{comp.technology}' lacks cryptographic primitives for '{target_alg}'."
        else:
            reason = f"Insufficient or unverified telemetry for '{comp.component_name}'; target '{target_alg}' status remains uncertain."

    return CompatibilityRecord(
        component_id=comp.component_id,
        proposed_target=target_alg,
        status=status,
        evidence_references=evid_refs,
        reason=reason,
        assessment_source=assessment_source,
        metadata={"target_algorithm": target_alg},
    )
