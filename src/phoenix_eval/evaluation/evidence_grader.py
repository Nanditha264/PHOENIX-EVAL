"""Deterministic grading engine for evidence grounding, citation validity, and uncertainty calibration."""

from dataclasses import dataclass
from typing import Any, Optional

from phoenix_eval.evaluation.violation_catalog import VIOLATIONS
from phoenix_eval.schemas.evaluation import CriticalViolation, ViolationSeverity
from phoenix_eval.schemas.evidence import VerificationStatus
from phoenix_eval.schemas.response_contract import ModelResponseContract
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.utils.identifiers import generate_id


@dataclass(frozen=True)
class EvidenceGradingResult:
    """Outcome of grading the evidence grounding and uncertainty dimension."""

    dimension_name: str
    raw_score: float
    max_score: float
    normalized_score: float
    passed: bool
    valid_citations: list[str]
    invalid_citations: list[str]
    unsupported_claims: list[str]
    uncertainties_calibrated: bool
    deductions: list[tuple[float, str]]
    violations: list[CriticalViolation]
    details: dict[str, Any]


class EvidenceGrader:
    """Grades model's evidence citations and epistemic calibration against scenario facts."""

    def __init__(self, max_score: float = 15.0) -> None:
        self.max_score = max_score

    def grade(
        self,
        contract: Optional[ModelResponseContract],
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
    ) -> EvidenceGradingResult:
        """Evaluate evidence citation validity, epistemic category distinction, and contradiction handling."""
        if not contract:
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description="Cannot evaluate evidence citations from malformed or unparseable response.",
                severity=ViolationSeverity.CRITICAL,
                evidence="Parsed contract is None.",
            )
            return EvidenceGradingResult(
                dimension_name="evidence_and_uncertainty",
                raw_score=0.0,
                max_score=self.max_score,
                normalized_score=0.0,
                passed=False,
                valid_citations=[],
                invalid_citations=[],
                unsupported_claims=[],
                uncertainties_calibrated=False,
                deductions=[(self.max_score, "Malformed response prevents evidence evaluation.")],
                violations=[viol],
                details={"error": "Malformed response"},
            )

        scenario_evids = {e.evidence_id: e for e in scenario.evidence_records}
        deductions: list[tuple[float, str]] = []
        violations: list[CriticalViolation] = []

        # 1. Collect all cited evidence IDs
        all_cited: set[str] = set(contract.evidence_references)
        for dep in contract.identified_dependencies:
            if dep.evidence_reference:
                all_cited.add(dep.evidence_reference)
        for comp in contract.compatibility_assessments:
            if comp.evidence_reference:
                all_cited.add(comp.evidence_reference)
        for test_res in contract.verification_results:
            if test_res.evidence_reference:
                all_cited.add(test_res.evidence_reference)

        valid_citations = sorted(all_cited & set(scenario_evids.keys()))
        invalid_citations = sorted(all_cited - set(scenario_evids.keys()))

        # Check for Invalid / Invented Evidence IDs
        if invalid_citations:
            ded = VIOLATIONS["VIO_INVALID_EVIDENCE_REFERENCE"].score_deduction
            deductions.append(
                (
                    min(len(invalid_citations) * 2.0, ded),
                    f"Cited {len(invalid_citations)} non-existent evidence ID(s): {invalid_citations[:3]}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_INVALID_EVIDENCE_REFERENCE"),
                    rule_name="VIO_INVALID_EVIDENCE_REFERENCE",
                    description=f"Model hallucinated non-existent evidence IDs: {invalid_citations}.",
                    severity=ViolationSeverity.HIGH,
                    evidence=f"Invalid IDs: {invalid_citations}",
                )
            )

        # Check citation coverage
        if scenario_evids and not valid_citations:
            deductions.append(
                (5.0, "Model provided zero citations to verified scenario evidence records.")
            )

        # 2. Epistemic Calibration & Uncertainty Check
        # If scenario contains UNKNOWN components or unverified evidence, check whether model acknowledged uncertainty
        has_unknown = any(c.status.value == "UNKNOWN" for c in scenario.compatibility_records)
        has_unverified = any(
            e.verification_status == VerificationStatus.UNVERIFIED
            for e in scenario.evidence_records
        )
        needs_uncertainty = has_unknown or has_unverified

        uncertainties_stated = len(contract.uncertainties) > 0 or len(contract.assumptions) > 0
        uncertainties_calibrated = True

        if needs_uncertainty and not uncertainties_stated:
            deductions.append(
                (
                    3.0,
                    "Failed to state uncertainties or assumptions despite ambiguous telemetry in the scenario.",
                )
            )
            uncertainties_calibrated = False

        # 3. Contradictory & Disproven Telemetry Handling
        # If scenario has conflicting evidence (e.g. wire capture vs config audit), check if model cited the contradicted one
        contradicted_evids = {
            e.evidence_id
            for e in scenario.evidence_records
            if e.verification_status
            in (
                VerificationStatus.DISPROVEN,
                VerificationStatus.CONTRADICTED,
                VerificationStatus.CONFLICTING,
            )
        }
        relied_on_contradicted = all_cited & contradicted_evids
        if relied_on_contradicted:
            ded = VIOLATIONS["VIO_UNSUPPORTED_EVIDENCE_CLAIM"].score_deduction
            deductions.append(
                (
                    ded,
                    f"Relied on contradicted or disproven evidence records: {sorted(relied_on_contradicted)}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_UNSUPPORTED_EVIDENCE_CLAIM"),
                    rule_name="VIO_UNSUPPORTED_EVIDENCE_CLAIM",
                    description="Model relied on contradicted telemetry disproven by empirical evidence.",
                    severity=ViolationSeverity.HIGH,
                    evidence=f"Contradicted records cited: {sorted(relied_on_contradicted)}",
                )
            )

        # 4. Stale Evidence Handling
        stale_evids = {
            e.evidence_id
            for e in scenario.evidence_records
            if e.verification_status == VerificationStatus.STALE
            or getattr(e, "is_stale", False)
        }
        relied_on_stale = all_cited & stale_evids
        if relied_on_stale:
            ded = VIOLATIONS["VIO_STALE_EVIDENCE_RELIED_UPON"].score_deduction
            deductions.append(
                (
                    ded,
                    f"Relied on stale or outdated evidence records: {sorted(relied_on_stale)}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_STALE_EVIDENCE_RELIED_UPON"),
                    rule_name="VIO_STALE_EVIDENCE_RELIED_UPON",
                    description="Model relied on stale evidence without fresh verification telemetry.",
                    severity=ViolationSeverity.HIGH,
                    evidence=f"Stale records cited: {sorted(relied_on_stale)}",
                )
            )

        # 5. Unsupported Claims Check (Never treat missing evidence as positive evidence)
        for comp in contract.compatibility_assessments:
            if comp.status.value == "SUPPORTED" and comp.evidence_reference:
                ev = scenario_evids.get(comp.evidence_reference)
                if ev is None:
                    # Model cited non-existent / fabricated evidence ID to claim SUPPORTED
                    ded = VIOLATIONS["VIO_FALSE_VERIFICATION_CLAIM"].score_deduction
                    deductions.append(
                        (
                            ded,
                            f"Component '{comp.component_id}' claimed SUPPORTED citing non-existent evidence '{comp.evidence_reference}'.",
                        )
                    )
                    violations.append(
                        CriticalViolation(
                            violation_id=generate_id("viol", "VIO_FALSE_VERIFICATION_CLAIM"),
                            rule_name="VIO_FALSE_VERIFICATION_CLAIM",
                            description=f"Model made false verification claim for '{comp.component_id}' citing non-existent evidence ID '{comp.evidence_reference}'.",
                            severity=ViolationSeverity.CRITICAL,
                            evidence=f"Component: {comp.component_id}, Invalid Evidence: {comp.evidence_reference}",
                        )
                    )
                elif ev.verification_status in (
                    VerificationStatus.UNKNOWN,
                    VerificationStatus.NOT_APPLICABLE,
                    VerificationStatus.CONTRADICTED,
                    VerificationStatus.DISPROVEN,
                ):
                    deductions.append(
                        (
                            3.0,
                            f"Component '{comp.component_id}' claimed SUPPORTED citing {ev.verification_status.value} evidence '{ev.evidence_id}'.",
                        )
                    )
                    if ev.verification_status in (VerificationStatus.CONTRADICTED, VerificationStatus.DISPROVEN):
                        violations.append(
                            CriticalViolation(
                                violation_id=generate_id("viol", "VIO_FALSE_VERIFICATION_CLAIM"),
                                rule_name="VIO_FALSE_VERIFICATION_CLAIM",
                                description=f"Component '{comp.component_id}' claimed SUPPORTED citing contradicted/disproven telemetry '{ev.evidence_id}'.",
                                severity=ViolationSeverity.CRITICAL,
                                evidence=f"Component: {comp.component_id}, Contradicted Evidence: {ev.evidence_id}",
                            )
                        )
                elif ev.target_component_id and ev.target_component_id != comp.component_id:
                    deductions.append(
                        (
                            4.0,
                            f"Component '{comp.component_id}' cited evidence '{ev.evidence_id}' scoped specifically to component '{ev.target_component_id}'.",
                        )
                    )
                    violations.append(
                        CriticalViolation(
                            violation_id=generate_id("viol", "VIO_UNSUPPORTED_EVIDENCE_CLAIM"),
                            rule_name="VIO_UNSUPPORTED_EVIDENCE_CLAIM",
                            description=f"Evidence '{ev.evidence_id}' targets '{ev.target_component_id}', but was cited for '{comp.component_id}'.",
                            severity=ViolationSeverity.HIGH,
                            evidence=f"Target: {ev.target_component_id}, Cited for: {comp.component_id}",
                        )
                    )

        total_deduction = sum(d[0] for d in deductions)
        final_score = max(0.0, round(self.max_score - total_deduction, 2))
        normalized = round(final_score / self.max_score, 4)

        return EvidenceGradingResult(
            dimension_name="evidence_and_uncertainty",
            raw_score=final_score,
            max_score=self.max_score,
            normalized_score=normalized,
            passed=final_score >= (self.max_score * 0.70) and len(invalid_citations) == 0,
            valid_citations=valid_citations,
            invalid_citations=invalid_citations,
            unsupported_claims=sorted(relied_on_contradicted),
            uncertainties_calibrated=uncertainties_calibrated,
            deductions=deductions,
            violations=violations,
            details={
                "valid_citation_count": len(valid_citations),
                "invalid_citation_count": len(invalid_citations),
                "disproven_citation_count": len(relied_on_contradicted),
                "stale_citation_count": len(relied_on_stale),
                "uncertainties_calibrated": uncertainties_calibrated,
            },
        )
