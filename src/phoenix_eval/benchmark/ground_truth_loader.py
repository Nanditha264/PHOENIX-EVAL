"""Evaluator-only ground truth loader functions.

ARCHITECTURAL BOUNDARY:
This module is intended solely for evaluator execution. Model execution
pipelines, prompt builders, and benchmark registries do not use this module.
"""

from pathlib import Path
from typing import Any

from phoenix_eval.core.exceptions import GroundTruthError
from phoenix_eval.core.logging import get_logger
from phoenix_eval.data.serialization import read_json

logger = get_logger("benchmark.ground_truth_loader")


def load_ground_truth_from_file(file_path: Path) -> dict[str, Any]:
    """Load ground-truth artifact from file for evaluator execution.

    Args:
        file_path: Path to ground truth JSON file.

    Raises:
        FileNotFoundError: If file does not exist.
        GroundTruthError: If reading or JSON parsing fails.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"Ground truth file does not exist: {file_path}")

    try:
        data = read_json(file_path)
        if not isinstance(data, dict):
            raise GroundTruthError(f"Ground truth in '{file_path}' must be a JSON object.")
        return data
    except Exception as err:
        raise GroundTruthError(f"Failed to parse ground truth from '{file_path}': {err}") from err


def load_ground_truths_from_dir(directory: Path) -> dict[str, dict[str, Any]]:
    """Scan directory and load all ground truth JSON files into a dictionary keyed by ID."""
    ground_truths: dict[str, dict[str, Any]] = {}
    if not directory.is_dir():
        return ground_truths

    for p in sorted(directory.glob("*.json")):
        try:
            gt_data = load_ground_truth_from_file(p)
            gt_id = gt_data.get("ground_truth_id") or p.stem
            ground_truths[gt_id] = gt_data
        except Exception as err:
            logger.warning("Skipping invalid ground truth file '%s': %s", p, err)

    return ground_truths
