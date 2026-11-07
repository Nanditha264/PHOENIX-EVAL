"""Unit tests for deterministic serialization and file parsing."""

from pathlib import Path

import pytest

from phoenix_eval.core.exceptions import SerializationError
from phoenix_eval.data.serialization import (
    read_json,
    read_jsonl,
    serialize_json,
    write_json,
    write_jsonl,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask
from phoenix_eval.utils.hashing import compute_dict_hash, compute_file_hash, compute_sha256


def test_json_round_trip_scenario(sample_scenario: ScenarioModel, temp_dir: Path) -> None:
    """Verify that a ScenarioModel serializes and deserializes cleanly without data loss."""
    target_path = temp_dir / "scenario.json"
    write_json(target_path, sample_scenario)

    data = read_json(target_path)
    restored = ScenarioModel.model_validate(data)

    assert restored.scenario_id == sample_scenario.scenario_id
    assert len(restored.system_components) == len(sample_scenario.system_components)
    assert len(restored.dependencies) == len(sample_scenario.dependencies)


def test_json_deterministic_formatting() -> None:
    """Verify that dictionary keys are sorted deterministically."""
    data1 = {"zebra": 1, "apple": 2, "mango": 3}
    data2 = {"mango": 3, "apple": 2, "zebra": 1}

    str1 = serialize_json(data1)
    str2 = serialize_json(data2)

    assert str1 == str2
    assert compute_dict_hash(data1) == compute_dict_hash(data2)


def test_jsonl_write_and_read(sample_task: BenchmarkTask, temp_dir: Path) -> None:
    """Verify JSON Lines writing and reading of Pydantic models."""
    jsonl_path = temp_dir / "tasks.jsonl"
    write_jsonl(jsonl_path, [sample_task, sample_task])

    items = read_jsonl(jsonl_path)
    assert len(items) == 2
    assert items[0]["task_id"] == sample_task.task_id
    assert items[1]["task_id"] == sample_task.task_id


def test_malformed_json_raises_serialization_error(temp_dir: Path) -> None:
    """Verify that malformed JSON files raise SerializationError with clear context."""
    bad_file = temp_dir / "bad.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json content: 123, }")

    with pytest.raises(SerializationError, match="Invalid JSON"):
        read_json(bad_file)


def test_file_hash_calculation(temp_dir: Path) -> None:
    """Verify chunked SHA-256 calculation for file integrity verification."""
    file_path = temp_dir / "test_file.txt"
    content = "PHOENIX-EVAL cryptographic verification artifact"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    expected_hash = compute_sha256(content)
    actual_hash = compute_file_hash(file_path)
    assert actual_hash == expected_hash
