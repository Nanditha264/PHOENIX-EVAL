"""Deterministic grading engine for migration plan ordering, causal precedence, and deadlock recognition.

Implements strict validation of all submitted migration steps, distinguishing safe
preparation and discovery actions from production cutover, and removing any refusal bypass.
"""

from dataclasses import dataclass
import re
from typing import Any, Optional

from phoenix_eval.evaluation.independent_graph_verifier import IndependentGraphVerifier
from phoenix_eval.evaluation.violation_catalog import VIOLATIONS
from phoenix_eval.schemas.compatibility import CompatibilityStatus
from phoenix_eval.schemas.evaluation import CriticalViolation, ViolationSeverity
from phoenix_eval.schemas.response_contract import (
    MigrationActionType,
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibilityStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.utils.identifiers import generate_id


@dataclass(frozen=True)
class MigrationPlanGradingResult:
    """Outcome of grading the migration plan ordering dimension."""

    dimension_name: str
    raw_score: float
    max_score: float
    normalized_score: float
    passed: bool
    is_dag: bool
    plan_valid: bool
    causal_violations: list[tuple[str, str, int, int]]
    unsupported_scheduled: list[str]
    omitted_components: list[str]
    deductions: list[tuple[float, str]]
    violations: list[CriticalViolation]
    details: dict[str, Any]


class MigrationPlanGrader:
    """Grades model's proposed migration waves using independent causal precedence verification."""

    def __init__(self, max_score: float = 20.0) -> None:
        self.max_score = max_score

    def grade(
        self,
        contract: Optional[ModelResponseContract],
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
    ) -> MigrationPlanGradingResult:
        """Validate migration wave ordering against independent graph verifier without canonical wave bias."""
        if not contract:
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description="Cannot evaluate migration plan from malformed or unparseable response.",
                severity=ViolationSeverity.CRITICAL,
                evidence="Parsed contract is None.",
            )
            return MigrationPlanGradingResult(
                dimension_name="migration_plan_correctness",
                raw_score=0.0,
                max_score=self.max_score,
                normalized_score=0.0,
                passed=False,
                is_dag=False,
                plan_valid=False,
                causal_violations=[],
                unsupported_scheduled=[],
                omitted_components=[],
                deductions=[
                    (self.max_score, "Malformed response prevents migration plan evaluation.")
                ],
                violations=[viol],
                details={"error": "Malformed response"},
            )

        # Independent graph verification
        verifier = IndependentGraphVerifier(scenario)
        is_dag = verifier.is_dag
        cycles = verifier.cycles

        deductions: list[tuple[float, str]] = []
        violations: list[CriticalViolation] = []

        compat_map = {c.component_id: c.status for c in scenario.compatibility_records}
        unsupported_cids = {
            cid for cid, stat in compat_map.items() if stat == CompatibilityStatus.UNSUPPORTED
        }
        unknown_cids = {
            cid for cid, stat in compat_map.items() if stat == CompatibilityStatus.UNKNOWN
        }
        has_failed_tests = any(
            bool(re.search(r'\bSTATUS\s*:\s*(FAILED|FAIL)\b', t.description, re.IGNORECASE))
            for t in scenario.required_tests
        )
        is_missing_test_t07 = (
            len(scenario.required_tests) == 0 and "t07" in scenario.scenario_id.lower()
        )
        scenario_requires_refusal = (
            not is_dag
            or bool(unsupported_cids)
            or bool(unknown_cids)
            or has_failed_tests
            or is_missing_test_t07
        )

        steps = contract.migration_plan
        scenario_comp_ids = {c.component_id for c in scenario.system_components}

        # Case A: Empty Migration Plan
        if len(steps) == 0:
            if scenario_requires_refusal and contract.decision in (
                ModelDecision.MIGRATION_BLOCKED,
                ModelDecision.INSUFFICIENT_INFORMATION,
                ModelDecision.CONDITIONAL,
            ):
                # Valid safe refusal with empty plan
                return MigrationPlanGradingResult(
                    dimension_name="migration_plan_correctness",
                    raw_score=self.max_score,
                    max_score=self.max_score,
                    normalized_score=1.0,
                    passed=True,
                    is_dag=is_dag,
                    plan_valid=True,
                    causal_violations=[],
                    unsupported_scheduled=[],
                    omitted_components=[],
                    deductions=[],
                    violations=[],
                    details={"safe_refusal_recognized": True, "empty_plan_valid": True},
                )
            elif not scenario_requires_refusal:
                # Clean scenario that is migration ready, but model provided zero steps
                deductions.append(
                    (self.max_score, "Omitted migration plan for valid, ready architecture.")
                )
                return MigrationPlanGradingResult(
                    dimension_name="migration_plan_correctness",
                    raw_score=0.0,
                    max_score=self.max_score,
                    normalized_score=0.0,
                    passed=False,
                    is_dag=is_dag,
                    plan_valid=False,
                    causal_violations=[],
                    unsupported_scheduled=[],
                    omitted_components=sorted(scenario_comp_ids),
                    deductions=deductions,
                    violations=[],
                    details={"empty_plan_unjustified": True},
                )
            else:
                # Scenario required refusal, but decision was MIGRATION_READY with empty plan
                deductions.append(
                    (
                        self.max_score,
                        "Declared MIGRATION_READY with empty plan on blocked scenario.",
                    )
                )
                return MigrationPlanGradingResult(
                    dimension_name="migration_plan_correctness",
                    raw_score=0.0,
                    max_score=self.max_score,
                    normalized_score=0.0,
                    passed=False,
                    is_dag=is_dag,
                    plan_valid=False,
                    causal_violations=[],
                    unsupported_scheduled=[],
                    omitted_components=sorted(scenario_comp_ids),
                    deductions=deductions,
                    violations=[],
                    details={"empty_plan_contradictory": True},
                )

        # Case B: Non-Empty Migration Plan -> ALWAYS INSPECT EVERY SUBMITTED STEP
        # Categorize steps by action type
        cutover_steps = [
            s
            for s in steps
            if getattr(s, "action_type", MigrationActionType.PRODUCTION_CUTOVER)
            == MigrationActionType.PRODUCTION_CUTOVER
        ]
        prep_steps = [
            s
            for s in steps
            if getattr(s, "action_type", MigrationActionType.PRODUCTION_CUTOVER)
            in (
                MigrationActionType.DISCOVERY,
                MigrationActionType.PREPARATION,
                MigrationActionType.STAGING,
                MigrationActionType.VALIDATION,
                MigrationActionType.ROLLBACK,
            )
        ]

        # 1. Cyclic Graph Checks
        if not is_dag:
            # Any PRODUCTION_CUTOVER on cyclic components is forbidden
            cycle_nodes = {node for cycle in cycles for node in cycle}
            cyclic_cutovers = [
                s.component_id for s in cutover_steps if s.component_id in cycle_nodes
            ]
            if cyclic_cutovers or contract.decision == ModelDecision.MIGRATION_READY:
                ded = VIOLATIONS["VIO_CYCLE_IGNORED"].score_deduction
                deductions.append(
                    (
                        self.max_score,
                        f"Proposed linear cutover {cyclic_cutovers} over circular dependency cycle(s) {cycles}.",
                    )
                )
                violations.append(
                    CriticalViolation(
                        violation_id=generate_id("viol", "VIO_CYCLE_IGNORED"),
                        rule_name="VIO_CYCLE_IGNORED",
                        description=f"Model proposed a linear production cutover over cyclic graph with cycle(s) {cycles}.",
                        severity=ViolationSeverity.CRITICAL,
                        evidence=f"Cycles: {cycles}, Prohibited cutovers: {cyclic_cutovers}",
                    )
                )
            elif len(cutover_steps) > 0:
                # Cutting over components on a cyclic graph
                deductions.append(
                    (
                        10.0,
                        f"Proposed production cutover on cyclic system: {[s.component_id for s in cutover_steps]}.",
                    )
                )

        # 2. Check for UNSUPPORTED and UNKNOWN components in PRODUCTION_CUTOVER
        cutover_cids = {s.component_id for s in cutover_steps}
        reported_unknown_cids = {
            ca.component_id
            for ca in contract.compatibility_assessments
            if ca.status == ReportedCompatibilityStatus.UNKNOWN
        }
        unsupported_cutover = sorted(cutover_cids & unsupported_cids)
        unknown_cutover = sorted(cutover_cids & (unknown_cids | reported_unknown_cids))

        if unsupported_cutover:
            ded = VIOLATIONS["VIO_UNSUPPORTED_COMPONENT_SCHEDULED"].score_deduction
            deductions.append(
                (
                    ded,
                    f"Scheduled {len(unsupported_cutover)} known UNSUPPORTED component(s) for production cutover: {unsupported_cutover}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_UNSUPPORTED_COMPONENT_SCHEDULED"),
                    rule_name="VIO_UNSUPPORTED_COMPONENT_SCHEDULED",
                    description=f"Model scheduled known UNSUPPORTED components {unsupported_cutover} for production cutover.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Unsupported components: {unsupported_cutover}",
                )
            )

        if unknown_cutover:
            ded = VIOLATIONS["VIO_UNKNOWN_ASSUMED_SUPPORTED"].score_deduction
            deductions.append(
                (
                    ded,
                    f"Scheduled {len(unknown_cutover)} UNKNOWN component(s) for production cutover: {unknown_cutover}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_UNKNOWN_ASSUMED_SUPPORTED"),
                    rule_name="VIO_UNKNOWN_ASSUMED_SUPPORTED",
                    description=f"Model scheduled UNKNOWN components {unknown_cutover} for production cutover without verified support.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Unknown components: {unknown_cutover}",
                )
            )

        # Exploit Resistance A: Declaring MIGRATION_BLOCKED or INSUFFICIENT_INFORMATION but scheduling PRODUCTION_CUTOVER
        if (
            contract.decision
            in (
                ModelDecision.MIGRATION_BLOCKED,
                ModelDecision.INSUFFICIENT_INFORMATION,
            )
            and len(cutover_steps) > 0
        ):
            ded = VIOLATIONS["VIO_UNSAFE_BLOCKED_PLAN"].score_deduction
            deductions.append(
                (
                    self.max_score,
                    f"Model declared {contract.decision.value} but submitted a plan scheduling production cutovers: {[s.component_id for s in cutover_steps]}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_UNSAFE_BLOCKED_PLAN"),
                    rule_name="VIO_UNSAFE_BLOCKED_PLAN",
                    description=f"Model declared {contract.decision.value} but scheduled {len(cutover_steps)} component(s) for PRODUCTION_CUTOVER.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Decision: {contract.decision.value}, Cutover components: {[s.component_id for s in cutover_steps]}",
                )
            )

        # Exploit Resistance B: Declaring CONDITIONAL while scheduling cutover of UNSUPPORTED components
        if contract.decision == ModelDecision.CONDITIONAL and len(cutover_steps) > 0:
            unsupported_in_conditional = [
                s.component_id for s in cutover_steps if s.component_id in unsupported_cids
            ]
            if unsupported_in_conditional:
                ded = VIOLATIONS["VIO_CONDITIONAL_CUTOVER_VIOLATION"].score_deduction
                deductions.append(
                    (
                        ded,
                        f"Model declared CONDITIONAL readiness but scheduled production cutover for UNSUPPORTED component(s): {unsupported_in_conditional}.",
                    )
                )
                violations.append(
                    CriticalViolation(
                        violation_id=generate_id("viol", "VIO_CONDITIONAL_CUTOVER_VIOLATION"),
                        rule_name="VIO_CONDITIONAL_CUTOVER_VIOLATION",
                        description=f"Model declared CONDITIONAL readiness while scheduling cutovers for known UNSUPPORTED components: {unsupported_in_conditional}.",
                        severity=ViolationSeverity.CRITICAL,
                        evidence=f"Unsupported cutovers in conditional plan: {unsupported_in_conditional}",
                    )
                )

        # 3. Check Causal Dependency Ordering on Cutover Steps
        causal_violations: list[tuple[str, str, int, int]] = []
        cutover_wave_map: dict[str, int] = {}
        for s in cutover_steps:
            cutover_wave_map[s.component_id] = s.wave

        for caller, prereq_set in verifier.prereqs.items():
            if caller not in cutover_wave_map:
                continue
            caller_wave = cutover_wave_map[caller]
            for prereq in prereq_set:
                if prereq in cutover_wave_map:
                    prereq_wave = cutover_wave_map[prereq]
                    if prereq_wave >= caller_wave:
                        causal_violations.append((caller, prereq, caller_wave, prereq_wave))
                elif contract.decision == ModelDecision.MIGRATION_READY:
                    # Prerequisite was never cutover in full migration plan
                    causal_violations.append((caller, prereq, caller_wave, -1))

        # Check Transitive Causal Ordering on Cutover Steps
        for caller, trans_set in verifier.transitive_prereqs.items():
            if caller not in cutover_wave_map:
                continue
            caller_wave = cutover_wave_map[caller]
            for prereq in trans_set:
                if prereq in cutover_wave_map:
                    prereq_wave = cutover_wave_map[prereq]
                    if prereq_wave >= caller_wave:
                        viol = (caller, prereq, caller_wave, prereq_wave)
                        if viol not in causal_violations:
                            causal_violations.append(viol)

        if causal_violations:
            ded = VIOLATIONS["VIO_DEPENDENCY_ORDER_REVERSED"].score_deduction
            deductions.append(
                (
                    ded,
                    f"{len(causal_violations)} causal wave ordering violations (e.g. {causal_violations[0]}).",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_DEPENDENCY_ORDER_REVERSED"),
                    rule_name="VIO_DEPENDENCY_ORDER_REVERSED",
                    description="Model scheduled caller component before or in the same wave as its prerequisite cutover.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Causal violations: {causal_violations}",
                )
            )

        # 4. Check Unknown and Duplicated Components
        unknown_comps = [s.component_id for s in steps if s.component_id not in scenario_comp_ids]
        if unknown_comps:
            ded = VIOLATIONS["VIO_MALFORMED_RESPONSE"].score_deduction
            deductions.append((ded, f"Included non-existent components in plan: {unknown_comps}."))
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                    rule_name="VIO_MALFORMED_RESPONSE",
                    description=f"Model scheduled non-existent phantom component IDs in migration plan: {unknown_comps}.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Unknown component IDs: {unknown_comps}",
                )
            )

        seen_cutover: set[str] = set()
        duplicated_cutover: list[str] = []
        for s in cutover_steps:
            if s.component_id in seen_cutover:
                duplicated_cutover.append(s.component_id)
            seen_cutover.add(s.component_id)
        if duplicated_cutover:
            ded = VIOLATIONS["VIO_DUPLICATE_MIGRATION_STEP"].score_deduction
            deductions.append(
                (
                    ded,
                    f"Duplicated components across multiple cutover waves: {duplicated_cutover}.",
                )
            )
            violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_DUPLICATE_MIGRATION_STEP"),
                    rule_name="VIO_DUPLICATE_MIGRATION_STEP",
                    description=f"Model scheduled duplicate cutover steps for component(s): {duplicated_cutover}.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Duplicates: {duplicated_cutover}",
                )
            )

        # 5. Check Omitted Components for MIGRATION_READY
        omitted: list[str] = []
        if contract.decision == ModelDecision.MIGRATION_READY:
            omitted = sorted(scenario_comp_ids - cutover_cids)
            if omitted:
                ded = min(len(omitted) * 2.0, 6.0)
                deductions.append(
                    (
                        ded,
                        f"Omitted {len(omitted)} component(s) from migration plan: {omitted[:3]}.",
                    )
                )

        # Safe preparatory response check:
        # If all steps are preparatory/discovery and decision is CONDITIONAL or MIGRATION_BLOCKED, no cutover violations exist.
        only_safe_prep = len(cutover_steps) == 0 and len(prep_steps) > 0
        if only_safe_prep and contract.decision in (
            ModelDecision.CONDITIONAL,
            ModelDecision.MIGRATION_BLOCKED,
            ModelDecision.INSUFFICIENT_INFORMATION,
        ):
            # All actions are safe preparation/discovery
            deductions = [d for d in deductions if "Omitted" not in d[1]]

        total_deduction = sum(d[0] for d in deductions)
        final_score = max(0.0, round(self.max_score - total_deduction, 2))
        normalized = round(final_score / self.max_score, 4)

        has_critical_plan_violation = (
            len(violations) > 0
            or len(unsupported_cutover) > 0
            or len(unknown_cutover) > 0
            or len(causal_violations) > 0
        )

        return MigrationPlanGradingResult(
            dimension_name="migration_plan_correctness",
            raw_score=final_score,
            max_score=self.max_score,
            normalized_score=normalized,
            passed=final_score >= (self.max_score * 0.70) and not has_critical_plan_violation,
            is_dag=is_dag,
            plan_valid=not has_critical_plan_violation,
            causal_violations=causal_violations,
            unsupported_scheduled=unsupported_cutover,
            omitted_components=omitted,
            deductions=deductions,
            violations=violations,
            details={
                "step_count": len(steps),
                "cutover_step_count": len(cutover_steps),
                "prep_step_count": len(prep_steps),
                "causal_violation_count": len(causal_violations),
                "unsupported_cutover_count": len(unsupported_cutover),
                "unknown_cutover_count": len(unknown_cutover),
                "omitted_count": len(omitted),
            },
        )
