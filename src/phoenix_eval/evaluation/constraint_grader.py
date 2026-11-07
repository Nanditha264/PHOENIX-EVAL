"""Deterministic grading engine for operational and architectural migration constraints.

Evaluates scenario.migration_constraints against model responses and ReportedMigrationStep.preconditions.
Covers:
    - ORDERING: Causal precedence and precondition verification.
    - NO_DOWNTIME: Continuous availability, zero breaking cutovers, dual-stack/zero-downtime declarations.
    - BACKWARD_COMPATIBILITY: Dual-stack fallback support during transitional waves.
    - HARDWARE_LIMIT: Preservation of hardware boundaries, firmware verification, capacity limits.
    - REGULATORY_COMPLIANCE: Standards adherence (e.g. FIPS 203/204), avoidance of deprecated ciphers.
    - ROLLBACK_CAPABILITY: Verified rollback and automated fallback procedures.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from phoenix_eval.schemas.evaluation import CriticalViolation, ViolationSeverity
from phoenix_eval.schemas.response_contract import (
    MigrationActionType,
    ModelDecision,
    ModelResponseContract,
    ReportedTestStatus,
)
from phoenix_eval.schemas.scenarios import ConstraintType, ScenarioModel
from phoenix_eval.utils.identifiers import generate_id


class ConstraintStatus(str, Enum):
    """Explicit evaluation status for a migration constraint."""

    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class PreconditionFinding:
    """Detailed finding for a single step precondition check."""

    step_wave: int
    component_id: str
    precondition_ref: str
    finding_type: str  # "UNKNOWN_ENTITY", "UNSATISFIED_PREREQUISITE", "INCORRECT_WAVE_ORDER", "MISSING_ACTION", "INVALID_GATE", "UNSATISFIED_GATE"
    description: str
    deduction: float


@dataclass(frozen=True)
class ConstraintCheckResult:
    """Outcome of checking a single migration constraint with complete audit telemetry."""

    constraint_id: str
    constraint_type: ConstraintType
    status: ConstraintStatus
    relevant_scenario_facts: dict[str, Any]
    model_response_evidence: dict[str, Any]
    reason: str
    score_impact: float
    safety_impact: str  # "NONE" or "VETO"
    missing_information: Optional[str] = None
    is_critical: bool = False
    violation: Optional[CriticalViolation] = None

    @property
    def passed(self) -> bool:
        """Backward compatibility helper: True only if SATISFIED or NOT_APPLICABLE."""
        return self.status in (ConstraintStatus.SATISFIED, ConstraintStatus.NOT_APPLICABLE)

    @property
    def deduction(self) -> float:
        return self.score_impact


@dataclass(frozen=True)
class ConstraintGradingResult:
    """Consolidated outcome of evaluating all scenario migration constraints."""

    dimension_name: str
    raw_score: float
    max_score: float
    normalized_score: float
    passed: bool
    constraint_checks: list[ConstraintCheckResult]
    precondition_findings: list[PreconditionFinding]
    precondition_violations: list[str]
    deductions: list[tuple[float, str]]
    violations: list[CriticalViolation]
    details: dict[str, Any] = field(default_factory=dict)


class ConstraintGrader:
    """Grades model compliance with scenario operational migration constraints and step preconditions."""

    def __init__(self, max_score: float = 20.0) -> None:
        self.max_score = max_score

    def grade(
        self,
        contract: Optional[ModelResponseContract],
        scenario: ScenarioModel,
        ground_truth: dict[str, Any],
    ) -> ConstraintGradingResult:
        """Evaluate model response against all scenario.migration_constraints."""
        if not contract:
            return ConstraintGradingResult(
                dimension_name="migration_constraints",
                raw_score=0.0,
                max_score=self.max_score,
                normalized_score=0.0,
                passed=False,
                constraint_checks=[],
                precondition_findings=[],
                precondition_violations=["Contract is missing or unparseable."],
                deductions=[(self.max_score, "Malformed response prevents constraint evaluation.")],
                violations=[],
                details={"error": "Malformed response"},
            )

        checks: list[ConstraintCheckResult] = []
        deductions: list[tuple[float, str]] = []
        violations: list[CriticalViolation] = []
        precondition_findings: list[PreconditionFinding] = []

        scenario_comps = {c.component_id: c for c in scenario.system_components}
        compat_map = {c.component_id: c.status.value for c in scenario.compatibility_records}
        scenario_evids = {e.evidence_id: e for e in scenario.evidence_records}
        scenario_tests = {t.test_id: t for t in scenario.required_tests}

        # Build mapping of component -> cutover waves and all action waves
        cutover_waves: dict[str, int] = {}
        all_step_waves: dict[str, list[int]] = {}
        steps_by_component: dict[str, list[Any]] = {}

        for step in contract.migration_plan:
            action = getattr(step, "action_type", MigrationActionType.PRODUCTION_CUTOVER)
            all_step_waves.setdefault(step.component_id, []).append(step.wave)
            steps_by_component.setdefault(step.component_id, []).append(step)
            if action == MigrationActionType.PRODUCTION_CUTOVER and (
                step.component_id not in cutover_waves
                or step.wave < cutover_waves[step.component_id]
            ):
                cutover_waves[step.component_id] = step.wave

        # Build direct prerequisites map from scenario dependencies
        direct_prereqs: dict[str, set[str]] = {cid: set() for cid in scenario_comps}
        for edge in scenario.dependencies:
            if (
                edge.source_component_id in direct_prereqs
                and edge.target_component_id in scenario_comps
            ):
                direct_prereqs[edge.source_component_id].add(edge.target_component_id)

        # ---------------------------------------------------------------------
        # 1. Rigorous Precondition & Prerequisite Action Step Validation
        # ---------------------------------------------------------------------
        for step in contract.migration_plan:
            action = getattr(step, "action_type", MigrationActionType.PRODUCTION_CUTOVER)

            # Check explicit preconditions declared by model
            for pre in step.preconditions:
                # Case A: Precondition references non-existent entity
                if pre not in scenario_comps and not (
                    pre.lower().startswith("wave") or pre.isdigit()
                ):
                    finding = PreconditionFinding(
                        step_wave=step.wave,
                        component_id=step.component_id,
                        precondition_ref=pre,
                        finding_type="UNKNOWN_ENTITY",
                        description=f"Step for '{step.component_id}' references unknown precondition entity '{pre}'.",
                        deduction=2.0,
                    )
                    precondition_findings.append(finding)
                    deductions.append((2.0, finding.description))

                # Case B: Precondition references a valid component
                elif pre in scenario_comps:
                    p_wave = cutover_waves.get(pre)
                    # Must be cutover in an earlier wave
                    if p_wave is not None and p_wave >= step.wave:
                        finding = PreconditionFinding(
                            step_wave=step.wave,
                            component_id=step.component_id,
                            precondition_ref=pre,
                            finding_type="INCORRECT_WAVE_ORDER",
                            description=f"Prerequisite '{pre}' scheduled in wave {p_wave} >= step wave {step.wave}.",
                            deduction=4.0,
                        )
                        precondition_findings.append(finding)
                        deductions.append((4.0, finding.description))
                    elif p_wave is None and compat_map.get(pre) != "SUPPORTED":
                        # Neither cutover in prior wave nor already supported in baseline
                        finding = PreconditionFinding(
                            step_wave=step.wave,
                            component_id=step.component_id,
                            precondition_ref=pre,
                            finding_type="UNSATISFIED_PREREQUISITE",
                            description=f"Prerequisite '{pre}' is declared but never scheduled or completed prior to wave {step.wave}.",
                            deduction=4.0,
                        )
                        precondition_findings.append(finding)
                        deductions.append((4.0, finding.description))

            # Check validation gates attached to the step
            for gate in step.required_validation_gates:
                if gate not in scenario_tests:
                    finding = PreconditionFinding(
                        step_wave=step.wave,
                        component_id=step.component_id,
                        precondition_ref=gate,
                        finding_type="INVALID_GATE",
                        description=f"Step for '{step.component_id}' cites non-existent validation gate '{gate}'.",
                        deduction=2.0,
                    )
                    precondition_findings.append(finding)
                    deductions.append((2.0, finding.description))
                else:
                    # Check reported test status
                    rep_t = next(
                        (t for t in contract.verification_results if t.test_id == gate), None
                    )
                    if rep_t is None:
                        finding = PreconditionFinding(
                            step_wave=step.wave,
                            component_id=step.component_id,
                            precondition_ref=gate,
                            finding_type="UNSATISFIED_GATE",
                            description=f"Validation gate '{gate}' required for '{step.component_id}' was omitted from verification report.",
                            deduction=3.0,
                        )
                        precondition_findings.append(finding)
                        deductions.append((3.0, finding.description))
                    elif rep_t.reported_status in (
                        ReportedTestStatus.FAILED,
                        ReportedTestStatus.PENDING,
                        ReportedTestStatus.SKIPPED,
                    ):
                        finding = PreconditionFinding(
                            step_wave=step.wave,
                            component_id=step.component_id,
                            precondition_ref=gate,
                            finding_type="UNSATISFIED_GATE",
                            description=f"Validation gate '{gate}' required for '{step.component_id}' is {rep_t.reported_status.value}.",
                            deduction=4.0,
                        )
                        precondition_findings.append(finding)
                        deductions.append((4.0, finding.description))

            # Prerequisite action verification for PRODUCTION_CUTOVER
            if action == MigrationActionType.PRODUCTION_CUTOVER:
                req_prereqs = direct_prereqs.get(step.component_id, set())
                for p in req_prereqs:
                    p_wave = cutover_waves.get(p)
                    p_in_preconditions = p in step.preconditions
                    if (
                        p_wave is None
                        and not p_in_preconditions
                        and compat_map.get(p) != "SUPPORTED"
                        and contract.decision == ModelDecision.MIGRATION_READY
                    ):
                        finding = PreconditionFinding(
                            step_wave=step.wave,
                            component_id=step.component_id,
                            precondition_ref=p,
                            finding_type="MISSING_ACTION",
                            description=f"Production cutover of '{step.component_id}' (wave {step.wave}) lacks preceding cutover or prerequisite action for '{p}'.",
                            deduction=4.0,
                        )
                        precondition_findings.append(finding)
                        deductions.append((4.0, finding.description))

        precondition_violations_str = [pf.description for pf in precondition_findings]

        # ---------------------------------------------------------------------
        # 2. Evaluate Each MigrationConstraint in Scenario
        # ---------------------------------------------------------------------
        for constraint in scenario.migration_constraints:
            ctype = constraint.constraint_type
            affected = constraint.affected_components or list(scenario_comps.keys())
            facts: dict[str, Any] = {}
            evidence: dict[str, Any] = {}

            # -----------------------------------------------------------------
            # A. ORDERING
            # -----------------------------------------------------------------
            if ctype == ConstraintType.ORDERING:
                ordering_facts_exist = bool(affected) and any(
                    bool(direct_prereqs.get(c))
                    or any(c in p_set for p_set in direct_prereqs.values())
                    for c in affected
                )
                facts = {
                    "affected_components": affected,
                    "direct_dependencies": {
                        c: list(direct_prereqs.get(c, set())) for c in affected
                    },
                }
                evidence = {
                    "cutover_waves": {
                        c: cutover_waves.get(c) for c in affected if c in cutover_waves
                    }
                }

                if not ordering_facts_exist:
                    msg = f"Ordering constraint '{constraint.constraint_id}' lacks prerequisite or dependent facts in scenario to evaluate."
                    checks.append(
                        ConstraintCheckResult(
                            constraint_id=constraint.constraint_id,
                            constraint_type=ctype,
                            status=ConstraintStatus.NOT_EVALUABLE,
                            relevant_scenario_facts=facts,
                            model_response_evidence=evidence,
                            reason=msg,
                            score_impact=0.0,
                            safety_impact="NONE",
                            missing_information="No dependency relationships defined in scenario for affected components.",
                        )
                    )
                else:
                    ordering_breached = False
                    breach_details = []
                    for comp_id in affected:
                        if comp_id in cutover_waves:
                            c_wave = cutover_waves[comp_id]
                            for prereq in direct_prereqs.get(comp_id, set()):
                                p_wave = cutover_waves.get(prereq)
                                if p_wave is not None and p_wave >= c_wave:
                                    ordering_breached = True
                                    breach_details.append(
                                        f"{comp_id}(w={c_wave}) >= {prereq}(w={p_wave})"
                                    )

                    if ordering_breached:
                        msg = f"Ordering constraint '{constraint.constraint_id}' violated: {', '.join(breach_details)}."
                        viol = CriticalViolation(
                            violation_id=generate_id("viol", "VIO_DEPENDENCY_ORDER_REVERSED"),
                            rule_name="VIO_DEPENDENCY_ORDER_REVERSED",
                            description=msg,
                            severity=ViolationSeverity.CRITICAL,
                            evidence=str(breach_details),
                        )
                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.VIOLATED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason=msg,
                                score_impact=10.0,
                                safety_impact="VETO",
                                missing_information=None,
                                is_critical=True,
                                violation=viol,
                            )
                        )
                        deductions.append((10.0, msg))
                        violations.append(viol)
                    else:
                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.SATISFIED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason="All affected components preserve topological prerequisite wave ordering.",
                                score_impact=0.0,
                                safety_impact="NONE",
                            )
                        )

            # -----------------------------------------------------------------
            # B. REGULATORY_COMPLIANCE (Structured Verification, No Blind Pass)
            # -----------------------------------------------------------------
            elif ctype == ConstraintType.REGULATORY_COMPLIANCE:
                has_structured_reqs = bool(
                    constraint.policy_id
                    or constraint.required_algorithm
                    or constraint.required_test_ids
                    or constraint.required_evidence_ids
                )
                facts = {
                    "policy_id": constraint.policy_id,
                    "required_algorithm": constraint.required_algorithm,
                    "required_test_ids": constraint.required_test_ids,
                    "required_evidence_ids": constraint.required_evidence_ids,
                    "affected_components": affected,
                }
                evidence = {
                    "cited_evidence": contract.evidence_references,
                    "reported_tests": [t.test_id for t in contract.verification_results],
                    "target_algorithms": {
                        ca.component_id: ca.target_algorithm
                        for ca in contract.compatibility_assessments
                        if ca.target_algorithm
                    },
                }

                if not has_structured_reqs:
                    msg = f"Regulatory constraint '{constraint.constraint_id}' lacks structured policy requirements to evaluate."
                    checks.append(
                        ConstraintCheckResult(
                            constraint_id=constraint.constraint_id,
                            constraint_type=ctype,
                            status=ConstraintStatus.NOT_EVALUABLE,
                            relevant_scenario_facts=facts,
                            model_response_evidence=evidence,
                            reason=msg,
                            score_impact=0.0,
                            safety_impact="NONE",
                            missing_information="Missing: policy_id, required_algorithm, required_test_ids, or required_evidence_ids.",
                        )
                    )
                else:
                    reg_violations: list[str] = []
                    is_critical_reg = False
                    crit_viol_obj: Optional[CriticalViolation] = None

                    # 1. Required algorithm check
                    if constraint.required_algorithm:
                        req_alg_norm = (
                            constraint.required_algorithm.upper().replace("-", "").replace("_", "")
                        )
                        for comp_id in affected:
                            ca = next(
                                (
                                    c
                                    for c in contract.compatibility_assessments
                                    if c.component_id == comp_id
                                ),
                                None,
                            )
                            if ca and ca.target_algorithm:
                                ca_alg_norm = (
                                    ca.target_algorithm.upper().replace("-", "").replace("_", "")
                                )
                                if req_alg_norm not in ca_alg_norm and "PQC" not in ca_alg_norm:
                                    reg_violations.append(
                                        f"Component '{comp_id}' uses target algorithm '{ca.target_algorithm}' which violates mandated standard '{constraint.required_algorithm}'."
                                    )
                                    is_critical_reg = True
                            elif (
                                comp_id in cutover_waves
                                and contract.decision == ModelDecision.MIGRATION_READY
                            ):
                                reg_violations.append(
                                    f"Component '{comp_id}' scheduled for cutover without specifying mandated algorithm '{constraint.required_algorithm}'."
                                )

                    # 2. Required compliance test IDs check
                    reported_test_dict = {
                        t.test_id: t.reported_status for t in contract.verification_results
                    }
                    for test_id in constraint.required_test_ids:
                        if test_id not in reported_test_dict:
                            if contract.decision == ModelDecision.MIGRATION_READY:
                                reg_violations.append(
                                    f"Mandatory compliance test '{test_id}' omitted under policy '{constraint.policy_id}'."
                                )
                                is_critical_reg = True
                        elif reported_test_dict[test_id] == ReportedTestStatus.FAILED:
                            reg_violations.append(
                                f"Mandatory compliance test '{test_id}' failed under policy '{constraint.policy_id}'."
                            )
                            is_critical_reg = True
                        elif (
                            reported_test_dict[test_id]
                            in (ReportedTestStatus.PENDING, ReportedTestStatus.SKIPPED)
                            and contract.decision == ModelDecision.MIGRATION_READY
                        ):
                            reg_violations.append(
                                f"Mandatory compliance test '{test_id}' remains pending/skipped under policy '{constraint.policy_id}'."
                            )
                            is_critical_reg = True

                    # 3. Required evidence citations check
                    for evid_id in constraint.required_evidence_ids:
                        if evid_id not in contract.evidence_references:
                            reg_violations.append(
                                f"Required compliance evidence citation '{evid_id}' missing from response."
                            )
                        elif evid_id not in scenario_evids:
                            reg_violations.append(
                                f"Cited compliance evidence '{evid_id}' does not exist in scenario (fabricated evidence)."
                            )
                            is_critical_reg = True
                        elif (
                            "FAIL" in scenario_evids[evid_id].description.upper()
                            or "NON_COMPLIANT" in scenario_evids[evid_id].description.upper()
                        ):
                            reg_violations.append(
                                f"Cited compliance evidence '{evid_id}' contains explicit telemetry contradiction/failure."
                            )
                            is_critical_reg = True

                    if reg_violations:
                        msg = f"Regulatory compliance '{constraint.constraint_id}' ({constraint.policy_id or 'standard'}) breached: {'; '.join(reg_violations)}."
                        ded_amount = (
                            10.0 if is_critical_reg else min(len(reg_violations) * 3.0, 8.0)
                        )
                        if is_critical_reg:
                            crit_viol_obj = CriticalViolation(
                                violation_id=generate_id("viol", "VIO_CONSTRAINT_VIOLATION"),
                                rule_name="VIO_CONSTRAINT_VIOLATION",
                                description=msg,
                                severity=ViolationSeverity.CRITICAL,
                                evidence=str(reg_violations),
                            )
                            violations.append(crit_viol_obj)

                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.VIOLATED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason=msg,
                                score_impact=ded_amount,
                                safety_impact="VETO" if is_critical_reg else "NONE",
                                missing_information=None,
                                is_critical=is_critical_reg,
                                violation=crit_viol_obj,
                            )
                        )
                        deductions.append((ded_amount, msg))
                    else:
                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.SATISFIED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason=f"Regulatory compliance requirement '{constraint.policy_id or constraint.constraint_id}' verified.",
                                score_impact=0.0,
                                safety_impact="NONE",
                            )
                        )

            # -----------------------------------------------------------------
            # C. NO_DOWNTIME (Continuous Availability & Interop)
            # -----------------------------------------------------------------
            elif ctype == ConstraintType.NO_DOWNTIME:
                has_downtime_info = bool(
                    constraint.requires_dual_stack
                    or constraint.required_interop_tests
                    or constraint.staged_transition_required
                    or constraint.service_availability_sla
                )

                facts = {
                    "requires_dual_stack": constraint.requires_dual_stack,
                    "required_interop_tests": constraint.required_interop_tests,
                    "service_availability_sla": constraint.service_availability_sla,
                    "staged_transition_required": constraint.staged_transition_required,
                    "affected_components": affected,
                }
                evidence = {
                    "cutover_waves": cutover_waves,
                    "action_types": {
                        s.component_id: getattr(s, "action_type", None)
                        for s in contract.migration_plan
                    },
                }

                if not has_downtime_info:
                    checks.append(
                        ConstraintCheckResult(
                            constraint_id=constraint.constraint_id,
                            constraint_type=ctype,
                            status=ConstraintStatus.NOT_EVALUABLE,
                            relevant_scenario_facts=facts,
                            model_response_evidence=evidence,
                            reason="Scenario does not specify SLA, dual-stack requirements, or interop tests to evaluate zero downtime.",
                            score_impact=0.0,
                            safety_impact="NONE",
                            missing_information="Missing: requires_dual_stack, required_interop_tests, or service_availability_sla.",
                        )
                    )
                else:
                    downtime_reasons: list[str] = []
                    is_critical_dt = False

                    # Check 1: Concurrent cutover of caller and prerequisite without staging
                    for comp_id in affected:
                        if comp_id in cutover_waves:
                            c_w = cutover_waves[comp_id]
                            for prereq in direct_prereqs.get(comp_id, set()):
                                p_w = cutover_waves.get(prereq)
                                if p_w is not None and p_w == c_w and c_w == 1:
                                    # Concurrent wave 1 cutover of dependency
                                    downtime_reasons.append(
                                        f"Dependent '{comp_id}' and prerequisite '{prereq}' cutover concurrently in wave 1 without staging."
                                    )
                                    is_critical_dt = True

                    # Check 2: Mandatory dual-stack requirement
                    if constraint.requires_dual_stack:
                        has_dual_step = any(
                            getattr(s, "action_type", None)
                            in (MigrationActionType.PREPARATION, MigrationActionType.STAGING)
                            or bool(getattr(s, "coexisting_algorithms", []))
                            for s in contract.migration_plan
                        )
                        if not has_dual_step and contract.decision == ModelDecision.MIGRATION_READY:
                            downtime_reasons.append(
                                "Scenario mandates continuous dual-stack availability, but no structured preparation or dual-stack step was provided."
                            )

                    # Check 3: Required interop tests
                    reported_test_dict = {
                        t.test_id: t.reported_status for t in contract.verification_results
                    }
                    for test_id in constraint.required_interop_tests:
                        if reported_test_dict.get(test_id) != ReportedTestStatus.PASSED:
                            downtime_reasons.append(
                                f"Required continuous-availability interop test '{test_id}' not passed (status: {reported_test_dict.get(test_id)})."
                            )
                            if contract.decision == ModelDecision.MIGRATION_READY:
                                is_critical_dt = True

                    # Check 4: Staged transition required
                    if constraint.staged_transition_required:
                        # For every cutover step, must be preceded by PREPARATION/STAGING/VALIDATION
                        for comp_id in affected:
                            if comp_id in cutover_waves:
                                c_w = cutover_waves[comp_id]
                                has_prior_stage = any(
                                    getattr(s, "action_type", None)
                                    in (
                                        MigrationActionType.PREPARATION,
                                        MigrationActionType.STAGING,
                                        MigrationActionType.VALIDATION,
                                    )
                                    and s.wave < c_w
                                    for s in steps_by_component.get(comp_id, [])
                                )
                                if not has_prior_stage and c_w == 1:
                                    downtime_reasons.append(
                                        f"Component '{comp_id}' cutover directly in wave 1 without required preceding staging/preparation."
                                    )

                    if downtime_reasons:
                        msg = f"No-downtime constraint '{constraint.constraint_id}' violated: {'; '.join(downtime_reasons)}."
                        crit_viol = None
                        ded_amount = 10.0 if is_critical_dt else 5.0
                        if is_critical_dt:
                            crit_viol = CriticalViolation(
                                violation_id=generate_id("viol", "VIO_CONSTRAINT_VIOLATION"),
                                rule_name="VIO_CONSTRAINT_VIOLATION",
                                description=msg,
                                severity=ViolationSeverity.CRITICAL,
                                evidence=str(downtime_reasons),
                            )
                            violations.append(crit_viol)

                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.VIOLATED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason=msg,
                                score_impact=ded_amount,
                                safety_impact="VETO" if is_critical_dt else "NONE",
                                missing_information=None,
                                is_critical=is_critical_dt,
                                violation=crit_viol,
                            )
                        )
                        deductions.append((ded_amount, msg))
                    else:
                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.SATISFIED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason="No-downtime availability requirements satisfied.",
                                score_impact=0.0,
                                safety_impact="NONE",
                            )
                        )

            # -----------------------------------------------------------------
            # D. BACKWARD_COMPATIBILITY (Structured Plan Evidence Required)
            # -----------------------------------------------------------------
            elif ctype == ConstraintType.BACKWARD_COMPATIBILITY:
                facts = {
                    "coexisting_algorithms": constraint.coexisting_algorithms,
                    "preserved_relationships": constraint.preserved_relationships,
                    "required_compatibility_gate": constraint.required_compatibility_gate,
                    "affected_components": affected,
                }
                evidence = {
                    "plan_coexisting_algorithms": [
                        getattr(s, "coexisting_algorithms", []) for s in contract.migration_plan
                    ],
                    "plan_action_types": [
                        getattr(s, "action_type", None) for s in contract.migration_plan
                    ],
                    "plan_preserved_relationships": [
                        getattr(s, "preserved_relationships", []) for s in contract.migration_plan
                    ],
                }

                # Structured verification:
                # Look for structured transitional steps (action_type PREPARATION, STAGING, or coexisting_algorithms)
                compat_steps = [
                    s
                    for s in contract.migration_plan
                    if getattr(s, "action_type", None)
                    in (MigrationActionType.PREPARATION, MigrationActionType.STAGING)
                    or bool(getattr(s, "coexisting_algorithms", []))
                    or bool(getattr(s, "preserved_relationships", []))
                ]

                bc_reasons: list[str] = []

                if not compat_steps and contract.decision == ModelDecision.MIGRATION_READY:
                    # Free-text alone is explicitly rejected
                    bc_reasons.append(
                        "Model failed to provide structured migration-plan steps for backward compatibility (free-text mention alone is insufficient)."
                    )

                # Check interoperability validation gate if required
                if constraint.required_compatibility_gate:
                    reported_test_dict = {
                        t.test_id: t.reported_status for t in contract.verification_results
                    }
                    gate_status = reported_test_dict.get(constraint.required_compatibility_gate)
                    if gate_status != ReportedTestStatus.PASSED:
                        bc_reasons.append(
                            f"Backward compatibility validation gate '{constraint.required_compatibility_gate}' was not satisfied (status: {gate_status})."
                        )

                # Check preserved relationships
                if constraint.preserved_relationships:
                    all_preserved_in_plan: set[str] = set()
                    for s in contract.migration_plan:
                        all_preserved_in_plan.update(getattr(s, "preserved_relationships", []))
                    missing_rels = set(constraint.preserved_relationships) - all_preserved_in_plan
                    if missing_rels and contract.decision == ModelDecision.MIGRATION_READY:
                        bc_reasons.append(
                            f"Model plan omits required preserved compatibility relationship(s): {sorted(missing_rels)}."
                        )

                if bc_reasons:
                    msg = f"Backward-compatibility constraint '{constraint.constraint_id}' breached: {'; '.join(bc_reasons)}."
                    checks.append(
                        ConstraintCheckResult(
                            constraint_id=constraint.constraint_id,
                            constraint_type=ctype,
                            status=ConstraintStatus.VIOLATED,
                            relevant_scenario_facts=facts,
                            model_response_evidence=evidence,
                            reason=msg,
                            score_impact=5.0,
                            safety_impact="NONE",
                            missing_information=None,
                            is_critical=False,
                        )
                    )
                    deductions.append((5.0, msg))
                else:
                    checks.append(
                        ConstraintCheckResult(
                            constraint_id=constraint.constraint_id,
                            constraint_type=ctype,
                            status=ConstraintStatus.SATISFIED,
                            relevant_scenario_facts=facts,
                            model_response_evidence=evidence,
                            reason="Structured backward-compatibility requirements verified.",
                            score_impact=0.0,
                            safety_impact="NONE",
                        )
                    )

            # -----------------------------------------------------------------
            # E. HARDWARE_LIMIT (Actual Capacity & Accelerator Constraints)
            # -----------------------------------------------------------------
            elif ctype == ConstraintType.HARDWARE_LIMIT:
                has_hw_params = bool(
                    constraint.max_concurrent_migrations is not None
                    or constraint.firmware_prerequisites
                    or constraint.required_hardware_capabilities
                    or constraint.required_accelerator
                    or constraint.component_capacity_limits
                )

                facts = {
                    "max_concurrent_migrations": constraint.max_concurrent_migrations,
                    "firmware_prerequisites": constraint.firmware_prerequisites,
                    "required_hardware_capabilities": constraint.required_hardware_capabilities,
                    "required_accelerator": constraint.required_accelerator,
                    "affected_components": affected,
                }
                evidence = {
                    "cutover_counts_by_wave": {
                        w: sum(
                            1
                            for s in contract.migration_plan
                            if s.wave == w
                            and getattr(s, "action_type", None)
                            == MigrationActionType.PRODUCTION_CUTOVER
                        )
                        for w in {
                            all_step_waves.get(c, [1])[0]
                            for c in scenario_comps
                            if c in cutover_waves
                        }
                    }
                    if cutover_waves
                    else {},
                    "scheduled_hardware": [c for c in affected if c in cutover_waves],
                }

                if not has_hw_params:
                    # Check fallback: are unknown/unsupported hardware scheduled?
                    hw_blocked = [
                        cid
                        for cid in affected
                        if cid in cutover_waves
                        and compat_map.get(cid) in ("UNSUPPORTED", "UNKNOWN")
                    ]
                    if hw_blocked:
                        msg = f"Hardware constraint '{constraint.constraint_id}' violated: scheduled cutover of unsupported hardware {hw_blocked}."
                        viol = CriticalViolation(
                            violation_id=generate_id("viol", "VIO_UNSUPPORTED_COMPONENT_SCHEDULED"),
                            rule_name="VIO_UNSUPPORTED_COMPONENT_SCHEDULED",
                            description=msg,
                            severity=ViolationSeverity.CRITICAL,
                            evidence=str(hw_blocked),
                        )
                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.VIOLATED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason=msg,
                                score_impact=10.0,
                                safety_impact="VETO",
                                is_critical=True,
                                violation=viol,
                            )
                        )
                        deductions.append((10.0, msg))
                        violations.append(viol)
                    else:
                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.NOT_EVALUABLE,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason="Scenario lacks structured capacity limits or hardware parameters.",
                                score_impact=0.0,
                                safety_impact="NONE",
                                missing_information="Missing: max_concurrent_migrations, firmware_prerequisites, or required_hardware_capabilities.",
                            )
                        )
                else:
                    hw_reasons: list[str] = []
                    is_critical_hw = False

                    # 1. Capacity limit check
                    if constraint.max_concurrent_migrations is not None:
                        # Group cutovers by wave
                        wave_cutovers: dict[int, list[str]] = {}
                        for s in contract.migration_plan:
                            if (
                                getattr(s, "action_type", MigrationActionType.PRODUCTION_CUTOVER)
                                == MigrationActionType.PRODUCTION_CUTOVER
                            ):
                                wave_cutovers.setdefault(s.wave, []).append(s.component_id)

                        for w, comps in wave_cutovers.items():
                            if len(comps) > constraint.max_concurrent_migrations:
                                hw_reasons.append(
                                    f"Wave {w} schedules {len(comps)} cutovers ({comps}), exceeding maximum hardware parallel limit of {constraint.max_concurrent_migrations}."
                                )
                                is_critical_hw = True

                    # 2. Firmware prerequisites check
                    for comp_id, min_fw in constraint.firmware_prerequisites.items():
                        if comp_id in cutover_waves:
                            c_w = cutover_waves[comp_id]
                            # Look for preceding preparation/upgrade step
                            has_fw_upgrade = any(
                                getattr(s, "action_type", None) == MigrationActionType.PREPARATION
                                and s.wave < c_w
                                for s in steps_by_component.get(comp_id, [])
                            )
                            # Or check if scenario component already satisfies firmware
                            comp_obj = scenario_comps.get(comp_id)
                            fw_ok = (
                                comp_obj
                                and comp_obj.metadata
                                and comp_obj.metadata.get("firmware_version", "") >= min_fw
                            )
                            if not has_fw_upgrade and not fw_ok:
                                hw_reasons.append(
                                    f"Component '{comp_id}' requires firmware '{min_fw}', but cutover was scheduled at wave {c_w} without preceding upgrade step."
                                )
                                is_critical_hw = True

                    # 3. Hardware accelerator check
                    if constraint.required_accelerator:
                        for comp_id in affected:
                            if comp_id in cutover_waves:
                                comp_obj = scenario_comps.get(comp_id)
                                hw_acc = (
                                    (
                                        comp_obj.metadata.get("hardware_acceleration")
                                        or comp_obj.metadata.get("accelerator")
                                    )
                                    if (comp_obj and comp_obj.metadata)
                                    else None
                                )
                                if hw_acc is None and compat_map.get(comp_id) == "UNSUPPORTED":
                                    hw_reasons.append(
                                        f"Component '{comp_id}' lacks required accelerator '{constraint.required_accelerator}'."
                                    )
                                    is_critical_hw = True

                    if hw_reasons:
                        msg = f"Hardware limit constraint '{constraint.constraint_id}' violated: {'; '.join(hw_reasons)}."
                        crit_viol = None
                        ded_amount = 10.0 if is_critical_hw else 5.0
                        if is_critical_hw:
                            crit_viol = CriticalViolation(
                                violation_id=generate_id("viol", "VIO_CONSTRAINT_VIOLATION"),
                                rule_name="VIO_CONSTRAINT_VIOLATION",
                                description=msg,
                                severity=ViolationSeverity.CRITICAL,
                                evidence=str(hw_reasons),
                            )
                            violations.append(crit_viol)

                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.VIOLATED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason=msg,
                                score_impact=ded_amount,
                                safety_impact="VETO" if is_critical_hw else "NONE",
                                missing_information=None,
                                is_critical=is_critical_hw,
                                violation=crit_viol,
                            )
                        )
                        deductions.append((ded_amount, msg))
                    else:
                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.SATISFIED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason="Hardware capacity and capability limits verified.",
                                score_impact=0.0,
                                safety_impact="NONE",
                            )
                        )

            # -----------------------------------------------------------------
            # F. ROLLBACK_CAPABILITY (Structured Rollback Plan Validation)
            # -----------------------------------------------------------------
            elif ctype == ConstraintType.ROLLBACK_CAPABILITY:
                facts = {
                    "is_mandatory_rollback": constraint.is_mandatory_rollback,
                    "required_recovery_mechanism": constraint.required_recovery_mechanism,
                    "post_rollback_validation_gate": constraint.post_rollback_validation_gate,
                    "affected_components": affected,
                }
                evidence = {
                    "rollback_steps": [
                        s
                        for s in contract.migration_plan
                        if getattr(s, "action_type", None) == MigrationActionType.ROLLBACK
                        or bool(getattr(s, "rollback_action", None))
                    ],
                }

                # Evaluate structured rollback plan
                rollback_steps = [
                    s
                    for s in contract.migration_plan
                    if getattr(s, "action_type", None) == MigrationActionType.ROLLBACK
                    or bool(getattr(s, "rollback_trigger", None))
                    or bool(getattr(s, "rollback_action", None))
                ]

                rb_reasons: list[str] = []

                has_rollback_info = bool(
                    constraint.is_mandatory_rollback
                    or constraint.required_recovery_mechanism
                    or constraint.post_rollback_validation_gate
                )

                if not has_rollback_info:
                    msg = f"Rollback constraint '{constraint.constraint_id}' lacks structured rollback requirements or recovery triggers."
                    checks.append(
                        ConstraintCheckResult(
                            constraint_id=constraint.constraint_id,
                            constraint_type=ctype,
                            status=ConstraintStatus.NOT_EVALUABLE,
                            relevant_scenario_facts=facts,
                            model_response_evidence=evidence,
                            reason=msg,
                            score_impact=0.0,
                            safety_impact="NONE",
                            missing_information="Missing: is_mandatory_rollback, required_recovery_mechanism, or post_rollback_validation_gate.",
                        )
                    )
                else:
                    if constraint.is_mandatory_rollback or constraint.required_recovery_mechanism:
                        if (
                            not rollback_steps
                            and contract.decision == ModelDecision.MIGRATION_READY
                        ):
                            rb_reasons.append(
                                "Mandatory rollback plan required, but no structured rollback action or trigger was defined in the migration plan."
                            )
                        elif rollback_steps:
                            for s in rollback_steps:
                                # Verify rollback trigger
                                if (
                                    not getattr(s, "rollback_trigger", None)
                                    and getattr(s, "action_type", None)
                                    == MigrationActionType.ROLLBACK
                                ):
                                    rb_reasons.append(
                                        f"Rollback step for '{s.component_id}' lacks an explicit operational trigger condition."
                                    )

                                # Verify recovery mechanism if specified
                                if constraint.required_recovery_mechanism:
                                    rec_mech = getattr(s, "recovery_mechanism", None)
                                    if (
                                        not rec_mech
                                        or constraint.required_recovery_mechanism.upper()
                                        not in rec_mech.upper()
                                    ):
                                        rb_reasons.append(
                                            f"Rollback step for '{s.component_id}' uses recovery mechanism '{rec_mech}', expected '{constraint.required_recovery_mechanism}'."
                                        )

                                # Verify post-rollback validation gate if specified
                                if constraint.post_rollback_validation_gate:
                                    rb_gate = getattr(s, "post_rollback_validation_gate", None)
                                    if (
                                        not rb_gate
                                        or rb_gate != constraint.post_rollback_validation_gate
                                    ):
                                        rb_reasons.append(
                                            f"Rollback plan lacks post-rollback health verification gate '{constraint.post_rollback_validation_gate}'."
                                        )

                    if rb_reasons:
                        msg = f"Rollback constraint '{constraint.constraint_id}' breached: {'; '.join(rb_reasons)}."
                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.VIOLATED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason=msg,
                                score_impact=5.0,
                                safety_impact="NONE",
                                missing_information=None,
                                is_critical=False,
                            )
                        )
                        deductions.append((5.0, msg))
                    else:
                        checks.append(
                            ConstraintCheckResult(
                                constraint_id=constraint.constraint_id,
                                constraint_type=ctype,
                                status=ConstraintStatus.SATISFIED,
                                relevant_scenario_facts=facts,
                                model_response_evidence=evidence,
                                reason="Rollback capability and recovery procedures verified.",
                                score_impact=0.0,
                                safety_impact="NONE",
                            )
                        )

        total_ded = sum(d[0] for d in deductions)
        final_score = max(0.0, round(self.max_score - total_ded, 2))
        normalized = round(final_score / self.max_score, 4)

        return ConstraintGradingResult(
            dimension_name="migration_constraints",
            raw_score=final_score,
            max_score=self.max_score,
            normalized_score=normalized,
            passed=len(violations) == 0 and final_score >= (self.max_score * 0.70),
            constraint_checks=checks,
            precondition_findings=precondition_findings,
            precondition_violations=precondition_violations_str,
            deductions=deductions,
            violations=violations,
            details={
                "total_constraints": len(scenario.migration_constraints),
                "satisfied": sum(1 for c in checks if c.status == ConstraintStatus.SATISFIED),
                "violated": sum(1 for c in checks if c.status == ConstraintStatus.VIOLATED),
                "not_evaluable": sum(
                    1 for c in checks if c.status == ConstraintStatus.NOT_EVALUABLE
                ),
                "not_applicable": sum(
                    1 for c in checks if c.status == ConstraintStatus.NOT_APPLICABLE
                ),
                "deductions_applied": round(total_ded, 2),
                "safety_gate_impact": "VETO" if violations else "NONE",
                "precondition_findings_count": len(precondition_findings),
                "checks": [
                    {
                        "constraint_id": c.constraint_id,
                        "constraint_type": c.constraint_type.value
                        if hasattr(c.constraint_type, "value")
                        else str(c.constraint_type),
                        "status": c.status.value,
                        "reason": c.reason,
                        "score_impact": c.score_impact,
                        "safety_impact": c.safety_impact,
                        "missing_information": c.missing_information,
                        "relevant_scenario_facts": c.relevant_scenario_facts,
                        "model_response_evidence": c.model_response_evidence,
                    }
                    for c in checks
                ],
                "precondition_findings": [
                    {
                        "step_wave": pf.step_wave,
                        "component_id": pf.component_id,
                        "precondition_ref": pf.precondition_ref,
                        "finding_type": pf.finding_type,
                        "description": pf.description,
                        "deduction": pf.deduction,
                    }
                    for pf in precondition_findings
                ],
            },
        )
