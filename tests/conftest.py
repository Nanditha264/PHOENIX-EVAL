"""Pytest fixtures and environment configuration for PHOENIX-EVAL tests."""

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from phoenix_eval.core.config import reset_settings
from phoenix_eval.core.paths import ProjectPaths
from phoenix_eval.schemas.compatibility import CompatibilityRecord, CompatibilityStatus
from phoenix_eval.schemas.components import ComponentType, CryptographicComponent, CryptographicRole
from phoenix_eval.schemas.dependencies import (
    DependencyCriticality,
    DependencyRelationship,
    RelationshipType,
)
from phoenix_eval.schemas.evidence import (
    EvidenceCategory,
    EvidenceRecord,
    EvidenceType,
    VerificationStatus,
)
from phoenix_eval.schemas.scenarios import (
    MigrationConstraint,
    RequiredTest,
    ScenarioModel,
    TestType,
)
from phoenix_eval.schemas.tasks import (
    BenchmarkTask,
    DifficultyLevel,
    EvaluationCriterion,
    TaskCategory,
)


@pytest.fixture(autouse=True)
def clean_settings_cache() -> Generator[None, None, None]:
    """Ensure settings cache is cleared before and after every test."""
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory and remove it after the test."""
    tmp = Path(tempfile.mkdtemp(prefix="phoenix_test_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def mock_project_paths(temp_dir: Path) -> ProjectPaths:
    """Provide isolated ProjectPaths pointing inside a temporary directory."""
    paths = ProjectPaths(
        root=temp_dir,
        config_dir=temp_dir / "config",
        datasets_dir=temp_dir / "datasets",
        scenarios_dir=temp_dir / "datasets" / "scenarios",
        tasks_dir=temp_dir / "datasets" / "tasks",
        ground_truth_dir=temp_dir / "datasets" / "ground_truth",
        fixtures_dir=temp_dir / "datasets" / "fixtures",
        results_dir=temp_dir / "results",
        raw_runs_dir=temp_dir / "results" / "raw_runs",
        processed_dir=temp_dir / "results" / "processed",
        reports_dir=temp_dir / "results" / "reports",
        docs_dir=temp_dir / "docs",
        tests_dir=temp_dir / "tests",
    )
    paths.ensure_directories()
    return paths


@pytest.fixture
def sample_component() -> CryptographicComponent:
    """Fixture providing a standard valid CryptographicComponent."""
    return CryptographicComponent(
        component_id="comp-auth-svc-01",
        component_name="Auth Service",
        component_type=ComponentType.MICROSERVICE,
        cryptographic_role=CryptographicRole.AUTHENTICATION_TOKEN,
        description="Authenticates users with RSA tokens.",
        technology="Java 17 / BouncyCastle 1.70",
        current_algorithms=["RSA-2048", "SHA-256"],
        evidence_references=["evid-auth-scan-01"],
        metadata={"tier": "1"},
    )


@pytest.fixture
def sample_evidence() -> EvidenceRecord:
    """Fixture providing a standard valid EvidenceRecord."""
    return EvidenceRecord(
        evidence_id="evid-auth-scan-01",
        evidence_type=EvidenceType.STATIC_CODE_ANALYSIS,
        source="Static Scan Tool v1.0",
        description="Found RSA-2048 key usage in TokenSigner.java",
        observed_value="RSA-2048",
        confidence=1.0,
        provenance="git:commit-abcdef",
        verification_status=VerificationStatus.VERIFIED,
        evidence_category=EvidenceCategory.OBSERVED,
    )


@pytest.fixture
def sample_scenario(
    sample_component: CryptographicComponent, sample_evidence: EvidenceRecord
) -> ScenarioModel:
    """Fixture providing a valid interconnected ScenarioModel."""
    comp2 = CryptographicComponent(
        component_id="comp-db-02",
        component_name="Core DB",
        component_type=ComponentType.DATABASE,
        cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
        description="Ledger database encrypted at rest.",
        technology="PostgreSQL 15 / AES-256-GCM",
        current_algorithms=["AES-256-GCM"],
        evidence_references=[],
    )

    edge = DependencyRelationship(
        edge_id="edge-auth-to-db-01",
        source_component_id=sample_component.component_id,
        target_component_id=comp2.component_id,
        relationship_type=RelationshipType.STORES_DATA_IN,
        evidence_references=[sample_evidence.evidence_id],
        confidence=1.0,
        description="Auth stores sessions in DB.",
        criticality=DependencyCriticality.HIGH,
    )

    compat1 = CompatibilityRecord(
        component_id=sample_component.component_id,
        proposed_target="ML-DSA-65",
        status=CompatibilityStatus.UNKNOWN,
        evidence_references=[],
        reason="Requires JVM library testing.",
        assessment_source="Team Review",
    )

    compat2 = CompatibilityRecord(
        component_id=comp2.component_id,
        proposed_target="AES-256-GCM",
        status=CompatibilityStatus.SUPPORTED,
        evidence_references=[],
        reason="AES-256 is quantum-safe.",
        assessment_source="NIST Guidelines",
    )

    return ScenarioModel(
        scenario_id="scen-test-001",
        scenario_name="Test Enterprise Architecture",
        description="A minimal test scenario for unit tests.",
        system_components=[sample_component, comp2],
        dependencies=[edge],
        compatibility_records=[compat1, compat2],
        evidence_records=[sample_evidence],
        migration_constraints=[
            MigrationConstraint(
                constraint_id="cnstr-uptime-01",
                constraint_type="NO_DOWNTIME",
                description="Zero downtime required.",
                affected_components=[comp2.component_id],
            )
        ],
        required_tests=[
            RequiredTest(
                test_id="test-integ-01",
                test_type=TestType.INTEROPERABILITY,
                description="Verify connection handshake.",
                target_components=[sample_component.component_id, comp2.component_id],
            )
        ],
    )


@pytest.fixture
def sample_task() -> BenchmarkTask:
    """Fixture providing a valid BenchmarkTask."""
    return BenchmarkTask(
        task_id="task-test-seq-001",
        task_name="Test Migration Sequencing Task",
        task_category=TaskCategory.MIGRATION_SEQUENCING,
        difficulty=DifficultyLevel.INTERMEDIATE,
        description="Formulate valid migration sequence.",
        scenario_reference="scen-test-001",
        task_instructions="Analyze dependencies and provide wave order.",
        expected_output_schema={"type": "object"},
        evaluation_criteria=[
            EvaluationCriterion(
                criterion_id="crit-blocker-01",
                name="Blocker Detection",
                description="Must identify unknown compatibility.",
                weight=50.0,
                is_safety_critical=True,
            ),
            EvaluationCriterion(
                criterion_id="crit-order-02",
                name="Sequence Order",
                description="Must maintain correct order.",
                weight=50.0,
                is_safety_critical=False,
            ),
        ],
        ground_truth_reference="gt-test-seq-001",
        tags=["test", "unit"],
        version="1.0.0",
    )
