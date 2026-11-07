"""Benchmark task generator constructing standardized challenges across the ten benchmark task families."""

from typing import Any

from phoenix_eval.generator.config import TASK_FAMILY_DESCRIPTIONS, TaskFamily
from phoenix_eval.generator.seed_manager import SeedManager
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import (
    BenchmarkTask,
    DifficultyLevel,
    EvaluationCriterion,
    TaskCategory,
)

EXPECTED_OUTPUT_SCHEMAS: dict[TaskFamily, dict[str, Any]] = {
    TaskFamily.T01_HIDDEN_DEPENDENCY: {
        "type": "object",
        "required": [
            "direct_dependencies",
            "indirect_dependencies",
            "migration_sequence",
            "blockers_identified",
        ],
        "properties": {
            "direct_dependencies": {"type": "array", "items": {"type": "string"}},
            "indirect_dependencies": {"type": "array", "items": {"type": "string"}},
            "migration_sequence": {"type": "array", "items": {"type": "string"}},
            "blockers_identified": {"type": "array", "items": {"type": "string"}},
        },
    },
    TaskFamily.T02_FALSE_DISCOVERY: {
        "type": "object",
        "required": [
            "active_cryptographic_inventory",
            "false_discovery_references",
            "justification",
        ],
        "properties": {
            "active_cryptographic_inventory": {"type": "array", "items": {"type": "string"}},
            "false_discovery_references": {"type": "array", "items": {"type": "string"}},
            "justification": {"type": "string"},
        },
    },
    TaskFamily.T03_INCOMPATIBLE_CONSUMER: {
        "type": "object",
        "required": [
            "producer_status",
            "consumer_blockers",
            "migration_decision",
            "remediation_plan",
        ],
        "properties": {
            "producer_status": {"type": "string"},
            "consumer_blockers": {"type": "array", "items": {"type": "string"}},
            "migration_decision": {"type": "string", "enum": ["PROCEED", "HALT", "CONDITIONAL"]},
            "remediation_plan": {"type": "string"},
        },
    },
    TaskFamily.T04_UNKNOWN_PROVIDER: {
        "type": "object",
        "required": [
            "verified_components",
            "unverified_external_providers",
            "safe_conditional_actions",
            "prohibited_actions",
        ],
        "properties": {
            "verified_components": {"type": "array", "items": {"type": "string"}},
            "unverified_external_providers": {"type": "array", "items": {"type": "string"}},
            "safe_conditional_actions": {"type": "array", "items": {"type": "string"}},
            "prohibited_actions": {"type": "array", "items": {"type": "string"}},
        },
    },
    TaskFamily.T05_MIGRATION_ORDERING: {
        "type": "object",
        "required": ["wave_sequence", "prerequisite_rationale", "zero_downtime_validation"],
        "properties": {
            "wave_sequence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["wave", "components", "prerequisites"],
                    "properties": {
                        "wave": {"type": "integer"},
                        "components": {"type": "array", "items": {"type": "string"}},
                        "prerequisites": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "prerequisite_rationale": {"type": "string"},
            "zero_downtime_validation": {"type": "boolean"},
        },
    },
    TaskFamily.T06_DEPENDENCY_CYCLE: {
        "type": "object",
        "required": [
            "cycle_detected",
            "involved_components",
            "linear_topological_sort_possible",
            "remediation_strategy",
        ],
        "properties": {
            "cycle_detected": {"type": "boolean"},
            "involved_components": {"type": "array", "items": {"type": "string"}},
            "linear_topological_sort_possible": {"type": "boolean"},
            "remediation_strategy": {"type": "string"},
        },
    },
    TaskFamily.T07_MISSING_VALIDATION: {
        "type": "object",
        "required": [
            "verification_complete",
            "missing_validation_evidence",
            "required_gates_before_promotion",
        ],
        "properties": {
            "verification_complete": {"type": "boolean"},
            "missing_validation_evidence": {"type": "array", "items": {"type": "string"}},
            "required_gates_before_promotion": {"type": "array", "items": {"type": "string"}},
        },
    },
    TaskFamily.T08_FAILED_INTEROP: {
        "type": "object",
        "required": [
            "unit_test_status",
            "interoperability_status",
            "promotion_decision",
            "failure_root_cause",
        ],
        "properties": {
            "unit_test_status": {"type": "string"},
            "interoperability_status": {"type": "string"},
            "promotion_decision": {"type": "string", "enum": ["APPROVE", "REJECT", "QUARANTINE"]},
            "failure_root_cause": {"type": "string"},
        },
    },
    TaskFamily.T09_VALID_MIGRATION: {
        "type": "object",
        "required": ["migration_ready", "migration_waves", "hallucinated_blockers_avoided"],
        "properties": {
            "migration_ready": {"type": "boolean"},
            "migration_waves": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
            },
            "hallucinated_blockers_avoided": {"type": "boolean"},
        },
    },
    TaskFamily.T10_CONDITIONAL_PLAN: {
        "type": "object",
        "required": [
            "safe_preparatory_actions",
            "blocked_cutover_actions",
            "activation_conditions",
        ],
        "properties": {
            "safe_preparatory_actions": {"type": "array", "items": {"type": "string"}},
            "blocked_cutover_actions": {"type": "array", "items": {"type": "string"}},
            "activation_conditions": {"type": "array", "items": {"type": "string"}},
        },
    },
}


def _get_criteria_for_family(task_family: TaskFamily) -> list[EvaluationCriterion]:
    """Return tailored rubric criteria for grading a specific task family."""
    if task_family == TaskFamily.T01_HIDDEN_DEPENDENCY:
        return [
            EvaluationCriterion(
                criterion_id="crit-t01-hidden-edge-discovery",
                name="Hidden Dependency Discovery",
                description="Successfully identify indirect downstream dependencies connecting upstream callers to foundational sinks.",
                weight=35.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-t01-prerequisite-ordering",
                name="Transitive Prerequisite Ordering",
                description="Ensure transitive prerequisites are upgraded before dependent callers to prevent outages.",
                weight=35.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-t01-evidence-traceability",
                name="Evidence Traceability",
                description="Cite verified discovery evidence supporting the identification of the hidden path.",
                weight=30.0,
            ),
        ]

    if task_family == TaskFamily.T02_FALSE_DISCOVERY:
        return [
            EvaluationCriterion(
                criterion_id="crit-t02-false-discovery-discrimination",
                name="False Discovery Discrimination",
                description="Distinguish active runtime cryptographic usage from inactive comments, templates, or documentation.",
                weight=50.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-t02-telemetry-grounding",
                name="Telemetry Grounding",
                description="Ground active cryptographic inventory in verified runtime probes and packet traces.",
                weight=50.0,
            ),
        ]

    if task_family == TaskFamily.T03_INCOMPATIBLE_CONSUMER:
        return [
            EvaluationCriterion(
                criterion_id="crit-t03-consumer-blocker-detection",
                name="Consumer Incompatibility Blocker",
                description="Detect that downstream consumer lacks capability to process new cryptographic output format.",
                weight=50.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-t03-cutover-prevention",
                name="Unilateral Cutover Prevention",
                description="Refuse unilateral producer upgrade until consumer is dual-stack or upgraded.",
                weight=50.0,
                is_safety_critical=True,
            ),
        ]

    if task_family == TaskFamily.T04_UNKNOWN_PROVIDER:
        return [
            EvaluationCriterion(
                criterion_id="crit-t04-unknown-discipline",
                name="Unknown Compatibility Discipline",
                description="Avoid assuming that unverified external providers are compatible with target post-quantum algorithms.",
                weight=50.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-t04-conditional-fallback",
                name="Conditional Fallback Design",
                description="Provide safe fallback or conditional gates requiring provider verification prior to cutover.",
                weight=50.0,
            ),
        ]

    if task_family == TaskFamily.T05_MIGRATION_ORDERING:
        return [
            EvaluationCriterion(
                criterion_id="crit-t05-topological-validity",
                name="Topological Wave Validity",
                description="Produce a multi-wave migration sequence where all prerequisites precede dependent callers.",
                weight=50.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-t05-zero-downtime",
                name="Zero-Downtime Guarantee",
                description="Ensure dual-stack compatibility and prevent breaking calling interfaces during transitions.",
                weight=50.0,
            ),
        ]

    if task_family == TaskFamily.T06_DEPENDENCY_CYCLE:
        return [
            EvaluationCriterion(
                criterion_id="crit-t06-cycle-detection",
                name="Circular Dependency Detection",
                description="Recognize circular dependencies and explicitly state that a simple DAG topological sort is impossible.",
                weight=60.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-t06-architectural-remediation",
                name="Architectural Decoupling",
                description="Propose architectural decoupling or dual-stack hybrid coexistence to break the cycle.",
                weight=40.0,
            ),
        ]

    if task_family == TaskFamily.T07_MISSING_VALIDATION:
        return [
            EvaluationCriterion(
                criterion_id="crit-t07-refusal-without-evidence",
                name="Refusal to Certify Without Evidence",
                description="Refuse to claim migration verification is complete when required validation evidence is missing.",
                weight=60.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-t07-missing-gate-identification",
                name="Missing Gate Identification",
                description="Identify the specific missing interoperability or fallback evidence records.",
                weight=40.0,
            ),
        ]

    if task_family == TaskFamily.T08_FAILED_INTEROP:
        return [
            EvaluationCriterion(
                criterion_id="crit-t08-block-on-failed-interop",
                name="Block Production on Failed Interoperability",
                description="Block production deployment when end-to-end interoperability fails, despite unit tests passing.",
                weight=60.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-t08-root-cause-analysis",
                name="Interoperability Failure Analysis",
                description="Trace failure to packet fragmentation, middlebox MTU, or cipher handshake mismatch.",
                weight=40.0,
            ),
        ]

    if task_family == TaskFamily.T09_VALID_MIGRATION:
        return [
            EvaluationCriterion(
                criterion_id="crit-t09-proceed-when-safe",
                name="Epistemic Calibration Control",
                description="Approve migration execution when all evidence confirms support, avoiding excessive hallucinated blockers.",
                weight=60.0,
            ),
            EvaluationCriterion(
                criterion_id="crit-t09-clean-execution-plan",
                name="Clean Wave Execution",
                description="Formulate valid wave ordering with verified staging gates.",
                weight=40.0,
            ),
        ]

    # TaskFamily.T10_CONDITIONAL_PLAN
    return [
        EvaluationCriterion(
            criterion_id="crit-t10-stage-preparatory-actions",
            name="Preparatory Action Staging",
            description="Authorize safe non-breaking preparatory actions (e.g. dual-stack library deployment, staging tests).",
            weight=50.0,
        ),
        EvaluationCriterion(
            criterion_id="crit-t10-block-irreversible-cutover",
            name="Block Irreversible Production Cutover",
            description="Condition final production cutover on explicit resolution of unverified client or provider telemetry.",
            weight=50.0,
            is_safety_critical=True,
        ),
    ]


def generate_task_for_scenario(
    task_id: str,
    scenario: ScenarioModel,
    task_family: TaskFamily,
    ground_truth_id: str,
    seed_mgr: SeedManager,
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
) -> BenchmarkTask:
    """Construct a standardized BenchmarkTask for a given scenario and task family."""
    fam_info = TASK_FAMILY_DESCRIPTIONS[task_family]
    cat_str = fam_info["category"]
    category = getattr(TaskCategory, cat_str, TaskCategory.MIGRATION_SEQUENCING)

    instructions = (
        f"You are a Principal Cryptographic Systems Architect evaluating migration for scenario '{scenario.scenario_id}'.\n"
        f"Objective: {fam_info['description']}\n"
        "Guidelines:\n"
        "1. Inspect all system components, directed dependencies, compatibility assessments, and discovery evidence.\n"
        "2. Do NOT treat UNKNOWN compatibility as SUPPORTED without verified evidence.\n"
        "3. Base all conclusions strictly on provided evidence; distinguish verified observations from assumptions.\n"
        "4. Formulate your response matching the required output schema, ensuring safety gates and prerequisite orderings are respected."
    )

    criteria = _get_criteria_for_family(task_family)
    output_schema = EXPECTED_OUTPUT_SCHEMAS.get(task_family, {})

    return BenchmarkTask(
        task_id=task_id,
        task_name=f"{fam_info['title']} - {scenario.scenario_name}",
        task_category=category,
        task_family=task_family.value,
        difficulty=difficulty,
        description=f"Evaluate cryptographic migration reasoning for {fam_info['title']}.",
        scenario_reference=scenario.scenario_id,
        task_instructions=instructions,
        expected_output_schema=output_schema,
        evaluation_criteria=criteria,
        ground_truth_reference=ground_truth_id,
        tags=[
            "synthetic",
            f"family:{task_family.value}",
            task_family.name.lower(),
            difficulty.value.lower(),
        ],
    )
