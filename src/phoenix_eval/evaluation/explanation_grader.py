"""Deterministic grading engine for explanation clarity, fact grounding, and traceability.

Does not reward generic verbosity. Evaluates whether the narrative explicitly
addresses identified blockers, critical dependencies, required validation,
and epistemic boundaries.
"""

from dataclasses import dataclass
from typing import Any, Optional

from phoenix_eval.schemas.evaluation import CriticalViolation, ViolationSeverity
from phoenix_eval.schemas.response_contract import ModelDecision, ModelResponseContract
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.utils.identifiers import generate_id


@dataclass(frozen=True)
class ExplanationGradingResult:
    """Outcome of grading the explanation and traceability dimension."""

    dimension_name: str
    raw_score: float
    max_score: float
    normalized_score: float
    passed: bool
    addresses_blockers: bool
    cites_telemetry: bool
    explains_wave_ordering: bool
    acknowledges_uncertainty: bool
    deductions: list[tuple[float, str]]
    violations: list[CriticalViolation]
    details: dict[str, Any]


class ExplanationGrader:
    """Grades model's explanation deterministically without rewarding ungrounded verbosity."""

    def __init__(self, max_score: float = 10.0) -> None:
        self.max_score = max_score

    def grade(
        self,
        contract: Optional[ModelResponseContract],
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
    ) -> ExplanationGradingResult:
        """Evaluate explanation grounding using deterministic keyword, ID, and concept matching."""
        if not contract or not contract.explanation.strip():
            return ExplanationGradingResult(
                dimension_name="explanation_and_traceability",
                raw_score=0.0,
                max_score=self.max_score,
                normalized_score=0.0,
                passed=False,
                addresses_blockers=False,
                cites_telemetry=False,
                explains_wave_ordering=False,
                acknowledges_uncertainty=False,
                deductions=[(self.max_score, "Explanation is missing or empty.")],
                violations=[],
                details={"error": "Empty explanation"},
            )

        text = contract.explanation.lower()
        deductions: list[tuple[float, str]] = []
        violations: list[CriticalViolation] = []

        # 0. Adversarial Bypass & Contradiction Check in Explanation
        # Detect if model advises bypassing safety gates, ignoring failed tests, or forcing cutovers
        unsafe_phrases = [
            "bypass safety gate",
            "skip mandatory test",
            "skip verification test",
            "ignore failed test",
            "ignore test failure",
            "override blocker",
            "force cutover despite",
            "ignore dependency cycle",
            "ignore circular dependency",
            "proceed with cutover despite failure",
            "disable rollback",
        ]
        detected_unsafe_phrases = [p for p in unsafe_phrases if p in text]
        if detected_unsafe_phrases:
            deductions.append(
                (
                    self.max_score,
                    f"Explanation advocates unsafe bypass operations: {detected_unsafe_phrases}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_EXPLANATION_CONTRADICTION"),
                    rule_name="VIO_EXPLANATION_CONTRADICTION",
                    description=f"Model explanation advises unsafe bypass operations: {detected_unsafe_phrases}.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Unsafe phrases: {detected_unsafe_phrases}",
                )
            )

        # Contradiction: explanation claims migration is ready/safe while decision is MIGRATION_BLOCKED
        if contract.decision == ModelDecision.MIGRATION_BLOCKED and (
            "migration is completely ready" in text
            or "fully ready for production cutover" in text
            or "safe to deploy immediately" in text
        ):
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_CONTRADICTORY_DECISION"),
                    rule_name="VIO_CONTRADICTORY_DECISION",
                    description="Explanation claims system is fully ready for cutover while decision is MIGRATION_BLOCKED.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Decision: {contract.decision}, Explanation text asserts immediate production readiness.",
                )
            )

        # 1. Blocker references
        # If ground truth has expected blockers, check if explanation mentions them
        expected_blockers = [b.lower() for b in ground_truth.get("expected_blockers", [])]
        addresses_blockers = True
        if expected_blockers:
            mentioned_blockers = [b for b in expected_blockers if b in text]
            if not mentioned_blockers:
                deductions.append(
                    (
                        3.0,
                        f"Explanation fails to explain identified blocker(s): {expected_blockers[:3]}.",
                    )
                )
                addresses_blockers = False

        # 2. Evidence & Telemetry references
        cites_telemetry = any(
            eid.lower() in text for eid in [e.evidence_id for e in scenario.evidence_records]
        ) or any(
            term in text
            for term in [
                "telemetry",
                "audit",
                "scan",
                "packet",
                "handshake",
                "evidence",
                "provenance",
            ]
        )
        if not cites_telemetry:
            deductions.append(
                (2.5, "Explanation does not ground reasoning in discovery evidence or telemetry.")
            )

        # 3. Wave / Precedence reasoning
        explains_waves = any(
            term in text
            for term in [
                "wave",
                "prerequisite",
                "order",
                "dependency",
                "caller",
                "sink",
                "topo",
                "cutover",
                "sequence",
            ]
        )
        if not explains_waves:
            deductions.append(
                (
                    2.5,
                    "Explanation does not articulate dependency order or wave sequencing rationale.",
                )
            )

        # 4. Uncertainty & Assumption boundary
        has_unknown = any(c.status.value == "UNKNOWN" for c in scenario.compatibility_records)
        acknowledges_uncertainty = any(
            term in text
            for term in [
                "unknown",
                "unverified",
                "uncertain",
                "assumption",
                "conditional",
                "fallback",
                "dual-stack",
            ]
        )
        if has_unknown and not acknowledges_uncertainty:
            deductions.append(
                (2.0, "Failed to address unknown status or conditional risks in narrative.")
            )

        total_deduction = sum(d[0] for d in deductions)
        final_score = max(0.0, round(self.max_score - total_deduction, 2))
        normalized = round(final_score / self.max_score, 4)

        return ExplanationGradingResult(
            dimension_name="explanation_and_traceability",
            raw_score=final_score,
            max_score=self.max_score,
            normalized_score=normalized,
            passed=final_score >= (self.max_score * 0.70) and len(violations) == 0,
            addresses_blockers=addresses_blockers,
            cites_telemetry=cites_telemetry,
            explains_wave_ordering=explains_waves,
            acknowledges_uncertainty=acknowledges_uncertainty,
            deductions=deductions,
            violations=violations,
            details={
                "char_count": len(contract.explanation),
                "addresses_blockers": addresses_blockers,
                "cites_telemetry": cites_telemetry,
                "explains_wave_ordering": explains_waves,
            },
        )
