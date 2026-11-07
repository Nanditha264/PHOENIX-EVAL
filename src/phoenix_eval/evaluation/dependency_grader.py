"""Deterministic grading engine for dependency identification and graph topology."""

from dataclasses import dataclass
from typing import Any, Optional

from phoenix_eval.evaluation.violation_catalog import VIOLATIONS
from phoenix_eval.schemas.evaluation import CriticalViolation, ViolationSeverity
from phoenix_eval.schemas.response_contract import ModelResponseContract
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.utils.identifiers import generate_id


@dataclass(frozen=True)
class DependencyGradingResult:
    """Outcome of grading the dependency identification dimension."""

    dimension_name: str
    raw_score: float
    max_score: float
    normalized_score: float
    passed: bool
    correct_edges: list[tuple[str, str]]
    missing_edges: list[tuple[str, str]]
    invented_edges: list[tuple[str, str]]
    inverted_edges: list[tuple[str, str]]
    deductions: list[tuple[float, str]]
    violations: list[CriticalViolation]
    details: dict[str, Any]


class DependencyGrader:
    """Grades model's identified dependencies against scenario ground truth facts."""

    def __init__(self, max_score: float = 20.0) -> None:
        self.max_score = max_score

    def grade(
        self,
        contract: Optional[ModelResponseContract],
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
    ) -> DependencyGradingResult:
        """Evaluate identified dependencies with edge-direction and false-positive checks."""
        if not contract:
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description="Cannot evaluate dependencies from malformed or unparseable response.",
                severity=ViolationSeverity.CRITICAL,
                evidence="Parsed contract is None.",
            )
            return DependencyGradingResult(
                dimension_name="dependency_identification",
                raw_score=0.0,
                max_score=self.max_score,
                normalized_score=0.0,
                passed=False,
                correct_edges=[],
                missing_edges=[],
                invented_edges=[],
                inverted_edges=[],
                deductions=[(self.max_score, "Malformed response prevents dependency evaluation.")],
                violations=[viol],
                details={"error": "Malformed response"},
            )

        # Active expected dependencies: (caller, prerequisite)
        expected_edges = {
            (d.source_component_id, d.target_component_id) for d in scenario.dependencies
        }
        critical_expected = {
            (d.source_component_id, d.target_component_id)
            for d in scenario.dependencies
            if d.criticality.value in ("HIGH", "CRITICAL")
        }

        # Reported edges: (source, target)
        reported_edges = {
            (d.source_component_id, d.target_component_id) for d in contract.identified_dependencies
        }

        correct = expected_edges & reported_edges
        missing = expected_edges - reported_edges
        extra = reported_edges - expected_edges

        # Check for inverted edges: (u, v) expected, but (v, u) reported
        inverted = set()
        invented = set()
        for u, v in extra:
            if (v, u) in expected_edges:
                inverted.add((u, v))
            else:
                invented.add((u, v))

        # Precision, recall, and F1 calculation
        n_expected = len(expected_edges)
        n_reported = len(reported_edges)

        recall = (len(correct) / n_expected) if n_expected > 0 else 1.0
        precision = (
            (len(correct) / n_reported) if n_reported > 0 else (1.0 if n_expected == 0 else 0.0)
        )

        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        base_score = f1 * self.max_score

        deductions: list[tuple[float, str]] = []
        violations: list[CriticalViolation] = []

        # Deductions & Violations for Inverted Edges
        if inverted:
            ded = VIOLATIONS["VIO_DEPENDENCY_ORDER_REVERSED"].score_deduction
            deductions.append(
                (
                    min(ded, base_score),
                    f"Inverted {len(inverted)} dependency edge(s) (caller/callee reversed: {sorted(inverted)[:3]}).",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_DEPENDENCY_ORDER_REVERSED"),
                    rule_name="VIO_DEPENDENCY_ORDER_REVERSED",
                    description="Model reversed dependency orientation, reporting callee as dependent on caller.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Inverted edges: {sorted(inverted)}",
                )
            )

        # Deductions & Violations for Missing Critical Dependencies
        critical_missing = missing & critical_expected
        if critical_missing:
            ded = VIOLATIONS["VIO_KNOWN_DEPENDENCY_OMITTED"].score_deduction
            deductions.append(
                (
                    ded,
                    f"Omitted {len(critical_missing)} critical dependency edge(s): {sorted(critical_missing)[:3]}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_KNOWN_DEPENDENCY_OMITTED"),
                    rule_name="VIO_KNOWN_DEPENDENCY_OMITTED",
                    description="Model failed to identify active critical prerequisite dependencies.",
                    severity=ViolationSeverity.HIGH,
                    evidence=f"Missing critical edges: {sorted(critical_missing)}",
                )
            )

        # Deductions for Invented Edges
        if invented:
            ded = min(len(invented) * 1.5, 6.0)
            deductions.append(
                (
                    ded,
                    f"Invented {len(invented)} unverified dependency edge(s): {sorted(invented)[:3]}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_INVENTED_DEPENDENCY"),
                    rule_name="VIO_INVENTED_DEPENDENCY",
                    description="Model hallucinated non-existent dependency links.",
                    severity=ViolationSeverity.HIGH,
                    evidence=f"Invented edges: {sorted(invented)}",
                )
            )

        total_deduction = sum(d[0] for d in deductions)
        final_score = max(0.0, round(base_score - total_deduction, 2))
        normalized = round(final_score / self.max_score, 4)

        return DependencyGradingResult(
            dimension_name="dependency_identification",
            raw_score=final_score,
            max_score=self.max_score,
            normalized_score=normalized,
            passed=final_score >= (self.max_score * 0.70),
            correct_edges=sorted(correct),
            missing_edges=sorted(missing),
            invented_edges=sorted(invented),
            inverted_edges=sorted(inverted),
            deductions=deductions,
            violations=violations,
            details={
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "expected_count": n_expected,
                "reported_count": n_reported,
            },
        )
