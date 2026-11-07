"""Strict Pydantic v2 data contracts for model responses in PHOENIX-EVAL Phase 3.

Defines the machine-readable response format required from evaluated AI models,
including controlled vocabularies, dependency representations, compatibility
assessments, migration wave steps, and verification gate outcomes.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.utils.identifiers import ensure_valid_identifier


class ModelDecision(StrEnum):
    """Controlled vocabulary for overall architectural migration decisions."""

    MIGRATION_READY = "MIGRATION_READY"
    MIGRATION_BLOCKED = "MIGRATION_BLOCKED"
    CONDITIONAL = "CONDITIONAL"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class ReportedCompatibilityStatus(StrEnum):
    """Compatibility statuses permitted in model assessments."""

    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class ReportedTestStatus(StrEnum):
    """Verification test execution status reported by the model."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"


class MigrationActionType(StrEnum):
    """Categorization of actions within a migration plan step.

    Distinguishes non-destructive preparation, discovery, staging, and validation
    from irrevocable production cutover and emergency rollback.
    """

    DISCOVERY = "DISCOVERY"
    PREPARATION = "PREPARATION"
    STAGING = "STAGING"
    VALIDATION = "VALIDATION"
    PRODUCTION_CUTOVER = "PRODUCTION_CUTOVER"
    ROLLBACK = "ROLLBACK"


class ReportedDependency(BaseModel):
    """A directed dependency relationship reported by the model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_component_id: str = Field(
        ...,
        description="Caller / dependent component ID that relies on the target.",
    )
    target_component_id: str = Field(
        ...,
        description="Prerequisite / provider component ID that is relied upon.",
    )
    relationship_type: Optional[str] = Field(
        default=None,
        description="Relationship type (e.g. CALLS, ENCRYPTS_WITH, HARDWARE_DEPENDENCY).",
    )
    evidence_reference: Optional[str] = Field(
        default=None,
        description="Evidence ID supporting this dependency link.",
    )

    @field_validator("source_component_id", "target_component_id")
    @classmethod
    def validate_component_ids(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="component_id")


class ReportedCompatibility(BaseModel):
    """Component compatibility assessment reported by the model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: str = Field(..., description="ID of the component assessed.")
    status: ReportedCompatibilityStatus = Field(
        ...,
        description="Assessed compatibility: SUPPORTED, UNSUPPORTED, or UNKNOWN.",
    )
    target_algorithm: Optional[str] = Field(
        default=None,
        description="Target algorithm evaluated (e.g. ML-KEM-768, ML-DSA-65).",
    )
    evidence_reference: Optional[str] = Field(
        default=None,
        description="Evidence ID supporting this compatibility assessment.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Reasoning or limitation notes.",
    )

    @field_validator("component_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="component_id")

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: object) -> object:
        if isinstance(v, str):
            v_clean = v.strip().upper().replace("-", "_").replace(" ", "_")
            if v_clean in (
                "UNSUPPORTED",
                "NOT_SUPPORTED",
                "INCOMPATIBLE",
                "NON_COMPLIANT",
                "FAIL",
                "FAILED",
                "BLOCKED",
            ):
                return ReportedCompatibilityStatus.UNSUPPORTED
            if v_clean in ("SUPPORTED", "COMPATIBLE", "COMPLIANT", "PASS", "PASSED", "READY"):
                return ReportedCompatibilityStatus.SUPPORTED
            if v_clean in ("UNKNOWN", "UNCERTAIN", "AMBIGUOUS", "UNVERIFIED", "PENDING"):
                return ReportedCompatibilityStatus.UNKNOWN
        return v


class ReportedMigrationStep(BaseModel):
    """A scheduled migration action within a phased wave."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    wave: int = Field(..., ge=1, description="Positive wave index (Wave 1 is first).")
    component_id: str = Field(..., description="ID of the component scheduled for migration.")
    action_type: MigrationActionType = Field(
        default=MigrationActionType.PRODUCTION_CUTOVER,
        description="Nature of migration action: DISCOVERY, PREPARATION, STAGING, VALIDATION, PRODUCTION_CUTOVER, or ROLLBACK.",
    )
    preconditions: list[str] = Field(
        default_factory=list,
        description="Required predecessor waves, components, or tasks.",
    )
    required_validation_gates: list[str] = Field(
        default_factory=list,
        description="Test IDs that must pass before or during this step.",
    )
    is_conditional: bool = Field(
        default=False,
        description="Whether this step requires contingent discovery resolution.",
    )
    # Structured backward-compatibility & transition plan fields
    coexisting_algorithms: list[str] = Field(
        default_factory=list,
        description="Algorithms running concurrently in dual-stack mode during this step.",
    )
    preserved_relationships: list[str] = Field(
        default_factory=list,
        description="Producer-consumer relationship IDs preserved by this step.",
    )
    # Structured rollback fields
    rollback_trigger: Optional[str] = Field(
        default=None,
        description="Event or metric condition that triggers rollback of this step.",
    )
    rollback_action: Optional[str] = Field(
        default=None,
        description="Specific automated action executed during rollback.",
    )
    recovery_mechanism: Optional[str] = Field(
        default=None,
        description="Technical recovery mechanism (e.g. DUAL_STACK_FALLBACK, SNAPSHOT_RESTORE).",
    )
    post_rollback_validation_gate: Optional[str] = Field(
        default=None,
        description="Verification test ID executed post-rollback to certify system health.",
    )

    @field_validator("component_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="component_id")


class ReportedTestResult(BaseModel):
    """Validation test outcome reported by the model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    test_id: str = Field(..., description="ID of the verification test.")
    reported_status: ReportedTestStatus = Field(
        ...,
        description="Status: PASSED, FAILED, PENDING, or SKIPPED.",
    )
    evidence_reference: Optional[str] = Field(
        default=None,
        description="Evidence ID containing test logs or execution telemetry.",
    )
    relevant_component: Optional[str] = Field(
        default=None,
        description="Component ID targeted by the test.",
    )

    @field_validator("test_id")
    @classmethod
    def validate_test_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="test_id")

    @field_validator("reported_status", mode="before")
    @classmethod
    def normalize_test_status(cls, v: object) -> object:
        if isinstance(v, str):
            v_clean = v.strip().upper().replace("-", "_").replace(" ", "_")
            if v_clean in ("PASSED", "PASS", "SUCCESS", "SUCCEEDED", "OK"):
                return ReportedTestStatus.PASSED
            if v_clean in ("FAILED", "FAIL", "ERROR", "FAILURE"):
                return ReportedTestStatus.FAILED
            if v_clean in ("PENDING", "WAITING", "RUNNING", "IN_PROGRESS"):
                return ReportedTestStatus.PENDING
            if v_clean in ("SKIPPED", "SKIP", "OMITTED"):
                return ReportedTestStatus.SKIPPED
        return v


class ModelResponseContract(BaseModel):
    """Authoritative Pydantic contract for structured model evaluation responses.

    Enforces machine-readable output schemas for all PHOENIX-EVAL Phase 3 benchmark tasks.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(..., description="Benchmark task ID being answered.")
    decision: ModelDecision = Field(
        ...,
        description="Overall migration recommendation from the controlled vocabulary.",
    )
    identified_dependencies: list[ReportedDependency] = Field(
        default_factory=list,
        description="List of directed dependency relationships identified.",
    )
    compatibility_assessments: list[ReportedCompatibility] = Field(
        default_factory=list,
        description="Granular component compatibility evaluations.",
    )
    migration_plan: list[ReportedMigrationStep] = Field(
        default_factory=list,
        description="Ordered sequence of migration wave steps.",
    )
    blocked_components: list[str] = Field(
        default_factory=list,
        description="Components explicitly identified as migration blockers.",
    )
    required_actions: list[str] = Field(
        default_factory=list,
        description="Remediations, dual-stack fallbacks, or staging requirements.",
    )
    verification_results: list[ReportedTestResult] = Field(
        default_factory=list,
        description="Results of pre-migration verification and interoperability tests.",
    )
    evidence_references: list[str] = Field(
        default_factory=list,
        description="All evidence IDs explicitly cited by the model.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made by the model in the absence of explicit evidence.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Identified epistemic uncertainties and information gaps.",
    )
    explanation: str = Field(
        default="",
        description="Narrative justification explaining the decisions and constraints.",
    )
    contract_version: str = Field(
        default="1.0.0",
        description="Version of the PHOENIX-EVAL model response contract.",
    )

    @field_validator("task_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="task_id")

    @field_validator("decision", mode="before")
    @classmethod
    def normalize_decision(cls, v: object) -> object:
        if isinstance(v, str):
            v_clean = v.strip().upper().replace("-", "_").replace(" ", "_")
            if v_clean in ("BLOCKED", "MIGRATION_BLOCKED", "REFUSE", "REFUSED", "FAIL"):
                return ModelDecision.MIGRATION_BLOCKED
            if v_clean in ("READY", "MIGRATION_READY", "APPROVED", "PASS"):
                return ModelDecision.MIGRATION_READY
            if v_clean in ("CONDITIONAL", "CONDITIONAL_READY", "CONTINGENT"):
                return ModelDecision.CONDITIONAL
            if v_clean in (
                "INSUFFICIENT_INFORMATION",
                "INSUFFICIENT",
                "UNKNOWN",
                "UNCERTAIN",
            ):
                return ModelDecision.INSUFFICIENT_INFORMATION
        return v
