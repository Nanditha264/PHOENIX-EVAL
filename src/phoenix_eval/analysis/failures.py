"""Structured failure intelligence engine and taxonomy for PHOENIX-EVAL Phase 5.

Extracts deterministic failure incidents from evaluation reports, categorizes them
into the six authoritative failure modes (+ parsing), builds failure frequency matrices,
and isolates safety-critical failure manifestations.
"""

from collections import defaultdict
from typing import Any

from phoenix_eval.analysis.ingestion import ValidatedExperimentData
from phoenix_eval.analysis.schemas import (
    FailureCategory,
    FailureIncident,
    FailureSeverity,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.utils.identifiers import generate_id

logger = get_logger("analysis.failures")

VIOLATION_TAXONOMY_MAP: dict[str, FailureCategory] = {
    # Dependency
    "VIO_CIRCULAR_DEPENDENCY_DEADLOCK": FailureCategory.DEPENDENCY,
    "VIO_CYCLE_IGNORED": FailureCategory.DEPENDENCY,
    "VIO_DEPENDENCY_BLOCKER_IGNORED": FailureCategory.DEPENDENCY,
    "VIO_INVENTED_DEPENDENCY": FailureCategory.DEPENDENCY,
    "VIO_KNOWN_DEPENDENCY_OMITTED": FailureCategory.DEPENDENCY,
    "VIO_DIRECT_DEP_OMITTED": FailureCategory.DEPENDENCY,
    "VIO_INDIRECT_DEP_OMITTED": FailureCategory.DEPENDENCY,
    # Compatibility
    "VIO_UNKNOWN_ASSUMED_SUPPORTED": FailureCategory.COMPATIBILITY,
    "VIO_UNKNOWN_COMPATIBILITY_UNCHECKED": FailureCategory.COMPATIBILITY,
    "VIO_UNSUPPORTED_COMPONENT_SCHEDULED": FailureCategory.COMPATIBILITY,
    "VIO_UNSUPPORTED_CUTOVER": FailureCategory.COMPATIBILITY,
    "VIO_BACKWARD_COMPATIBILITY_VIOLATION": FailureCategory.COMPATIBILITY,
    # Evidence
    "VIO_UNSUPPORTED_EVIDENCE_CLAIM": FailureCategory.EVIDENCE,
    "VIO_INVALID_EVIDENCE_REFERENCE": FailureCategory.EVIDENCE,
    "VIO_MISSING_EVIDENCE": FailureCategory.EVIDENCE,
    "VIO_FAILED_TEST_IGNORED": FailureCategory.EVIDENCE,
    "VIO_STALE_EVIDENCE_RELIED_UPON": FailureCategory.EVIDENCE,
    # Safety
    "VIO_FALSE_VERIFICATION_CLAIM": FailureCategory.SAFETY,
    "VIO_REQUIRED_TEST_MISSING": FailureCategory.SAFETY,
    "VIO_PENDING_TEST_CERTIFIED": FailureCategory.SAFETY,
    "VIO_REGULATORY_VIOLATION": FailureCategory.SAFETY,
    "VIO_CAPACITY_LIMIT_EXCEEDED": FailureCategory.SAFETY,
    "VIO_HARDWARE_LIMIT_EXCEEDED": FailureCategory.SAFETY,
    "VIO_ROLLBACK_REQUIRED_MISSING": FailureCategory.SAFETY,
    "VIO_NO_DOWNTIME_VIOLATION": FailureCategory.SAFETY,
    "VIO_CONSTRAINT_VIOLATION": FailureCategory.SAFETY,
    "VIO_UNSAFE_BLOCKED_PLAN": FailureCategory.SAFETY,
    "VIO_CONDITIONAL_CUTOVER_VIOLATION": FailureCategory.SAFETY,
    "VIO_EXPLANATION_CONTRADICTION": FailureCategory.SAFETY,
    # Planning
    "VIO_DEPENDENCY_ORDER_REVERSED": FailureCategory.PLANNING,
    "VIO_INVALID_PRECONDITION": FailureCategory.PLANNING,
    "VIO_MISSING_PREPARATION": FailureCategory.PLANNING,
    "VIO_INVALID_STEP_ORDER": FailureCategory.PLANNING,
    "VIO_DUPLICATE_MIGRATION_STEP": FailureCategory.PLANNING,
    # Uncertainty
    "VIO_CONTRADICTORY_DECISION": FailureCategory.UNCERTAINTY,
    "VIO_UNNECESSARY_BLOCKING": FailureCategory.UNCERTAINTY,
    "VIO_CONTRADICTORY_TEST_RESULTS": FailureCategory.UNCERTAINTY,
    # Parsing
    "VIO_MALFORMED_RESPONSE": FailureCategory.PARSING,
}


class FailureIntelligenceEngine:
    """Extracts, categorizes, and aggregates failure incidents across evaluated models."""

    def categorize_violation(self, violation_code: str) -> FailureCategory:
        """Map a violation code to the authoritative failure taxonomy.

        Strictly returns FailureCategory.UNCLASSIFIED for unmapped violation codes.
        Never guesses via heuristics or falls back to SAFETY.
        """
        code_upper = violation_code.upper().strip()
        if code_upper in VIOLATION_TAXONOMY_MAP:
            return VIOLATION_TAXONOMY_MAP[code_upper]

        logger.warning("Unmapped violation code '%s' assigned to UNCLASSIFIED", violation_code)
        return FailureCategory.UNCLASSIFIED

    def extract_incidents(
        self,
        validated_data: ValidatedExperimentData,
    ) -> list[FailureIncident]:
        """Extract deduplicated FailureIncident records from all evaluated runs in the experiment.

        Inspects both critical safety violations and high-severity non-critical reasoning violations.
        """
        incidents: list[FailureIncident] = []

        for record in validated_data.valid_runs:
            run_id = record.run_id
            task_id = record.task_id
            model_id = record.model_identifier
            report = validated_data.evaluation_reports.get(run_id)
            if not report:
                continue

            seen_in_run: set[str] = set()

            all_violation_items: list[tuple[Any, str]] = []
            for item in report.critical_violations:
                all_violation_items.append((item, "CRITICAL"))
            for item in report.non_critical_violations:
                all_violation_items.append((item, "MAJOR"))

            for item, default_sev in all_violation_items:
                rn = (
                    item.get("rule_name")
                    if isinstance(item, dict)
                    else getattr(item, "rule_name", "")
                )
                sev_str = (
                    item.get("severity")
                    if isinstance(item, dict)
                    else getattr(item, "severity", default_sev)
                )
                desc = (
                    item.get("description")
                    if isinstance(item, dict)
                    else getattr(item, "description", "")
                )
                evi = (
                    item.get("evidence")
                    if isinstance(item, dict)
                    else getattr(item, "evidence", "")
                )

                code = str(rn).strip()
                if not code:
                    continue

                # Deduplicate identical violation codes within the same run
                if code in seen_in_run:
                    continue
                seen_in_run.add(code)

                category = self.categorize_violation(code)

                try:
                    severity = FailureSeverity(str(sev_str).upper())
                except ValueError:
                    severity = (
                        FailureSeverity.CRITICAL
                        if default_sev == "CRITICAL"
                        else FailureSeverity.MAJOR
                    )

                incident = FailureIncident(
                    incident_id=generate_id("fail"),
                    run_id=run_id,
                    task_id=task_id,
                    model_identifier=model_id,
                    category=category,
                    violation_code=code,
                    violation_name=code.replace("VIO_", "").replace("_", " ").title(),
                    severity=severity,
                    description=str(desc),
                    evidence=str(evi),
                )
                incidents.append(incident)

        return incidents

    def compute_taxonomy_coverage(
        self,
        known_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compute coverage of VIOLATION_TAXONOMY_MAP against known benchmark violation codes."""
        codes = list(VIOLATION_TAXONOMY_MAP.keys()) if known_codes is None else known_codes
        total_codes = len(codes)
        mapped = [c for c in codes if c in VIOLATION_TAXONOMY_MAP]
        unmapped = [c for c in codes if c not in VIOLATION_TAXONOMY_MAP]
        coverage_pct = round((len(mapped) / total_codes * 100.0) if total_codes > 0 else 100.0, 2)

        return {
            "total_codes": total_codes,
            "mapped_codes": len(mapped),
            "unmapped_codes": unmapped,
            "coverage_percentage": coverage_pct,
        }

    def compute_failure_frequency_matrix(
        self,
        incidents: list[FailureIncident],
    ) -> dict[str, dict[str, int]]:
        """Compute a failure frequency matrix mapping model_identifier -> category -> count."""
        matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for inc in incidents:
            matrix[inc.model_identifier][inc.category.value] += 1

        # Convert to normal dict
        return {m: dict(cats) for m, cats in matrix.items()}

    def compute_violation_code_frequencies(
        self,
        incidents: list[FailureIncident],
    ) -> dict[str, int]:
        """Compute frequency distribution of individual violation codes."""
        counts: dict[str, int] = defaultdict(int)
        for inc in incidents:
            counts[inc.violation_code] += 1
        return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))
