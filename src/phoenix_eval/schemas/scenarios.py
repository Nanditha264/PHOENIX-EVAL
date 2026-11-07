"""Scenario model representing enterprise cryptographic architectures and discovery facts."""

from typing import Optional

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from phoenix_eval.core.exceptions import ScenarioError
from phoenix_eval.schemas.common import MetadataModel, StrEnum
from phoenix_eval.schemas.compatibility import CompatibilityRecord
from phoenix_eval.schemas.components import CryptographicComponent
from phoenix_eval.schemas.dependencies import DependencyRelationship
from phoenix_eval.schemas.evidence import EvidenceRecord
from phoenix_eval.utils.identifiers import ensure_valid_identifier


class ConstraintType(StrEnum):
    """Categorization of cryptographic migration constraints."""

    ORDERING = "ORDERING"
    NO_DOWNTIME = "NO_DOWNTIME"
    BACKWARD_COMPATIBILITY = "BACKWARD_COMPATIBILITY"
    HARDWARE_LIMIT = "HARDWARE_LIMIT"
    REGULATORY_COMPLIANCE = "REGULATORY_COMPLIANCE"
    ROLLBACK_CAPABILITY = "ROLLBACK_CAPABILITY"


class TestType(StrEnum):
    """Type of mandatory pre-migration or post-migration test."""

    __test__ = False

    INTEROPERABILITY = "INTEROPERABILITY"
    REGRESSION = "REGRESSION"
    LOAD_PERFORMANCE = "LOAD_PERFORMANCE"
    FALLBACK_VERIFICATION = "FALLBACK_VERIFICATION"
    SECURITY_AUDIT = "SECURITY_AUDIT"


class MigrationConstraint(BaseModel):
    """Operational or regulatory rule bounding the migration order and execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    constraint_id: str = Field(
        ..., description="Unique ID for constraint (e.g. 'cnstr-no-downtime-01')."
    )
    constraint_type: ConstraintType = Field(
        ..., description="Classification of migration restriction."
    )
    description: str = Field(
        ..., min_length=1, description="Detailed explanation of the constraint."
    )
    affected_components: list[str] = Field(
        default_factory=list, description="Component IDs subject to this rule."
    )

    # Structured regulatory parameters
    policy_id: Optional[str] = Field(
        default=None, description="Applicable regulatory policy or standard ID."
    )
    required_algorithm: Optional[str] = Field(
        default=None, description="Required cryptographic algorithm or property."
    )
    required_evidence_ids: list[str] = Field(
        default_factory=list, description="Mandatory evidence record IDs required."
    )
    required_test_ids: list[str] = Field(
        default_factory=list, description="Mandatory compliance test IDs required."
    )
    transition_deadline: Optional[str] = Field(
        default=None, description="Transition condition or deadline."
    )

    # Structured capacity and hardware parameters
    max_concurrent_migrations: Optional[int] = Field(
        default=None, description="Maximum parallel component cutovers allowed per wave."
    )
    required_hardware_capabilities: list[str] = Field(
        default_factory=list, description="Hardware capabilities required."
    )
    firmware_prerequisites: dict[str, str] = Field(
        default_factory=dict, description="Component ID -> minimum required firmware."
    )
    required_accelerator: Optional[str] = Field(
        default=None, description="Required hardware accelerator."
    )
    component_capacity_limits: dict[str, int] = Field(
        default_factory=dict, description="Component-specific capacity restrictions."
    )

    # Structured availability / no-downtime parameters
    requires_dual_stack: Optional[bool] = Field(
        default=None, description="Whether continuous dual-stack operation is required."
    )
    required_interop_tests: list[str] = Field(
        default_factory=list, description="Mandatory interoperability test IDs."
    )
    service_availability_sla: Optional[str] = Field(
        default=None, description="Availability constraint SLA."
    )
    staged_transition_required: Optional[bool] = Field(
        default=None, description="Whether cutover must be preceded by staging/preparation."
    )

    # Structured backward compatibility parameters
    coexisting_algorithms: list[str] = Field(
        default_factory=list, description="Algorithms that must coexist during transition."
    )
    preserved_relationships: list[str] = Field(
        default_factory=list, description="Producer-consumer relationship IDs preserved."
    )
    required_compatibility_gate: Optional[str] = Field(
        default=None, description="Validation test ID confirming compatibility."
    )

    # Structured rollback parameters
    is_mandatory_rollback: bool = Field(
        default=False, description="Whether an explicit automated rollback procedure is mandatory."
    )
    required_recovery_mechanism: Optional[str] = Field(
        default=None, description="Mandatory recovery mechanism."
    )
    post_rollback_validation_gate: Optional[str] = Field(
        default=None, description="Validation test ID to verify post-rollback health."
    )

    @field_validator("constraint_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="constraint_id")


class RequiredTest(BaseModel):
    """Verification step that must pass before claiming migration completeness."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    test_id: str = Field(
        ..., description="Unique ID for verification test (e.g. 'test-tls-handshake-01')."
    )
    test_type: TestType = Field(..., description="Category of verification test.")
    description: str = Field(..., min_length=1, description="Requirement and pass/fail criteria.")
    target_components: list[str] = Field(
        default_factory=list, description="Component IDs covered by this test."
    )

    @field_validator("test_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="test_id")


class ScenarioModel(BaseModel):
    """Enterprise architecture scenario containing discovery evidence and dependencies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(
        ...,
        description="Unique identifier for the scenario (e.g. 'scen-pqc-tls-banking-001').",
    )
    scenario_name: str = Field(
        ...,
        min_length=1,
        description="Descriptive name of the enterprise scenario.",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Background narrative, architecture overview, and migration motivation.",
    )
    system_components: list[CryptographicComponent] = Field(
        ...,
        min_length=1,
        description="All system components present in the enterprise boundary.",
    )
    dependencies: list[DependencyRelationship] = Field(
        default_factory=list,
        description="Directed relationships between system components.",
    )
    compatibility_records: list[CompatibilityRecord] = Field(
        default_factory=list,
        description="Assessed compatibility for proposed cryptographic targets.",
    )
    evidence_records: list[EvidenceRecord] = Field(
        default_factory=list,
        description="Discovery evidence observations discovered in this scenario.",
    )
    migration_constraints: list[MigrationConstraint] = Field(
        default_factory=list,
        description="Hard operational constraints governing valid migrations.",
    )
    required_tests: list[RequiredTest] = Field(
        default_factory=list,
        description="Mandatory verification tests that must be satisfied.",
    )
    metadata: MetadataModel = Field(
        default_factory=MetadataModel,
        description="Scenario provenance and audit metadata.",
    )

    @field_validator("scenario_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="scenario_id")

    @model_validator(mode="after")
    def validate_scenario_integrity(self) -> "ScenarioModel":
        """Verify referential integrity across components, dependencies, and evidence."""
        comp_ids = {c.component_id for c in self.system_components}
        if len(comp_ids) != len(self.system_components):
            raise ScenarioError(f"Duplicate component IDs found in scenario '{self.scenario_id}'.")

        edge_ids = set()
        for edge in self.dependencies:
            if edge.edge_id in edge_ids:
                raise ScenarioError(
                    f"Duplicate edge ID '{edge.edge_id}' in scenario '{self.scenario_id}'."
                )
            edge_ids.add(edge.edge_id)

            if edge.source_component_id not in comp_ids:
                raise ScenarioError(
                    f"Dependency edge '{edge.edge_id}' references unknown source '{edge.source_component_id}'."
                )
            if edge.target_component_id not in comp_ids:
                raise ScenarioError(
                    f"Dependency edge '{edge.edge_id}' references unknown target '{edge.target_component_id}'."
                )

        evid_ids = {e.evidence_id for e in self.evidence_records}
        if len(evid_ids) != len(self.evidence_records):
            raise ScenarioError(f"Duplicate evidence IDs found in scenario '{self.scenario_id}'.")

        for comp in self.system_components:
            for ref in comp.evidence_references:
                if ref not in evid_ids:
                    raise ScenarioError(
                        f"Component '{comp.component_id}' references unknown evidence '{ref}' in scenario '{self.scenario_id}'."
                    )

        for dep in self.dependencies:
            for ref in dep.evidence_references:
                if ref not in evid_ids:
                    raise ScenarioError(
                        f"Dependency edge '{dep.edge_id}' references unknown evidence '{ref}' in scenario '{self.scenario_id}'."
                    )

        for compat in self.compatibility_records:
            if compat.component_id not in comp_ids:
                raise ScenarioError(
                    f"Compatibility record references unknown component '{compat.component_id}'."
                )
            for ref in compat.evidence_references:
                if ref not in evid_ids:
                    raise ScenarioError(
                        f"Compatibility record for '{compat.component_id}' references unknown evidence '{ref}' in scenario '{self.scenario_id}'."
                    )

        for constraint in self.migration_constraints:
            for affected in constraint.affected_components:
                if affected not in comp_ids:
                    raise ScenarioError(
                        f"MigrationConstraint '{constraint.constraint_id}' references unknown component '{affected}'."
                    )

        for test in self.required_tests:
            for target in test.target_components:
                if target not in comp_ids:
                    raise ScenarioError(
                        f"RequiredTest '{test.test_id}' references unknown component '{target}'."
                    )

        return self

    def to_networkx_graph(self) -> nx.DiGraph:
        """Convert the scenario components and dependencies into a directed NetworkX graph."""
        graph = nx.DiGraph(scenario_id=self.scenario_id, scenario_name=self.scenario_name)

        for comp in self.system_components:
            graph.add_node(
                comp.component_id,
                name=comp.component_name,
                type=comp.component_type.value,
                role=comp.cryptographic_role.value,
                technology=comp.technology,
                current_algorithms=comp.current_algorithms,
            )

        for dep in self.dependencies:
            graph.add_edge(
                dep.source_component_id,
                dep.target_component_id,
                edge_id=dep.edge_id,
                relationship_type=dep.relationship_type.value,
                confidence=dep.confidence,
                criticality=dep.criticality.value,
                bidirectional=dep.is_bidirectional,
            )

        return graph

    def get_component(self, component_id: str) -> Optional[CryptographicComponent]:
        """Lookup a component by its unique ID."""
        for c in self.system_components:
            if c.component_id == component_id:
                return c
        return None

    def get_compatibility(
        self, component_id: str, proposed_target: Optional[str] = None
    ) -> list[CompatibilityRecord]:
        """Retrieve compatibility records for a component."""
        records = [c for c in self.compatibility_records if c.component_id == component_id]
        if proposed_target:
            return [c for c in records if c.proposed_target == proposed_target]
        return records
