"""Deterministic grading engine for component compatibility reasoning and epistemic discipline."""

from dataclasses import dataclass
from typing import Any, Optional

from phoenix_eval.evaluation.violation_catalog import VIOLATIONS
from phoenix_eval.schemas.compatibility import CompatibilityStatus
from phoenix_eval.schemas.evaluation import CriticalViolation, ViolationSeverity
from phoenix_eval.schemas.response_contract import (
    ModelResponseContract,
    ReportedCompatibilityStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.utils.identifiers import generate_id


BANNED_INSECURE_ALGORITHMS = {
    "DES", "DES-56", "3DES", "TRIPLEDES", "RC4", "RC4-128", "ARCFOUR",
    "MD5", "SHA-1", "SHA1", "ROT-13", "ROT13", "PLAINTEXT", "NONE", "NULL",
    "RSA-512", "RSA-1024"
}

ROLE_KEY_EXCHANGE = {
    "TLS_TERMINATION", "KEY_EXCHANGE", "DATA_ENCRYPTION_IN_TRANSIT", "DATA_ENCRYPTION_AT_REST"
}
ROLE_SIGNATURE = {
    "DIGITAL_SIGNATURE", "AUTHENTICATION_TOKEN", "CERTIFICATE_ISSUANCE"
}

PURE_SIGNATURE_ALGORITHMS = {
    "ML-DSA", "ML-DSA-44", "ML-DSA-65", "ML-DSA-87", "SLH-DSA",
    "SLH-DSA-SHA2-128S", "SLH-DSA-SHAKE-128S", "ECDSA", "ED25519", "RSA-PSS"
}
PURE_KEM_ALGORITHMS = {
    "ML-KEM", "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024", "KYBER", "KYBER-768", "X25519"
}

ALGORITHM_ALIASES = {
    "KYBER-512": "ML-KEM-512",
    "KYBER-768": "ML-KEM-768",
    "KYBER-1024": "ML-KEM-1024",
    "DILITHIUM-2": "ML-DSA-44",
    "DILITHIUM-3": "ML-DSA-65",
    "DILITHIUM-5": "ML-DSA-87",
}


def _normalize_algo(name: Optional[str]) -> str:
    if not name:
        return ""
    norm = name.strip().upper().replace("_", "-")
    return ALGORITHM_ALIASES.get(norm, norm)


@dataclass(frozen=True)
class CompatibilityGradingResult:
    """Outcome of grading the compatibility reasoning dimension."""

    dimension_name: str
    raw_score: float
    max_score: float
    normalized_score: float
    passed: bool
    correct_assessments: dict[str, str]
    incorrect_assessments: dict[str, dict[str, str]]
    unknown_assumed_supported: list[str]
    unsupported_assumed_supported: list[str]
    deductions: list[tuple[float, str]]
    violations: list[CriticalViolation]
    details: dict[str, Any]


class CompatibilityGrader:
    """Grades model's compatibility determinations against ground-truth scenario facts."""

    def __init__(self, max_score: float = 20.0) -> None:
        self.max_score = max_score

    def grade(
        self,
        contract: Optional[ModelResponseContract],
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
    ) -> CompatibilityGradingResult:
        """Evaluate compatibility accuracy with strict enforcement of Rule D and cryptographic policy."""
        if not contract:
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description="Cannot evaluate compatibility from malformed or unparseable response.",
                severity=ViolationSeverity.CRITICAL,
                evidence="Parsed contract is None.",
            )
            return CompatibilityGradingResult(
                dimension_name="compatibility_reasoning",
                raw_score=0.0,
                max_score=self.max_score,
                normalized_score=0.0,
                passed=False,
                correct_assessments={},
                incorrect_assessments={},
                unknown_assumed_supported=[],
                unsupported_assumed_supported=[],
                deductions=[
                    (self.max_score, "Malformed response prevents compatibility evaluation.")
                ],
                violations=[viol],
                details={"error": "Malformed response"},
            )

        # Expected scenario facts
        expected_records = {c.component_id: c for c in scenario.compatibility_records}
        expected_status: dict[str, str] = {
            c.component_id: c.status.value for c in scenario.compatibility_records
        }
        system_components = {c.component_id: c for c in scenario.system_components}

        # Reported assessments map
        reported_ca_map = {ca.component_id: ca for ca in contract.compatibility_assessments}
        reported_status: dict[str, str] = {
            ca.component_id: ca.status.value for ca in contract.compatibility_assessments
        }

        correct: dict[str, str] = {}
        incorrect: dict[str, dict[str, str]] = {}
        unknown_assumed_supported: list[str] = []
        unsupported_assumed_supported: list[str] = []

        deductions: list[tuple[float, str]] = []
        violations: list[CriticalViolation] = []

        total_components = len(expected_status)
        if total_components == 0:
            return CompatibilityGradingResult(
                dimension_name="compatibility_reasoning",
                raw_score=self.max_score,
                max_score=self.max_score,
                normalized_score=1.0,
                passed=True,
                correct_assessments={},
                incorrect_assessments={},
                unknown_assumed_supported=[],
                unsupported_assumed_supported=[],
                deductions=[],
                violations=[],
                details={"status": "No components in scenario."},
            )

        pts_per_comp = self.max_score / total_components
        accumulated_score = 0.0

        for cid, exp_stat in expected_status.items():
            ca = reported_ca_map.get(cid)
            if not ca:
                incorrect[cid] = {"expected": exp_stat, "reported": "MISSING"}
                deductions.append(
                    (
                        pts_per_comp,
                        f"Omitted compatibility assessment for '{cid}' (expected {exp_stat}).",
                    )
                )
                continue

            rep_stat = ca.status.value
            target_algo_raw = getattr(ca, "target_algorithm", None)
            target_algo_norm = _normalize_algo(target_algo_raw)

            # Component details from scenario
            scen_rec = expected_records.get(cid)
            comp_obj = system_components.get(cid)
            comp_role = ""
            if comp_obj and getattr(comp_obj, "cryptographic_role", None):
                comp_role = (
                    comp_obj.cryptographic_role.value
                    if hasattr(comp_obj.cryptographic_role, "value")
                    else str(comp_obj.cryptographic_role)
                ).upper()

            # -----------------------------------------------------------------
            # 1. Cryptographic Policy & Target Algorithm Validation
            # -----------------------------------------------------------------
            has_algo_violation = False

            if rep_stat == ReportedCompatibilityStatus.SUPPORTED.value and target_algo_raw:
                # Check for Deprecated, Insecure, or Plaintext Ciphers
                is_insecure = (
                    target_algo_norm in BANNED_INSECURE_ALGORITHMS
                    or any(bad in target_algo_norm for bad in ["DES", "ROT-13", "PLAINTEXT", "RC4"])
                )
                if is_insecure:
                    has_algo_violation = True
                    ded = VIOLATIONS["VIO_UNSUPPORTED_COMPONENT_SCHEDULED"].score_deduction
                    deductions.append(
                        (
                            ded,
                            f"Proposed insecure/prohibited algorithm '{target_algo_raw}' for component '{cid}'.",
                        )
                    )
                    violations.append(
                        CriticalViolation(
                            violation_id=generate_id("viol", "VIO_UNSUPPORTED_COMPONENT_SCHEDULED"),
                            rule_name="VIO_UNSUPPORTED_COMPONENT_SCHEDULED",
                            description=f"Model proposed deprecated, insecure, or plaintext algorithm '{target_algo_raw}' for component '{cid}'.",
                            severity=ViolationSeverity.CRITICAL,
                            evidence=f"Component: {cid}, Proposed: {target_algo_raw}",
                        )
                    )

            # -----------------------------------------------------------------
            # 2. Compatibility Status Alignment
            # -----------------------------------------------------------------
            if rep_stat == exp_stat and not has_algo_violation:
                correct[cid] = exp_stat
                accumulated_score += pts_per_comp
            else:
                incorrect[cid] = {"expected": exp_stat, "reported": rep_stat}

                # Rule D: UNKNOWN assumed SUPPORTED
                if (
                    exp_stat == CompatibilityStatus.UNKNOWN.value
                    and rep_stat == ReportedCompatibilityStatus.SUPPORTED.value
                ):
                    unknown_assumed_supported.append(cid)
                    ded = VIOLATIONS["VIO_UNKNOWN_ASSUMED_SUPPORTED"].score_deduction
                    deductions.append(
                        (ded, f"Falsely assumed UNKNOWN component '{cid}' is SUPPORTED.")
                    )
                    violations.append(
                        CriticalViolation(
                            violation_id=generate_id("viol", "VIO_UNKNOWN_ASSUMED_SUPPORTED"),
                            rule_name="VIO_UNKNOWN_ASSUMED_SUPPORTED",
                            description=f"Model certified UNKNOWN component '{cid}' as SUPPORTED without verified evidence.",
                            severity=ViolationSeverity.CRITICAL,
                            evidence=f"Component: {cid}, Expected: UNKNOWN, Reported: SUPPORTED",
                        )
                    )

                # UNSUPPORTED assumed SUPPORTED
                elif (
                    exp_stat == CompatibilityStatus.UNSUPPORTED.value
                    and rep_stat == ReportedCompatibilityStatus.SUPPORTED.value
                ):
                    unsupported_assumed_supported.append(cid)
                    ded = VIOLATIONS["VIO_UNSUPPORTED_COMPONENT_SCHEDULED"].score_deduction
                    deductions.append(
                        (ded, f"Falsely claimed UNSUPPORTED component '{cid}' is SUPPORTED.")
                    )
                    violations.append(
                        CriticalViolation(
                            violation_id=generate_id("viol", "VIO_UNSUPPORTED_COMPONENT_SCHEDULED"),
                            rule_name="VIO_UNSUPPORTED_COMPONENT_SCHEDULED",
                            description=f"Model incorrectly assessed known UNSUPPORTED component '{cid}' as SUPPORTED.",
                            severity=ViolationSeverity.CRITICAL,
                            evidence=f"Component: {cid}, Expected: UNSUPPORTED, Reported: SUPPORTED",
                        )
                    )
                elif not has_algo_violation:
                    deductions.append(
                        (
                            pts_per_comp,
                            f"Mismatched compatibility for '{cid}': expected {exp_stat}, got {rep_stat}.",
                        )
                    )

        # Check if model reported unknown component IDs
        invented_cids = set(reported_status.keys()) - set(expected_status.keys())
        if invented_cids:
            ded = min(len(invented_cids) * 2.0, 6.0)
            deductions.append(
                (
                    ded,
                    f"Assessed {len(invented_cids)} non-existent component(s): {sorted(invented_cids)[:3]}.",
                )
            )

        total_deduction = sum(d[0] for d in deductions)
        final_score = max(
            0.0, round(accumulated_score - (total_deduction - (len(incorrect) * pts_per_comp)), 2)
        )
        final_score = min(self.max_score, final_score)
        normalized = round(final_score / self.max_score, 4)

        has_critical = any(v.severity == ViolationSeverity.CRITICAL for v in violations)

        return CompatibilityGradingResult(
            dimension_name="compatibility_reasoning",
            raw_score=final_score,
            max_score=self.max_score,
            normalized_score=normalized,
            passed=final_score >= (self.max_score * 0.70)
            and len(unknown_assumed_supported) == 0
            and len(unsupported_assumed_supported) == 0
            and not has_critical,
            correct_assessments=correct,
            incorrect_assessments=incorrect,
            unknown_assumed_supported=unknown_assumed_supported,
            unsupported_assumed_supported=unsupported_assumed_supported,
            deductions=deductions,
            violations=violations,
            details={
                "accuracy": round(len(correct) / total_components, 4),
                "total_expected": total_components,
                "correct_count": len(correct),
                "incorrect_count": len(incorrect),
                "has_critical_algorithm_violation": has_critical,
            },
        )
