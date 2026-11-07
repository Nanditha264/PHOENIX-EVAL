"""Scenario loading utilities for discovery and batch registration."""

from pathlib import Path

from phoenix_eval.core.exceptions import ScenarioError
from phoenix_eval.core.logging import get_logger
from phoenix_eval.data.serialization import read_json
from phoenix_eval.schemas.scenarios import ScenarioModel

logger = get_logger("benchmark.scenario_loader")


def load_scenario_from_file(file_path: Path) -> ScenarioModel:
    """Load and validate a single ScenarioModel from a JSON file."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Scenario file does not exist: {file_path}")

    try:
        data = read_json(file_path)
        return ScenarioModel.model_validate(data)
    except Exception as err:
        raise ScenarioError(f"Failed to parse scenario from '{file_path}': {err}") from err


def load_scenarios_from_dir(directory: Path) -> list[ScenarioModel]:
    """Scan a directory for all .json scenario files and return validated ScenarioModel instances."""
    scenarios: list[ScenarioModel] = []
    if not directory.is_dir():
        return scenarios

    for p in sorted(directory.glob("*.json")):
        try:
            scenario = load_scenario_from_file(p)
            scenarios.append(scenario)
        except Exception as err:
            logger.warning("Skipping invalid scenario file '%s': %s", p, err)

    return scenarios
