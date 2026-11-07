"""Configuration and taxonomy definitions for synthetic benchmark generation."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from phoenix_eval.schemas.common import StrEnum


class ArchitectureDomain(StrEnum):
    """Target enterprise architecture domains for synthetic scenarios."""

    BANKING_PAYMENTS = "BANKING_PAYMENTS"
    TELECOM_NETWORK = "TELECOM_NETWORK"
    CLOUD_IDENTITY = "CLOUD_IDENTITY"
    GOVERNMENT_CRITICAL = "GOVERNMENT_CRITICAL"
    ENTERPRISE_SERVICES = "ENTERPRISE_SERVICES"


class GraphComplexity(StrEnum):
    """Topological complexity tiers for generated dependency graphs."""

    SMALL = "SMALL"  # 5-10 components, 5-15 dependencies
    MEDIUM = "MEDIUM"  # 11-25 components, 15-45 dependencies
    LARGE = "LARGE"  # 26-50 components, 40-100 dependencies


class TaskFamily(StrEnum):
    """The ten distinct benchmark task families of PHOENIX-EVAL Phase 2."""

    T01_HIDDEN_DEPENDENCY = "T01"  # Hidden Downstream Dependency
    T02_FALSE_DISCOVERY = "T02"  # False Cryptographic Discovery
    T03_INCOMPATIBLE_CONSUMER = "T03"  # Incompatible Downstream Consumer
    T04_UNKNOWN_PROVIDER = "T04"  # Unknown External Provider
    T05_MIGRATION_ORDERING = "T05"  # Dependency-Aware Migration Ordering
    T06_DEPENDENCY_CYCLE = "T06"  # Circular Dependency Deadlock
    T07_MISSING_VALIDATION = "T07"  # Missing Validation Evidence
    T08_FAILED_INTEROP = "T08"  # Failed Interoperability Test
    T09_VALID_MIGRATION = "T09"  # Valid Migration Control
    T10_CONDITIONAL_PLAN = "T10"  # Conditional Plan Under Uncertainty


TASK_FAMILY_DESCRIPTIONS: dict[TaskFamily, dict[str, str]] = {
    TaskFamily.T01_HIDDEN_DEPENDENCY: {
        "title": "Hidden Downstream Dependency",
        "description": "Test whether the model discovers an indirect dependency that changes the migration order.",
        "category": "DEPENDENCY_DISCOVERY",
    },
    TaskFamily.T02_FALSE_DISCOVERY: {
        "title": "False Cryptographic Discovery",
        "description": "Present cryptographic references in comments, unused configuration, or documentation; test distinguishing active usage.",
        "category": "EVIDENCE_VERIFICATION",
    },
    TaskFamily.T03_INCOMPATIBLE_CONSUMER: {
        "title": "Incompatible Downstream Consumer",
        "description": "A producer can migrate, but a downstream consumer cannot process the new format; test blocker detection.",
        "category": "COMPATIBILITY_ASSESSMENT",
    },
    TaskFamily.T04_UNKNOWN_PROVIDER: {
        "title": "Unknown External Provider",
        "description": "An external dependency has insufficient compatibility evidence; test avoiding unbacked assumptions.",
        "category": "COMPATIBILITY_ASSESSMENT",
    },
    TaskFamily.T05_MIGRATION_ORDERING: {
        "title": "Migration Ordering",
        "description": "Test whether the model produces a valid migration sequence respecting all dependency prerequisites.",
        "category": "MIGRATION_SEQUENCING",
    },
    TaskFamily.T06_DEPENDENCY_CYCLE: {
        "title": "Dependency Cycle",
        "description": "Introduce a circular dependency; test cycle detection over invalid topological orders.",
        "category": "DEPENDENCY_DISCOVERY",
    },
    TaskFamily.T07_MISSING_VALIDATION: {
        "title": "Missing Validation Evidence",
        "description": "A migration plan lacks required validation evidence; test refusing to claim verification without evidence.",
        "category": "EVIDENCE_VERIFICATION",
    },
    TaskFamily.T08_FAILED_INTEROP: {
        "title": "Failed Interoperability Test",
        "description": "Unit tests pass, but downstream interoperability tests fail; test blocking production promotion.",
        "category": "RISK_ASSESSMENT",
    },
    TaskFamily.T09_VALID_MIGRATION: {
        "title": "Valid Migration Control",
        "description": "Provide a scenario where migration is safe and supported; test avoiding unnecessary blockers (epistemic calibration).",
        "category": "MIGRATION_SEQUENCING",
    },
    TaskFamily.T10_CONDITIONAL_PLAN: {
        "title": "Conditional Plan Under Uncertainty",
        "description": "Allow safe preparatory actions but block irreversible cutover until evidence is obtained; test staged uncertainty reasoning.",
        "category": "RISK_ASSESSMENT",
    },
}


class GenerationConfig(BaseModel):
    """Configuration parameters for synthetic benchmark dataset generation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: int = Field(default=42, description="Random seed for deterministic generation.")
    domains: list[ArchitectureDomain] = Field(
        default_factory=lambda: list(ArchitectureDomain),
        description="Target enterprise domains to generate.",
    )
    task_families: list[TaskFamily] = Field(
        default_factory=lambda: list(TaskFamily),
        description="Target task families to generate.",
    )
    variants_per_family: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of scenario and task variants per task family.",
    )
    num_paired_cases: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of adversarial/paired benchmark cases (each produces 2 scenarios).",
    )
    num_metamorphic_cases: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of metamorphic test transformations to generate.",
    )
    default_complexity: GraphComplexity = Field(
        default=GraphComplexity.MEDIUM,
        description="Default topological complexity tier.",
    )
    output_dir: Optional[Path] = Field(
        default=None,
        description="Root output directory for generated datasets (default: datasets/generated).",
    )
