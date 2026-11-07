"""Regression tests for Phase 5.1 Defect 2: Mandatory dataset fingerprint validation."""

from pathlib import Path

from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.schemas import IngestionRecordStatus
from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json, write_json


def test_valid_manifest_fingerprints_succeeds(tmp_path: Path) -> None:
    """Experiment with exact matching 5-field fingerprints passes as VALID."""
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-phase5-1-001")

    assert data.ingestion_report.import_status == IngestionRecordStatus.VALID
    assert data.ingestion_report.dataset_fingerprint_match is True
    assert data.ingestion_report.recorded_dataset_fingerprint is not None
    assert data.ingestion_report.recorded_model_visible_fingerprint is not None
    assert data.ingestion_report.recorded_evaluator_fingerprint is not None
    assert data.ingestion_report.fingerprint_algorithm == "sha256-canonical-json-v1"
    assert data.ingestion_report.dataset_manifest_version == "1.0.0"


def test_missing_fingerprint_classified_as_legacy_unverifiable(tmp_path: Path) -> None:
    """Missing any fingerprint field causes classification as LEGACY_UNVERIFIABLE."""
    paths = get_paths()
    src_dir = paths.results_dir / "experiments" / "exp-mock-phase5-1-001"
    test_exp_dir = tmp_path / "exp-missing-fp"
    test_exp_dir.mkdir(parents=True)

    # Copy files
    manifest_dict = read_json(src_dir / "experiment_manifest.json")
    manifest_dict["dataset_fingerprint"] = None
    manifest_dict["model_visible_dataset_fingerprint"] = None
    manifest_dict["evaluator_dataset_fingerprint"] = None

    write_json(test_exp_dir / "experiment_manifest.json", manifest_dict)

    # Symlink or copy raw_responses & evaluations
    import shutil

    shutil.copytree(src_dir / "raw_responses", test_exp_dir / "raw_responses")
    shutil.copytree(src_dir / "evaluations", test_exp_dir / "evaluations")

    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment(test_exp_dir)

    assert data.ingestion_report.import_status == IngestionRecordStatus.LEGACY_UNVERIFIABLE
    assert data.ingestion_report.dataset_fingerprint_match is False
    issue_types = [issue.issue_type for issue in data.ingestion_report.issues]
    assert "INVALID_MISSING_DATASET_FINGERPRINT" in issue_types


def test_mismatched_fingerprint_causes_warning_and_issue(tmp_path: Path) -> None:
    """Mismatched dataset fingerprint creates INVALID_DATASET_FINGERPRINT_MISMATCH and warning status."""
    paths = get_paths()
    src_dir = paths.results_dir / "experiments" / "exp-mock-phase5-1-001"
    test_exp_dir = tmp_path / "exp-mismatch-fp"
    test_exp_dir.mkdir(parents=True)

    manifest_dict = read_json(src_dir / "experiment_manifest.json")
    manifest_dict["dataset_fingerprint"] = "0" * 64

    write_json(test_exp_dir / "experiment_manifest.json", manifest_dict)

    import shutil

    shutil.copytree(src_dir / "raw_responses", test_exp_dir / "raw_responses")
    shutil.copytree(src_dir / "evaluations", test_exp_dir / "evaluations")

    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment(test_exp_dir)

    assert data.ingestion_report.import_status == IngestionRecordStatus.VALID_WITH_WARNINGS
    assert data.ingestion_report.dataset_fingerprint_match is False
    issue_types = [issue.issue_type for issue in data.ingestion_report.issues]
    assert "INVALID_DATASET_FINGERPRINT_MISMATCH" in issue_types
