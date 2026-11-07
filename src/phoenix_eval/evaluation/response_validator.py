"""Semantic cross-referential validation of parsed model responses against scenario facts."""

from dataclasses import dataclass

from phoenix_eval.schemas.response_contract import (
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibilityStatus,
    ReportedTestStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel


@dataclass(frozen=True)
class SemanticValidationResult:
    """Outcome of validating a model response against scenario facts."""

    is_semantically_consistent: bool
    unknown_components: list[str]
    unknown_evidence_ids: list[str]
    unknown_test_ids: list[str]
    contradictory_decisions: list[str]
    duplicate_steps: list[str]
    duplicate_tests: list[str]
    contradictory_tests: list[str]
    duplicate_compatibilities: list[str]
    invalid_test_evidence: list[str]
    warnings: list[str]


def validate_response_semantics(
    contract: ModelResponseContract,
    scenario: ScenarioModel,
) -> SemanticValidationResult:
    """Cross-reference response content against scenario ground truth entities."""
    scenario_comps = {c.component_id for c in scenario.system_components}
    scenario_evids = {e.evidence_id for e in scenario.evidence_records}
    scenario_tests = {t.test_id for t in scenario.required_tests}

    unknown_comps: set[str] = set()
    unknown_evids: set[str] = set()
    unknown_tests: set[str] = set()
    contradictions: list[str] = []
    warnings: list[str] = []

    # 1. Check reported component references
    for dep in contract.identified_dependencies:
        if dep.source_component_id not in scenario_comps:
            unknown_comps.add(dep.source_component_id)
        if dep.target_component_id not in scenario_comps:
            unknown_comps.add(dep.target_component_id)
        if dep.evidence_reference and dep.evidence_reference not in scenario_evids:
            unknown_evids.add(dep.evidence_reference)

    seen_compat_cids: set[str] = set()
    duplicate_compatibilities: list[str] = []
    for comp_eval in contract.compatibility_assessments:
        if comp_eval.component_id not in scenario_comps:
            unknown_comps.add(comp_eval.component_id)
        if comp_eval.component_id in seen_compat_cids:
            duplicate_compatibilities.append(comp_eval.component_id)
        seen_compat_cids.add(comp_eval.component_id)
        if comp_eval.evidence_reference and comp_eval.evidence_reference not in scenario_evids:
            unknown_evids.add(comp_eval.evidence_reference)

    # 2. Check migration plan steps
    seen_step_comps: set[str] = set()
    duplicates: list[str] = []
    for step in contract.migration_plan:
        if step.component_id not in scenario_comps:
            unknown_comps.add(step.component_id)
        if step.component_id in seen_step_comps:
            duplicates.append(step.component_id)
        seen_step_comps.add(step.component_id)
        for g in step.required_validation_gates:
            if g not in scenario_tests:
                unknown_tests.add(g)

    # 3. Check verification results
    seen_tests: dict[str, ReportedTestStatus] = {}
    duplicate_tests: list[str] = []
    contradictory_tests: list[str] = []
    invalid_test_evidence: list[str] = []
    failed_reported_tests: list[str] = []
    pending_reported_tests: list[str] = []

    for res in contract.verification_results:
        if res.test_id not in scenario_tests:
            unknown_tests.add(res.test_id)
        if res.test_id in seen_tests:
            duplicate_tests.append(res.test_id)
            if seen_tests[res.test_id] != res.reported_status:
                contradictory_tests.append(
                    f"Test '{res.test_id}' reported with conflicting statuses: "
                    f"'{seen_tests[res.test_id].value}' vs '{res.reported_status.value}'."
                )
        seen_tests[res.test_id] = res.reported_status

        if res.evidence_reference and res.evidence_reference not in scenario_evids:
            unknown_evids.add(res.evidence_reference)
            if res.reported_status == ReportedTestStatus.PASSED:
                invalid_test_evidence.append(
                    f"Test '{res.test_id}' claimed PASSED with non-existent evidence '{res.evidence_reference}'."
                )
        if res.relevant_component and res.relevant_component not in scenario_comps:
            unknown_comps.add(res.relevant_component)
        if res.reported_status == ReportedTestStatus.FAILED:
            failed_reported_tests.append(res.test_id)
        elif res.reported_status in (ReportedTestStatus.PENDING, ReportedTestStatus.SKIPPED):
            pending_reported_tests.append(res.test_id)

    # 4. Check explicit evidence references
    for eid in contract.evidence_references:
        if eid not in scenario_evids:
            unknown_evids.add(eid)

    # 5. Check blocked components
    for b in contract.blocked_components:
        if b not in scenario_comps:
            unknown_comps.add(b)

    # 6. Detect internal decision contradictions
    # Contradiction A: MIGRATION_READY declared while blocked_components is non-empty
    if contract.decision == ModelDecision.MIGRATION_READY and contract.blocked_components:
        contradictions.append(
            f"Contradiction: Decision is MIGRATION_READY but blocked_components is non-empty: {contract.blocked_components}."
        )

    # Contradiction B: MIGRATION_READY declared while a test is reported as FAILED, PENDING, or SKIPPED
    if contract.decision == ModelDecision.MIGRATION_READY and failed_reported_tests:
        contradictions.append(
            f"Contradiction: Decision is MIGRATION_READY but test(s) reported as FAILED: {failed_reported_tests}."
        )
    if contract.decision == ModelDecision.MIGRATION_READY and pending_reported_tests:
        contradictions.append(
            f"Contradiction: Decision is MIGRATION_READY but mandatory test(s) remain PENDING or SKIPPED: {pending_reported_tests}."
        )

    # Contradiction C: A component is marked UNKNOWN and also scheduled for production cutover
    unknown_assessed = {
        ca.component_id
        for ca in contract.compatibility_assessments
        if ca.status == ReportedCompatibilityStatus.UNKNOWN
    }
    for step in contract.migration_plan:
        from phoenix_eval.schemas.response_contract import MigrationActionType

        is_cutover = (
            getattr(step, "action_type", MigrationActionType.PRODUCTION_CUTOVER)
            == MigrationActionType.PRODUCTION_CUTOVER
        )
        if step.component_id in unknown_assessed and is_cutover and not step.is_conditional:
            contradictions.append(
                f"Contradiction: Component '{step.component_id}' has UNKNOWN compatibility but is scheduled for PRODUCTION_CUTOVER in wave {step.wave}."
            )

    # Contradiction D: Decision is MIGRATION_BLOCKED but plan contains PRODUCTION_CUTOVER steps
    from phoenix_eval.schemas.response_contract import MigrationActionType

    cutover_steps_in_plan = [
        s
        for s in contract.migration_plan
        if getattr(s, "action_type", MigrationActionType.PRODUCTION_CUTOVER)
        == MigrationActionType.PRODUCTION_CUTOVER
    ]
    if (
        contract.decision
        in (ModelDecision.MIGRATION_BLOCKED, ModelDecision.INSUFFICIENT_INFORMATION)
        and cutover_steps_in_plan
    ):
        contradictions.append(
            f"Contradiction: Decision is {contract.decision.value} but migration_plan contains {len(cutover_steps_in_plan)} PRODUCTION_CUTOVER step(s)."
        )

    # Contradiction E: Decision is CONDITIONAL but plan contains cutover of UNSUPPORTED components
    unsupported_assessed = {
        ca.component_id
        for ca in contract.compatibility_assessments
        if ca.status == ReportedCompatibilityStatus.UNSUPPORTED
    }
    if contract.decision == ModelDecision.CONDITIONAL:
        unsupported_cutovers = [
            s.component_id for s in cutover_steps_in_plan if s.component_id in unsupported_assessed
        ]
        if unsupported_cutovers:
            contradictions.append(
                f"Contradiction: Decision is CONDITIONAL but migration_plan schedules UNSUPPORTED component(s) for cutover: {unsupported_cutovers}."
            )

    # Contradiction F: Decision is MIGRATION_READY but verification_results is empty when tests are required
    if (
        contract.decision == ModelDecision.MIGRATION_READY
        and scenario_tests
        and not contract.verification_results
    ):
        contradictions.append(
            f"Contradiction: Decision is MIGRATION_READY but verification_results is empty while {len(scenario_tests)} required test(s) exist."
        )

    # Contradiction G: Decision is MIGRATION_READY but conditional steps exist
    conditional_steps = [
        s.component_id for s in contract.migration_plan if getattr(s, "is_conditional", False)
    ]
    if contract.decision == ModelDecision.MIGRATION_READY and conditional_steps:
        contradictions.append(
            f"Contradiction: Decision is MIGRATION_READY but unresolved conditional step(s) exist: {conditional_steps}."
        )

    if contradictory_tests:
        contradictions.extend(contradictory_tests)

    is_consistent = (
        len(contradictions) == 0
        and len(unknown_comps) == 0
        and len(unknown_evids) == 0
        and len(unknown_tests) == 0
        and len(duplicates) == 0
        and len(duplicate_tests) == 0
        and len(contradictory_tests) == 0
        and len(duplicate_compatibilities) == 0
    )

    return SemanticValidationResult(
        is_semantically_consistent=is_consistent,
        unknown_components=sorted(unknown_comps),
        unknown_evidence_ids=sorted(unknown_evids),
        unknown_test_ids=sorted(unknown_tests),
        contradictory_decisions=contradictions,
        duplicate_steps=sorted(set(duplicates)),
        duplicate_tests=sorted(set(duplicate_tests)),
        contradictory_tests=contradictory_tests,
        duplicate_compatibilities=sorted(set(duplicate_compatibilities)),
        invalid_test_evidence=invalid_test_evidence,
        warnings=warnings,
    )
