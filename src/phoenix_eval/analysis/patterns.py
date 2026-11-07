"""Failure pattern detector with evidence-based scope thresholding for PHOENIX-EVAL Phase 5.

Identifies single-occurrence, task-repeated, cross-task recurring, and cross-domain recurring
failure patterns grounded in deterministic evaluator violation traces.
"""

from collections import defaultdict
from typing import Optional

from phoenix_eval.analysis.ingestion import ValidatedExperimentData
from phoenix_eval.analysis.performance import BenchmarkPerformanceAnalyzer
from phoenix_eval.analysis.schemas import (
    FailureIncident,
    FailurePattern,
    FailurePatternScope,
)
from phoenix_eval.core.logging import get_logger
from phoenix_eval.utils.identifiers import generate_id

logger = get_logger("analysis.patterns")

SUGGESTED_INTERPRETATIONS: dict[str, str] = {
    "VIO_MALFORMED_RESPONSE": (
        "Model systematically breaches JSON syntax or strict response contract schema specifications."
    ),
    "VIO_KNOWN_DEPENDENCY_OMITTED": (
        "Model routinely omits prerequisite upstream/downstream dependencies from the migration sequence."
    ),
    "VIO_DEPENDENCY_ORDER_REVERSED": (
        "Model orders dependents before dependencies, creating service interruption or breaking cutovers."
    ),
    "VIO_CYCLE_IGNORED": (
        "Model attempts linear topological ordering over circular dependency graphs without resolution."
    ),
    "VIO_INVENTED_DEPENDENCY": (
        "Model hallucinates non-existent architectural dependencies not present in ground-truth telemetry."
    ),
    "VIO_UNKNOWN_ASSUMED_SUPPORTED": (
        "Model assumes unverified cryptographic provider support in the absence of explicit compatibility evidence."
    ),
    "VIO_UNSUPPORTED_COMPONENT_SCHEDULED": (
        "Model schedules migration cutover for components with known architectural incompatibilities."
    ),
    "VIO_UNSUPPORTED_CUTOVER": (
        "Model executes premature cutover without establishing backward compatibility or dual-stack readiness."
    ),
    "VIO_UNSUPPORTED_EVIDENCE_CLAIM": (
        "Model cites non-existent test evidence, log entries, or certification artifacts."
    ),
    "VIO_INVALID_EVIDENCE_REFERENCE": (
        "Model references invalid or hallucinated artifact identifiers to justify readiness."
    ),
    "VIO_FALSE_VERIFICATION_CLAIM": (
        "Model asserts verification completion despite failing or missing verification telemetry."
    ),
    "VIO_REQUIRED_TEST_MISSING": (
        "Model bypasses mandatory pre-migration or post-cutover verification test suites."
    ),
    "VIO_PENDING_TEST_CERTIFIED": (
        "Model prematurely certifies pending, in-flight, or incomplete verification tests."
    ),
    "VIO_CONTRADICTORY_DECISION": (
        "Model produces contradictory migration decisions (e.g. declaring safe readiness while logging fatal blockers)."
    ),
    "VIO_CONSTRAINT_VIOLATION": (
        "Model violates explicit operational, regulatory, or zero-downtime migration constraints."
    ),
}


class FailurePatternDetector:
    """Detects recurring failure patterns with scientific thresholding rules."""

    def __init__(self, analyzer: Optional[BenchmarkPerformanceAnalyzer] = None) -> None:
        self.analyzer = analyzer or BenchmarkPerformanceAnalyzer()

    def detect_patterns(
        self,
        incidents: list[FailureIncident],
        validated_data: ValidatedExperimentData,
    ) -> list[FailurePattern]:
        """Detect and classify recurring failure patterns across all models.

        Thresholding criteria:
        - SINGLE_OCCURRENCE: count == 1 run
        - TASK_REPEATED: same model & same task across >= 2 runs (trials)
        - CROSS_TASK_RECURRING: same model across >= 2 distinct tasks
        - CROSS_DOMAIN_RECURRING: same model across >= 2 distinct enterprise domains
        """
        # Group incidents by (model_identifier, violation_code)
        grouped: dict[tuple[str, str], list[FailureIncident]] = defaultdict(list)
        for inc in incidents:
            grouped[(inc.model_identifier, inc.violation_code)].append(inc)

        patterns: list[FailurePattern] = []

        for (model_id, code), inc_list in sorted(
            grouped.items(), key=lambda kv: len(kv[1]), reverse=True
        ):
            primary_inc = inc_list[0]
            cat = primary_inc.category
            sev = primary_inc.severity

            run_ids = sorted({inc.run_id for inc in inc_list})
            task_ids = sorted({inc.task_id for inc in inc_list})

            # Resolve domains for each task
            domains = {self.analyzer._resolve_task_domain(t) for t in task_ids}

            num_runs = len(run_ids)
            num_tasks = len(task_ids)
            num_domains = len(domains)

            # Determine scope
            if num_domains >= 2:
                scope = FailurePatternScope.CROSS_DOMAIN_RECURRING
            elif num_tasks >= 2:
                scope = FailurePatternScope.CROSS_TASK_RECURRING
            elif num_runs >= 2:
                scope = FailurePatternScope.TASK_REPEATED
            else:
                scope = FailurePatternScope.SINGLE_OCCURRENCE

            # Confidence increases with sample evidence
            if scope == FailurePatternScope.SINGLE_OCCURRENCE:
                confidence = 0.50
            elif scope == FailurePatternScope.TASK_REPEATED:
                confidence = min(0.95, 0.65 + 0.05 * num_runs)
            elif scope == FailurePatternScope.CROSS_TASK_RECURRING:
                confidence = min(0.98, 0.75 + 0.05 * num_tasks)
            else:
                confidence = min(1.0, 0.85 + 0.03 * num_domains)

            name = f"{primary_inc.violation_name} ({scope.value})"
            description = (
                f"Model '{model_id}' demonstrated {code} across {num_runs} run(s) "
                f"spanning {num_tasks} task(s) and {num_domains} domain(s)."
            )

            interp = SUGGESTED_INTERPRETATIONS.get(
                code, f"Recurring {cat.value} reasoning failure under {code}."
            )

            patterns.append(
                FailurePattern(
                    pattern_id=generate_id("patt"),
                    pattern_name=name,
                    description=description,
                    model_identifier=model_id,
                    category=cat,
                    scope=scope,
                    severity=sev,
                    confidence=round(confidence, 4),
                    supporting_run_ids=run_ids,
                    supporting_task_ids=task_ids,
                    supporting_violation_codes=[code],
                    number_of_affected_runs=num_runs,
                    number_of_affected_trials=num_runs,
                    relevant_dimension=cat.value.lower(),
                    suggested_interpretation=interp,
                )
            )

        return patterns
