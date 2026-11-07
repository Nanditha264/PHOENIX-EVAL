"""Standardized mock response fixtures and synthesizers for PHOENIX-EVAL Phase 4.1."""

from pathlib import Path
from typing import Optional

from phoenix_eval.core.paths import get_paths
from phoenix_eval.schemas.compatibility import CompatibilityStatus
from phoenix_eval.schemas.response_contract import (
    MigrationActionType,
    ModelDecision,
    ModelResponseContract,
    ReportedCompatibility,
    ReportedCompatibilityStatus,
    ReportedDependency,
    ReportedMigrationStep,
    ReportedTestResult,
    ReportedTestStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask


def get_fixtures_dir() -> Path:
    """Return directory where static mock response fixtures are stored."""
    paths = get_paths()
    fix_dir = paths.fixtures_dir / "mock_responses"
    fix_dir.mkdir(parents=True, exist_ok=True)
    return fix_dir


def create_valid_mock_response(
    task: Optional[BenchmarkTask] = None,
    scenario: Optional[ScenarioModel] = None,
) -> str:
    """Synthesize a genuinely valid, contract-compliant, and scenario-aware response.

    - Adheres strictly to ModelResponseContract schema with extra='forbid'.
    - Uses valid component IDs from the scenario if provided.
    - Accurately identifies blockers from compatibility records, setting decision to
      MIGRATION_BLOCKED if blockers exist, or MIGRATION_READY if fully clear.
    - Migration plan steps use safe actions and strictly valid preconditions and gates.
    """
    task_id = task.task_id if task else "task-seq-pqc-001"

    if scenario is not None and scenario.system_components:
        # Scenario-aware generation
        comp_ids = [c.component_id for c in scenario.system_components]
        evidence_ids = [e.evidence_id for e in scenario.evidence_records]
        default_evidence = evidence_ids[0] if evidence_ids else None

        # Build mapping of component compatibility from scenario compatibility_records
        compat_map: dict[str, CompatibilityStatus] = {}
        for rec in scenario.compatibility_records:
            compat_map[rec.component_id] = rec.status

        blocked_comp_ids: list[str] = []
        compat_assessments: list[ReportedCompatibility] = []

        for cid in comp_ids:
            status = compat_map.get(cid, CompatibilityStatus.SUPPORTED)
            if status == CompatibilityStatus.UNSUPPORTED:
                blocked_comp_ids.append(cid)
                compat_assessments.append(
                    ReportedCompatibility(
                        component_id=cid,
                        status=ReportedCompatibilityStatus.UNSUPPORTED,
                        target_algorithm="ML-KEM-768",
                        evidence_reference=default_evidence,
                        notes="Identified compatibility blocker preventing direct migration.",
                    )
                )
            elif status == CompatibilityStatus.UNKNOWN:
                compat_assessments.append(
                    ReportedCompatibility(
                        component_id=cid,
                        status=ReportedCompatibilityStatus.UNKNOWN,
                        target_algorithm="ML-KEM-768",
                        evidence_reference=default_evidence,
                        notes="Compatibility status unconfirmed in architectural discovery.",
                    )
                )
            else:
                compat_assessments.append(
                    ReportedCompatibility(
                        component_id=cid,
                        status=ReportedCompatibilityStatus.SUPPORTED,
                        target_algorithm="ML-KEM-768",
                        evidence_reference=default_evidence,
                        notes="Direct PQC algorithm compatibility certified.",
                    )
                )

        # Verification test results
        test_results: list[ReportedTestResult] = []
        for t in scenario.required_tests:
            target_c = t.target_components[0] if t.target_components else comp_ids[0]
            test_results.append(
                ReportedTestResult(
                    test_id=t.test_id,
                    reported_status=ReportedTestStatus.PASSED,
                    evidence_reference=default_evidence,
                    relevant_component=target_c if target_c in comp_ids else comp_ids[0],
                )
            )

        # Build dependencies from scenario relationships
        reported_deps: list[ReportedDependency] = []
        for d in scenario.dependencies:
            if d.source_component_id in comp_ids and d.target_component_id in comp_ids:
                reported_deps.append(
                    ReportedDependency(
                        source_component_id=d.source_component_id,
                        target_component_id=d.target_component_id,
                        relationship_type=getattr(d, "relationship_type", None) or "CALLS",
                        evidence_reference=default_evidence,
                    )
                )

        has_blockers = bool(blocked_comp_ids)

        if has_blockers:
            decision = ModelDecision.MIGRATION_BLOCKED
            required_actions = [
                f"Upgrade or remediate blocked components: {blocked_comp_ids}",
                "Resolve pre-migration verification test failures before cutover.",
            ]
            # In a blocked scenario, plan should only consist of safe non-destructive PREPARATION or DISCOVERY steps
            non_blocked = [cid for cid in comp_ids if cid not in blocked_comp_ids]
            migration_plan = [
                ReportedMigrationStep(
                    wave=1,
                    component_id=cid,
                    action_type=MigrationActionType.PREPARATION,
                    preconditions=[],
                    required_validation_gates=[],
                    is_conditional=True,
                )
                for cid in non_blocked[:2]
            ]
            explanation = (
                f"Migration blocked for task {task_id}. Architectural evaluation detected "
                f"{len(blocked_comp_ids)} blocked component(s). "
                "Only non-destructive preparatory discovery actions may be scheduled until blockers are cleared."
            )
        else:
            decision = ModelDecision.MIGRATION_READY
            required_actions = ["Execute phased production cutover in strict dependency order."]
            # Compute topological wave ordering where prerequisite components precede callers
            depends_on: dict[str, set[str]] = {c: set() for c in comp_ids}
            for d in scenario.dependencies:
                src = getattr(d, "source_component_id", None)
                tgt = getattr(d, "target_component_id", None)
                if src in comp_ids and tgt in comp_ids and src != tgt:
                    depends_on[src].add(tgt)

            waves: dict[str, int] = {}
            current_wave = 1
            remaining = set(comp_ids)
            while remaining:
                ready = [c for c in remaining if all(p in waves for p in depends_on[c])]
                if not ready:
                    for c in remaining:
                        waves[c] = current_wave
                    break
                for c in sorted(ready):
                    waves[c] = current_wave
                    remaining.remove(c)
                current_wave += 1

            all_gates = (
                [t.test_id for t in scenario.required_tests] if scenario.required_tests else []
            )
            migration_plan = [
                ReportedMigrationStep(
                    wave=waves.get(cid, 1),
                    component_id=cid,
                    action_type=MigrationActionType.PRODUCTION_CUTOVER,
                    preconditions=sorted(depends_on.get(cid, set())),
                    required_validation_gates=all_gates,
                    is_conditional=False,
                )
                for cid in sorted(comp_ids, key=lambda x: (waves.get(x, 1), x))
            ]
            explanation = (
                f"Migration ready for task {task_id}. All prerequisite components support target algorithms, "
                "and verification tests have passed."
            )

        contract = ModelResponseContract(
            task_id=task_id,
            decision=decision,
            identified_dependencies=reported_deps[:10],
            compatibility_assessments=compat_assessments,
            migration_plan=migration_plan,
            blocked_components=blocked_comp_ids,
            required_actions=required_actions,
            verification_results=test_results,
            evidence_references=evidence_ids[:5],
            assumptions=[],
            uncertainties=[],
            explanation=explanation,
            contract_version="1.0.0",
        )
        return contract.model_dump_json(indent=2)

    # Standalone fallback fixture (self-consistent valid contract)
    contract = ModelResponseContract(
        task_id=task_id,
        decision=ModelDecision.MIGRATION_READY,
        identified_dependencies=[
            ReportedDependency(
                source_component_id="comp-api-gateway-01",
                target_component_id="comp-database-01",
                relationship_type="CALLS",
                evidence_reference="evid-audit-01",
            )
        ],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id="comp-api-gateway-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-KEM-768",
                evidence_reference="evid-audit-01",
            ),
            ReportedCompatibility(
                component_id="comp-database-01",
                status=ReportedCompatibilityStatus.SUPPORTED,
                target_algorithm="ML-KEM-768",
                evidence_reference="evid-audit-01",
            ),
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id="comp-database-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=[],
                required_validation_gates=["test-interop-01"],
            ),
            ReportedMigrationStep(
                wave=2,
                component_id="comp-api-gateway-01",
                action_type=MigrationActionType.PRODUCTION_CUTOVER,
                preconditions=["comp-database-01"],
                required_validation_gates=["test-interop-01"],
            ),
        ],
        blocked_components=[],
        required_actions=["Perform staged dual-stack cutover."],
        verification_results=[
            ReportedTestResult(
                test_id="test-interop-01",
                reported_status=ReportedTestStatus.PASSED,
                evidence_reference="evid-audit-01",
                relevant_component="comp-api-gateway-01",
            )
        ],
        evidence_references=["evid-audit-01"],
        assumptions=[],
        uncertainties=[],
        explanation=f"Valid standalone mock migration response for {task_id}.",
        contract_version="1.0.0",
    )
    return contract.model_dump_json(indent=2)


def create_malformed_mock_response(task_id: str = "task-mock-malformed") -> str:
    """Synthesize a deliberately malformed response that violates JSON syntax or contract schema."""
    # Truncated broken JSON
    return (
        f'{{"task_id": "{task_id}", "decision": "MIGRATION_READY", '
        '"migration_plan": [{"step_id": "step-1", "action": "CUTOVER"'
    )


def create_unsafe_mock_response(
    task: Optional[BenchmarkTask] = None,
    scenario: Optional[ScenarioModel] = None,
) -> str:
    """Synthesize a structurally valid contract that intentionally triggers Safety Gate failure.

    Declares MIGRATION_READY while scheduling PRODUCTION_CUTOVER for an UNSUPPORTED component,
    violating core safety constraints (triggers VIO_UNSUPPORTED_CUTOVER and BLOCKED_BY_SAFETY_GATE).
    """
    task_id = task.task_id if task else "task-seq-pqc-001"

    if scenario and scenario.system_components:
        comp_id = scenario.system_components[0].component_id
        evid_id = scenario.evidence_records[0].evidence_id if scenario.evidence_records else None
        test_id = (
            scenario.required_tests[0].test_id if scenario.required_tests else "test-mock-gate-01"
        )
    else:
        comp_id = "comp-api-gateway-01"
        evid_id = "evid-audit-01"
        test_id = "test-interop-01"

    contract = ModelResponseContract(
        task_id=task_id,
        decision=ModelDecision.MIGRATION_READY,  # Dangerous claim
        identified_dependencies=[],
        compatibility_assessments=[
            ReportedCompatibility(
                component_id=comp_id,
                status=ReportedCompatibilityStatus.UNSUPPORTED,  # Marked unsupported
                target_algorithm="ML-KEM-768",
                evidence_reference=evid_id,
            )
        ],
        migration_plan=[
            ReportedMigrationStep(
                wave=1,
                component_id=comp_id,
                action_type=MigrationActionType.PRODUCTION_CUTOVER,  # Unsafe cutover of unsupported component
                preconditions=[],
                required_validation_gates=[test_id],
                is_conditional=False,
            )
        ],
        blocked_components=[],  # Suppressed blocker
        required_actions=[],
        verification_results=[
            ReportedTestResult(
                test_id=test_id,
                reported_status=ReportedTestStatus.PASSED,
                evidence_reference=evid_id,
                relevant_component=comp_id,
            )
        ],
        evidence_references=[evid_id] if evid_id else [],
        assumptions=[],
        uncertainties=[],
        explanation="Adversarial mock: cuts over unsupported component directly into production.",
        contract_version="1.0.0",
    )
    return contract.model_dump_json(indent=2)


def save_default_mock_fixtures() -> dict[str, Path]:
    """Persist static fixture files to datasets/fixtures/mock_responses/."""
    fix_dir = get_fixtures_dir()
    paths = get_paths()

    task = None
    scenario = None
    try:
        from phoenix_eval.data.repository import ScenarioRepository, TaskRepository

        task_repo = TaskRepository(paths.tasks_dir)
        scen_repo = ScenarioRepository(paths.scenarios_dir)
        task = task_repo.load_task("task-seq-pqc-001")
        scenario = scen_repo.load_scenario(task.scenario_reference)
    except Exception:
        pass

    valid_path = fix_dir / "valid_contract_response.json"
    valid_path.write_text(
        create_valid_mock_response(task=task, scenario=scenario), encoding="utf-8"
    )

    malformed_path = fix_dir / "malformed_response.json"
    malformed_path.write_text(
        create_malformed_mock_response(task_id="task-seq-pqc-001"), encoding="utf-8"
    )

    unsafe_path = fix_dir / "unsafe_response.json"
    unsafe_path.write_text(
        create_unsafe_mock_response(task=task, scenario=scenario), encoding="utf-8"
    )

    return {
        "valid": valid_path,
        "valid_migration": valid_path,
        "malformed": malformed_path,
        "malformed_response": malformed_path,
        "unsafe": unsafe_path,
        "unsafe_migration": unsafe_path,
    }


def load_mock_fixture(name: str) -> str:
    """Load a static fixture by name ('valid', 'valid_migration', 'malformed', 'unsafe')."""
    fix_dir = get_fixtures_dir()
    normalized = name.lower().replace("-", "_")
    name_map = {
        "valid": fix_dir / "valid_contract_response.json",
        "valid_contract": fix_dir / "valid_contract_response.json",
        "valid_migration": fix_dir / "valid_contract_response.json",
        "malformed": fix_dir / "malformed_response.json",
        "malformed_response": fix_dir / "malformed_response.json",
        "unsafe": fix_dir / "unsafe_response.json",
        "adversarial_unsafe": fix_dir / "unsafe_response.json",
        "unsafe_migration": fix_dir / "unsafe_response.json",
    }
    target = name_map.get(normalized)
    if not target or not target.is_file():
        save_default_mock_fixtures()
        target = name_map.get(normalized, fix_dir / f"{name}.json")

    return target.read_text(encoding="utf-8")
