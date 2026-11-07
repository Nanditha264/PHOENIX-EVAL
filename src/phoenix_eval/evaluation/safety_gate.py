"""Centralized safety-gate engine evaluating critical architectural and cryptographic violations."""

from dataclasses import dataclass
import re
from typing import Optional

from phoenix_eval.schemas.evaluation import CriticalViolation, ViolationSeverity
from phoenix_eval.schemas.response_contract import (
    ModelDecision,
    ModelResponseContract,
    ReportedTestStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.utils.identifiers import generate_id


@dataclass(frozen=True)
class SafetyGateResult:
    """Consolidated safety-gate outcome across all evaluation dimensions."""

    safety_gate_passed: bool
    critical_violations: list[CriticalViolation]
    non_critical_violations: list[CriticalViolation]
    blocked_components: list[str]
    blocked_tests: list[str]
    readiness_decision: str
    reasoning_trace: list[str]


class SafetyGateEngine:
    """Consolidates safety violations across dimensions and enforces safety-critical vetos."""

    def evaluate(
        self,
        contract: Optional[ModelResponseContract],
        scenario: ScenarioModel,
        collected_violations: list[CriticalViolation],
        is_dag: bool,
        readiness_blocked_by_gates: bool,
    ) -> SafetyGateResult:
        """Consolidate violations, evaluate critical rules, and determine final safety gate status."""
        critical_violations: list[CriticalViolation] = []
        non_critical_violations: list[CriticalViolation] = []
        reasoning_trace: list[str] = []

        for v in collected_violations:
            if v.severity == ViolationSeverity.CRITICAL:
                critical_violations.append(v)
                reasoning_trace.append(f"[CRITICAL VETO] {v.rule_name}: {v.description}")
            else:
                non_critical_violations.append(v)
                reasoning_trace.append(f"[WARNING] {v.rule_name}: {v.description}")

        # Independent graph and causal precedence verification
        from phoenix_eval.evaluation.independent_graph_verifier import IndependentGraphVerifier

        independent_verifier = IndependentGraphVerifier(scenario)
        effective_is_dag = is_dag and independent_verifier.is_dag

        # Check for contradictory decision formulation
        if contract is not None and contract.decision == ModelDecision.MIGRATION_READY:
            # Independent causal plan validation check
            if contract.migration_plan:
                plan_ver = independent_verifier.verify_plan(contract.migration_plan)
                if not plan_ver.is_valid and plan_ver.causal_violations:
                    if not any(v.rule_name == "VIO_DEPENDENCY_ORDER_REVERSED" for v in critical_violations):
                        viol_ord = CriticalViolation(
                            violation_id=generate_id("viol", "VIO_DEPENDENCY_ORDER_REVERSED"),
                            rule_name="VIO_DEPENDENCY_ORDER_REVERSED",
                            description=f"Model proposed plan with {len(plan_ver.causal_violations)} causal order violations.",
                            severity=ViolationSeverity.CRITICAL,
                            evidence=f"Causal violations: {plan_ver.causal_violations[:3]}",
                        )
                        critical_violations.append(viol_ord)
                        reasoning_trace.append(f"[CRITICAL VETO] {viol_ord.rule_name}: {viol_ord.description}")

            if not effective_is_dag and not any(v.rule_name == "VIO_CYCLE_IGNORED" for v in critical_violations):
                viol_cyc = CriticalViolation(
                    violation_id=generate_id("viol", "VIO_CYCLE_IGNORED"),
                    rule_name="VIO_CYCLE_IGNORED",
                    description="Model declared MIGRATION_READY on a system with directed cyclic deadlocks.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Detected cycles: {independent_verifier.cycles}",
                )
                critical_violations.append(viol_cyc)
                reasoning_trace.append(f"[CRITICAL VETO] {viol_cyc.rule_name}: {viol_cyc.description}")
            from phoenix_eval.schemas.response_contract import MigrationActionType, ReportedCompatibilityStatus

            has_reported_blockers = len(contract.blocked_components) > 0
            has_reported_test_failures = any(
                t.reported_status == ReportedTestStatus.FAILED
                for t in contract.verification_results
            )
            has_reported_test_pending = any(
                t.reported_status in (ReportedTestStatus.PENDING, ReportedTestStatus.SKIPPED)
                for t in contract.verification_results
            )
            has_unresolved_conditions = any(
                getattr(s, "is_conditional", False) for s in contract.migration_plan
            )
            has_reported_unsupported_cutover = any(
                ca.status == ReportedCompatibilityStatus.UNSUPPORTED
                for ca in contract.compatibility_assessments
                if any(
                    s.component_id == ca.component_id
                    and getattr(s, "action_type", MigrationActionType.PRODUCTION_CUTOVER)
                    == MigrationActionType.PRODUCTION_CUTOVER
                    for s in contract.migration_plan
                )
            )
            comp_statuses: dict[str, set[str]] = {}
            for ca in contract.compatibility_assessments:
                comp_statuses.setdefault(ca.component_id, set()).add(ca.status.value)
            has_conflicting_compatibility = any(len(s) > 1 for s in comp_statuses.values())

            # Detect circular dependency deadlocks in reported dependencies
            reported_adj: dict[str, set[str]] = {}
            for dep in contract.identified_dependencies:
                reported_adj.setdefault(dep.source_component_id, set()).add(dep.target_component_id)
            visited_r: set[str] = set()
            rec_stack: set[str] = set()

            def _has_reported_cycle(u: str) -> bool:
                visited_r.add(u)
                rec_stack.add(u)
                for v in reported_adj.get(u, set()):
                    if v not in visited_r:
                        if _has_reported_cycle(v):
                            return True
                    elif v in rec_stack:
                        return True
                rec_stack.remove(u)
                return False

            has_reported_cycles = False
            for node in list(reported_adj.keys()):
                if node not in visited_r:
                    if _has_reported_cycle(node):
                        has_reported_cycles = True
                        break

            if (
                has_reported_blockers
                or has_reported_test_failures
                or has_reported_test_pending
                or has_unresolved_conditions
                or has_reported_unsupported_cutover
                or has_conflicting_compatibility
                or has_reported_cycles
            ):
                viol = CriticalViolation(
                    violation_id=generate_id("viol", "VIO_CONTRADICTORY_DECISION"),
                    rule_name="VIO_CONTRADICTORY_DECISION",
                    description=(
                        "Model decision contradicts its own reported findings or structural constraints "
                        f"(declared MIGRATION_READY while reporting {len(contract.blocked_components)} blocker(s), "
                        f"{sum(1 for t in contract.verification_results if t.reported_status == ReportedTestStatus.FAILED)} failed test(s), "
                        f"{sum(1 for t in contract.verification_results if t.reported_status in (ReportedTestStatus.PENDING, ReportedTestStatus.SKIPPED))} pending/skipped test(s), "
                        f"unsupported cutovers={has_reported_unsupported_cutover}, conflicting compatibility={has_conflicting_compatibility}, "
                        f"reported cycles={has_reported_cycles})."
                    ),
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Reported blockers: {contract.blocked_components}, decision: {contract.decision.value}",
                )
                critical_violations.append(viol)
                reasoning_trace.append(f"[CRITICAL VETO] {viol.rule_name}: {viol.description}")

            # Enforce gate blocking if readiness is blocked by mandatory tests
            if readiness_blocked_by_gates and not any(
                v.rule_name
                in (
                    "VIO_FAILED_TEST_IGNORED",
                    "VIO_PENDING_TEST_CERTIFIED",
                    "VIO_REQUIRED_TEST_MISSING",
                )
                for v in critical_violations
            ):
                gate_viol = CriticalViolation(
                    violation_id=generate_id("viol", "VIO_REQUIRED_TEST_MISSING"),
                    rule_name="VIO_REQUIRED_TEST_MISSING",
                    description="Model declared MIGRATION_READY while mandatory verification gates are missing or unsatisfied.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence="readiness_blocked_by_gates=True",
                )
                critical_violations.append(gate_viol)
                reasoning_trace.append(
                    f"[CRITICAL VETO] {gate_viol.rule_name}: {gate_viol.description}"
                )

        # Check for blocked cutovers submitted under MIGRATION_BLOCKED / INSUFFICIENT_INFORMATION
        if contract is not None and contract.decision in (
            ModelDecision.MIGRATION_BLOCKED,
            ModelDecision.INSUFFICIENT_INFORMATION,
        ):
            from phoenix_eval.schemas.response_contract import MigrationActionType

            cutover_cids = [
                s.component_id
                for s in contract.migration_plan
                if getattr(s, "action_type", MigrationActionType.PRODUCTION_CUTOVER)
                == MigrationActionType.PRODUCTION_CUTOVER
            ]
            if cutover_cids and not any(
                v.rule_name == "VIO_UNSAFE_BLOCKED_PLAN" for v in critical_violations
            ):
                viol_blocked = CriticalViolation(
                    violation_id=generate_id("viol", "VIO_UNSAFE_BLOCKED_PLAN"),
                    rule_name="VIO_UNSAFE_BLOCKED_PLAN",
                    description=f"Model declared {contract.decision.value} but submitted plan scheduling production cutovers: {cutover_cids}.",
                    severity=ViolationSeverity.CRITICAL,
                    evidence=f"Decision: {contract.decision.value}, Cutover components: {cutover_cids}",
                )
                critical_violations.append(viol_blocked)
                reasoning_trace.append(
                    f"[CRITICAL VETO] {viol_blocked.rule_name}: {viol_blocked.description}"
                )

        # Blocked components calculation from scenario
        blocked_comps = sorted(
            {
                c.component_id
                for c in scenario.compatibility_records
                if c.status.value in ("UNSUPPORTED", "UNKNOWN")
            }
        )

        # Blocked tests calculation from scenario
        blocked_tests = sorted(
            {
                t.test_id
                for t in scenario.required_tests
                if bool(re.search(r'\bSTATUS\s*:\s*(FAILED|FAIL)\b', t.description, re.IGNORECASE))
            }
        )

        # Calculate authoritative readiness decision
        if not effective_is_dag:
            authoritative_decision = ModelDecision.MIGRATION_BLOCKED.value
            reasoning_trace.append("System contains directed cycles: MIGRATION_BLOCKED required.")
        elif blocked_comps:
            authoritative_decision = ModelDecision.MIGRATION_BLOCKED.value
            reasoning_trace.append(
                f"System contains compatibility blockers {blocked_comps}: MIGRATION_BLOCKED required."
            )
        elif blocked_tests or readiness_blocked_by_gates:
            authoritative_decision = (
                ModelDecision.CONDITIONAL.value
                if not blocked_tests
                else ModelDecision.MIGRATION_BLOCKED.value
            )
            reasoning_trace.append(
                "System verification gates pending or failed: unconditional cutover forbidden."
            )
        else:
            authoritative_decision = ModelDecision.MIGRATION_READY.value
            reasoning_trace.append(
                "All components supported and verification gates clear: MIGRATION_READY permitted."
            )

        safety_gate_passed = len(critical_violations) == 0

        return SafetyGateResult(
            safety_gate_passed=safety_gate_passed,
            critical_violations=critical_violations,
            non_critical_violations=non_critical_violations,
            blocked_components=blocked_comps,
            blocked_tests=blocked_tests,
            readiness_decision=authoritative_decision,
            reasoning_trace=reasoning_trace,
        )
