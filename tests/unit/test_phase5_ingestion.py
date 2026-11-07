"""Unit tests for Phase 5 experiment ingestion and integrity verification."""

import shutil

from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.schemas import IngestionRecordStatus
from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json, write_json


def test_ingest_valid_experiment(tmp_path):
    validator = ExperimentIngestionValidator()
    # Ingest validated phase 5.1 mock comparison experiment
    data = validator.ingest_experiment("exp-mock-phase5-1-001")
    assert data.manifest.experiment_id == "exp-mock-phase5-1-001"
    assert data.is_mock is True
    assert len(data.valid_runs) == 12
    assert len(data.failed_runs) == 0
    assert len(data.corrupted_runs) == 0
    assert data.ingestion_report.import_status == IngestionRecordStatus.VALID
    assert data.ingestion_report.completed_runs == 12


def test_ingest_historical_experiment_classified_legacy_unverifiable():
    validator = ExperimentIngestionValidator()
    # Historical exp-mock-comparison-001 lacks fingerprints and is classified LEGACY_UNVERIFIABLE
    data = validator.ingest_experiment("exp-mock-comparison-001")
    assert data.manifest.experiment_id == "exp-mock-comparison-001"
    assert data.ingestion_report.import_status == IngestionRecordStatus.LEGACY_UNVERIFIABLE
    assert data.ingestion_report.dataset_fingerprint_match is False


def test_ingestion_detects_missing_raw_response(tmp_path):
    # Clone exp-mock-comparison-001 to tmp_path
    paths = get_paths()
    src_exp = paths.results_dir / "experiments" / "exp-mock-comparison-001"
    dst_exp = tmp_path / "exp-corrupt-raw"
    shutil.copytree(src_exp, dst_exp)

    # Delete one raw response
    raw_files = list((dst_exp / "raw_responses").glob("*.json"))
    assert len(raw_files) > 0
    raw_files[0].unlink()

    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment(dst_exp)
    assert len(data.corrupted_runs) == 1
    assert data.ingestion_report.missing_raw_responses_count == 1
    assert data.ingestion_report.import_status == IngestionRecordStatus.CORRUPTED
    assert any(iss.issue_type == "MISSING_RAW_RESPONSE" for iss in data.ingestion_report.issues)


def test_ingestion_detects_hash_mismatch(tmp_path):
    paths = get_paths()
    src_exp = paths.results_dir / "experiments" / "exp-mock-comparison-001"
    dst_exp = tmp_path / "exp-corrupt-hash"
    shutil.copytree(src_exp, dst_exp)

    # Modify raw response file content to cause SHA-256 hash mismatch
    raw_files = list((dst_exp / "raw_responses").glob("*.json"))
    raw_path = raw_files[0]
    content = read_json(raw_path)
    content["raw_response"] = "ALTERED_MALICIOUS_PAYLOAD"
    write_json(raw_path, content)

    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment(dst_exp)
    assert len(data.corrupted_runs) == 1
    assert data.ingestion_report.response_hash_mismatches_count == 1
    assert data.ingestion_report.import_status == IngestionRecordStatus.CORRUPTED
    assert any(iss.issue_type == "RESPONSE_HASH_MISMATCH" for iss in data.ingestion_report.issues)


def test_ingestion_detects_missing_evaluation_report(tmp_path):
    paths = get_paths()
    src_exp = paths.results_dir / "experiments" / "exp-mock-comparison-001"
    dst_exp = tmp_path / "exp-corrupt-eval"
    shutil.copytree(src_exp, dst_exp)

    # Delete an evaluation report
    eval_files = list((dst_exp / "evaluations").glob("*.json"))
    eval_files[0].unlink()

    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment(dst_exp)
    assert len(data.corrupted_runs) == 1
    assert data.ingestion_report.missing_eval_reports_count == 1
    assert any(iss.issue_type == "MISSING_EVAL_REPORT" for iss in data.ingestion_report.issues)


def test_ingestion_failed_runs_partitioned(tmp_path):
    paths = get_paths()
    src_exp = paths.results_dir / "experiments" / "exp-mock-comparison-001"
    dst_exp = tmp_path / "exp-failed-run"
    shutil.copytree(src_exp, dst_exp)

    # Mark one run as failed due to provider timeout
    manifest_data = read_json(dst_exp / "experiment_manifest.json")
    manifest_data["runs"][0]["execution_status"] = "FAILED"
    manifest_data["runs"][0]["error_type"] = "ProviderTimeoutError"
    write_json(dst_exp / "experiment_manifest.json", manifest_data)

    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment(dst_exp)
    assert len(data.valid_runs) == 7
    assert len(data.failed_runs) == 1
    assert data.failed_runs[0].error_type == "ProviderTimeoutError"
