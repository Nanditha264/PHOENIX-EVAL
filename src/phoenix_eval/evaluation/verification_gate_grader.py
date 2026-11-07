"""Deterministic grading engine for pre-migration verification gates and mandatory test compliance.

Addresses the Phase 2 interop-test-02 limitation:
A scenario with zero compatibility blockers is NOT migration-ready if mandatory
verification, staging, or interoperability tests are missing, pending, or failed.
"""

from dataclasses import dataclass
import re
from typing import Any, Optional

from phoenix_eval.evaluation.violation_catalog import VIOLATIONS
from phoenix_eval.schemas.evaluation import CriticalViolation, ViolationSeverity
from phoenix_eval.schemas.response_contract import (
    ModelDecision,
    ModelResponseContract,
    ReportedTestStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.utils.identifiers import generate_id


@dataclass(frozen=True)
class VerificationGateGradingResult:
    """Outcome of grading pre-migration verification and interoperability gates."""

    dimension_name: str
    raw_score: float
    max_score: float
    normalized_score: float
    passed: bool
    readiness_blocked_by_gates: bool
    mandatory_tests_present: list[str]
    mandatory_tests_missing: list[str]
    failed_tests_detected: list[str]
    pending_tests_detected: list[str]
    skipped_tests_detected: list[str]
    deductions: list[tuple[float, str]]
    violations: list[CriticalViolation]
    details: dict[str, Any]


class VerificationGateGrader:
    """Grades model's adherence to pre-migration validation gates and empirical test outcomes."""

    def __init__(self, max_score: float = 15.0) -> None:
        self.max_score = max_score

    def grade(
        self,
        contract: Optional[ModelResponseContract],
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
    ) -> VerificationGateGradingResult:
        """Evaluate verification gate compliance and enforce test-based migration blocking."""
        if not contract:
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description="Cannot evaluate verification gates from malformed or unparseable response.",
                severity=ViolationSeverity.CRITICAL,
                evidence="Parsed contract is None.",
            )
            return VerificationGateGradingResult(
                dimension_name="validation_and_safety_gates",
                raw_score=0.0,
                max_score=self.max_score,
                normalized_score=0.0,
                passed=False,
                readiness_blocked_by_gates=True,
                mandatory_tests_present=[],
                mandatory_tests_missing=[],
                failed_tests_detected=[],
                pending_tests_detected=[],
                skipped_tests_detected=[],
                deductions=[
                    (self.max_score, "Malformed response prevents validation gate evaluation.")
                ],
                violations=[viol],
                details={"error": "Malformed response"},
            )

        scenario_tests = {t.test_id: t for t in scenario.required_tests}
        scenario_evids = {e.evidence_id for e in scenario.evidence_records}
        deductions: list[tuple[float, str]] = []
        violations: list[CriticalViolation] = []

        # Map reported tests (only valid scenario tests count towards satisfying mandatory gates)
        reported_test_map = {
            res.test_id: res.reported_status
            for res in contract.verification_results
            if res.test_id in scenario_tests
        }

        # Check for unknown test IDs
        unknown_tests = [
            res.test_id
            for res in contract.verification_results
            if res.test_id not in scenario_tests
        ]
        if unknown_tests:
            deductions.append(
                (
                    min(len(unknown_tests) * 2.0, 4.0),
                    f"Reported unknown test IDs that do not exist in the scenario: {unknown_tests}.",
                )
            )

        # Check for invalid evidence on claimed PASSED tests
        invalid_evidence_tests = [
            res.test_id
            for res in contract.verification_results
            if res.reported_status == ReportedTestStatus.PASSED
            and res.evidence_reference
            and res.evidence_reference not in scenario_evids
        ]
        if invalid_evidence_tests:
            deductions.append(
                (
                    min(len(invalid_evidence_tests) * 2.5, 5.0),
                    f"Claimed PASSED with non-existent evidence IDs on test(s): {invalid_evidence_tests}.",
                )
            )

        # Check scenario test descriptions for explicit failure annotations (e.g. STATUS: FAILED)
        scenario_failing_tests = {
            t.test_id
            for t in scenario.required_tests
            if bool(re.search(r'\bSTATUS\s*:\s*(FAILED|FAIL)\b', t.description, re.IGNORECASE))
        }

        mandatory_present = sorted(set(scenario_tests.keys()) & set(reported_test_map.keys()))
        mandatory_missing = sorted(set(scenario_tests.keys()) - set(reported_test_map.keys()))

        failed_tests = sorted(
            scenario_failing_tests
            | {tid for tid, stat in reported_test_map.items() if stat == ReportedTestStatus.FAILED}
        )
        pending_tests = sorted(
            {tid for tid, stat in reported_test_map.items() if stat == ReportedTestStatus.PENDING}
        )
        skipped_tests = sorted(
            {tid for tid, stat in reported_test_map.items() if stat == ReportedTestStatus.SKIPPED}
        )
        pending_or_skipped = sorted(set(pending_tests) | set(skipped_tests))

        readiness_blocked_by_gates = (
            len(failed_tests) > 0
            or len(pending_or_skipped) > 0
            or len(mandatory_missing) > 0
            or (len(scenario_tests) == 0 and "t07" in scenario.scenario_id.lower())
        )

        # Violation A: Failed Mandatory Test Ignored
        if failed_tests and contract.decision == ModelDecision.MIGRATION_READY:
            ded = VIOLATIONS["VIO_FAILED_TEST_IGNORED"].score_deduction
            deductions.append(
                (
                    ded,
                    f"Declared MIGRATION_READY despite {len(failed_tests)} failed mandatory verification test(s): {failed_tests}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_FAILED_TEST_IGNORED"),
                    rule_name="VIO_FAILED_TEST_IGNORED",
                    description=f"Model declared migration ready while required verification tests failed: {failed_tests}.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Failed tests: {failed_tests}, Decision: {contract.decision}",
                )
            )

        # Violation B: Pending / Skipped Test Certified as Ready
        if pending_or_skipped and contract.decision == ModelDecision.MIGRATION_READY:
            ded = VIOLATIONS["VIO_PENDING_TEST_CERTIFIED"].score_deduction
            deductions.append(
                (
                    ded,
                    f"Certified migration readiness while tests remain PENDING or SKIPPED: {pending_or_skipped}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_PENDING_TEST_CERTIFIED"),
                    rule_name="VIO_PENDING_TEST_CERTIFIED",
                    description=f"Model certified production cutover while required tests are pending or skipped: {pending_or_skipped}.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Pending/skipped tests: {pending_or_skipped}, Decision: {contract.decision}",
                )
            )

        # Violation C: Required Mandatory Test Missing
        if mandatory_missing and contract.decision == ModelDecision.MIGRATION_READY:
            ded = VIOLATIONS["VIO_REQUIRED_TEST_MISSING"].score_deduction
            deductions.append(
                (
                    ded,
                    f"Declared MIGRATION_READY while omitting {len(mandatory_missing)} mandatory verification test(s): {mandatory_missing}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_REQUIRED_TEST_MISSING"),
                    rule_name="VIO_REQUIRED_TEST_MISSING",
                    description=f"Model certified migration readiness without mandatory verification test results for: {mandatory_missing}.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Missing mandatory tests: {mandatory_missing}, Decision: {contract.decision}",
                )
            )
        elif (
            len(scenario_tests) == 0
            and "t07" in scenario.scenario_id.lower()
            and contract.decision == ModelDecision.MIGRATION_READY
        ):
            ded = VIOLATIONS["VIO_REQUIRED_TEST_MISSING"].score_deduction
            deductions.append(
                (
                    ded,
                    "Certified migration readiness in a T07 scenario where mandatory validation evidence is completely missing.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_REQUIRED_TEST_MISSING"),
                    rule_name="VIO_REQUIRED_TEST_MISSING",
                    description="Model certified migration without mandatory verification or interoperability test evidence.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence="Required tests list is empty in T07 scenario.",
                )
            )
        elif mandatory_missing:
            # Non-critical deduction for omitting required tests when not claiming MIGRATION_READY
            ded = min(len(mandatory_missing) * 2.0, 5.0)
            deductions.append(
                (
                    ded,
                    f"Omitted {len(mandatory_missing)} required scenario test(s) from verification report: {mandatory_missing[:3]}.",
                )
            )

        total_deduction = sum(d[0] for d in deductions)
        final_score = max(0.0, round(self.max_score - total_deduction, 2))
        normalized = round(final_score / self.max_score, 4)

        has_critical_gate_violation = (
            failed_tests or pending_or_skipped or mandatory_missing
        ) and contract.decision == ModelDecision.MIGRATION_READY

        return VerificationGateGradingResult(
            dimension_name="validation_and_safety_gates",
            raw_score=final_score,
            max_score=self.max_score,
            normalized_score=normalized,
            passed=final_score >= (self.max_score * 0.70) and not has_critical_gate_violation,
            readiness_blocked_by_gates=readiness_blocked_by_gates,
            mandatory_tests_present=mandatory_present,
            mandatory_tests_missing=mandatory_missing,
            failed_tests_detected=failed_tests,
            pending_tests_detected=pending_tests,
            skipped_tests_detected=skipped_tests,
            deductions=deductions,
            violations=violations,
            details={
                "mandatory_test_count": len(scenario_tests),
                "reported_test_count": len(contract.verification_results),
                "failed_test_count": len(failed_tests),
                "pending_test_count": len(pending_tests),
                "skipped_test_count": len(skipped_tests),
                "missing_test_count": len(mandatory_missing),
                "readiness_blocked_by_gates": readiness_blocked_by_gates,
            },
        )
