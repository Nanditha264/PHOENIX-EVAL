"""Unit tests for Phase 4.2 Dataset Content Fingerprinting and Resume Validation."""

import json
from pathlib import Path

import pytest

from phoenix_eval.benchmark.fingerprint import (
    canonical_json_bytes,
    compute_dataset_fingerprints,
    compute_file_canonical_hash,
)
from phoenix_eval.core.exceptions import ExperimentError
from phoenix_eval.core.paths import get_paths
from phoenix_eval.experiment.runner import ExperimentRunner
from phoenix_eval.schemas.experiments import ExperimentConfig, ExperimentLifecycleStatus


def test_canonical_json_bytes_is_deterministic() -> None:
    """Verify canonical JSON serializer is key-order independent and compact."""
    dict_a = {"z": 1, "a": {"b": 2, "a": 3}}
    dict_b = {"a": {"a": 3, "b": 2}, "z": 1}

    bytes_a = canonical_json_bytes(dict_a)
    bytes_b = canonical_json_bytes(dict_b)

    assert bytes_a == bytes_b
    assert b" " not in bytes_a  # Minimal separators without extra spaces


def test_compute_dataset_fingerprints_stability_and_separation() -> None:
    """Verify compute_dataset_fingerprints produces identical hashes and separates visible from GT."""
    paths = get_paths()
    fp1 = compute_dataset_fingerprints(paths)
    fp2 = compute_dataset_fingerprints(paths)

    # Determinism across calls
    assert fp1.dataset_fingerprint == fp2.dataset_fingerprint
    assert fp1.model_visible_dataset_fingerprint == fp2.model_visible_dataset_fingerprint
    assert fp1.evaluator_dataset_fingerprint == fp2.evaluator_dataset_fingerprint
    assert fp1.fingerprint_algorithm == "sha256-canonical-json-v1"

    # Evaluator-only separation: Ground truth fingerprint is distinct from model-visible fingerprint
    assert fp1.model_visible_dataset_fingerprint != fp1.evaluator_dataset_fingerprint
    assert fp1.model_visible_files_count > 0
    assert fp1.evaluator_files_count > 0


def test_fingerprint_sensitivity_to_modifications(tmp_path: Path) -> None:
    """Verify altering a file immediately changes the computed fingerprint."""
    file_a = tmp_path / "task-01.json"
    file_a.write_text(json.dumps({"task_id": "task-01", "name": "Initial"}), encoding="utf-8")

    hash_initial = compute_file_canonical_hash(file_a)

    file_a.write_text(json.dumps({"task_id": "task-01", "name": "Modified"}), encoding="utf-8")
    hash_modified = compute_file_canonical_hash(file_a)

    assert hash_initial != hash_modified


def test_experiment_manifest_records_complete_fingerprint_bundle(tmp_path: Path) -> None:
    """Verify ExperimentManifest captures all required dataset fingerprint metadata."""
    exp_dir = tmp_path / "exp_fingerprint"
    config = ExperimentConfig(
        experiment_id="exp-fp-001",
        experiment_name="Fingerprint Recording Campaign",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-seq-pqc-001"],
        number_of_trials=1,
        output_dir=str(exp_dir),
        mode="mock",
    )

    runner = ExperimentRunner(config=config)
    manifest = runner.run()

    assert manifest.dataset_fingerprint is not None
    assert len(manifest.dataset_fingerprint) == 64  # SHA-256
    assert manifest.model_visible_dataset_fingerprint is not None
    assert manifest.evaluator_dataset_fingerprint is not None
    assert manifest.fingerprint_algorithm == "sha256-canonical-json-v1"
    assert manifest.fingerprint_created_at is not None


def test_resume_rejects_fingerprint_mismatch(tmp_path: Path) -> None:
    """Verify runner pre-flight refuses to resume an experiment if dataset fingerprint mismatches."""
    exp_dir = tmp_path / "exp_resume_drift"
    config = ExperimentConfig(
        experiment_id="exp-drift-001",
        experiment_name="Fingerprint Drift Test",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-seq-pqc-001"],
        number_of_trials=1,
        output_dir=str(exp_dir),
        mode="mock",
        resume=True,
        ignore_dataset_mismatch=False,
    )

    runner = ExperimentRunner(config=config)
    manifest = runner.run()
    assert manifest.execution_status == ExperimentLifecycleStatus.COMPLETED

    # Now tamper with recorded fingerprint in manifest to simulate dataset drift
    manifest_path = exp_dir / "experiment_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["dataset_fingerprint"] = "0000000000000000000000000000000000000000000000000000000000000000"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    # Resuming against altered fingerprint must raise ExperimentError
    runner_resumed = ExperimentRunner(config=config)
    with pytest.raises(ExperimentError, match="Dataset fingerprint mismatch"):
        runner_resumed.run()


def test_resume_allows_mismatch_with_override(tmp_path: Path) -> None:
    """Verify runner permits resuming despite fingerprint mismatch when ignore_dataset_mismatch=True."""
    exp_dir = tmp_path / "exp_resume_override"
    config = ExperimentConfig(
        experiment_id="exp-override-001",
        experiment_name="Fingerprint Drift Override Test",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-seq-pqc-001"],
        number_of_trials=1,
        output_dir=str(exp_dir),
        mode="mock",
        resume=True,
        ignore_dataset_mismatch=True,  # Explicit opt-in
    )

    runner = ExperimentRunner(config=config)
    manifest = runner.run()
    assert manifest.execution_status == ExperimentLifecycleStatus.COMPLETED

    # Alter recorded fingerprint in manifest
    manifest_path = exp_dir / "experiment_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["dataset_fingerprint"] = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    # Resuming with ignore_dataset_mismatch=True must succeed
    runner_resumed = ExperimentRunner(config=config)
    resumed_manifest = runner_resumed.run()
    assert resumed_manifest.execution_status == ExperimentLifecycleStatus.COMPLETED
