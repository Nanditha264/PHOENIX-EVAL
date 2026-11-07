"""Benchmark task loader utilities for discovery and batch registration."""

from pathlib import Path

from phoenix_eval.core.exceptions import TaskNotFoundError
from phoenix_eval.core.logging import get_logger
from phoenix_eval.data.serialization import read_json
from phoenix_eval.schemas.tasks import BenchmarkTask

logger = get_logger("benchmark.task_loader")


def load_task_from_file(file_path: Path) -> BenchmarkTask:
    """Load and validate a single BenchmarkTask from a JSON file."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Task file does not exist: {file_path}")

    try:
        data = read_json(file_path)
        return BenchmarkTask.model_validate(data)
    except Exception as err:
        raise TaskNotFoundError(f"Failed to parse task from '{file_path}': {err}") from err


def load_tasks_from_dir(directory: Path) -> list[BenchmarkTask]:
    """Scan a directory for all .json task files and return validated BenchmarkTask instances."""
    tasks: list[BenchmarkTask] = []
    if not directory.is_dir():
        return tasks

    for p in sorted(directory.glob("*.json")):
        try:
            task = load_task_from_file(p)
            tasks.append(task)
        except Exception as err:
            logger.warning("Skipping invalid task file '%s': %s", p, err)

    return tasks
