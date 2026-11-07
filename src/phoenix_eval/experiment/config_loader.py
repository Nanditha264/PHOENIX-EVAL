"""Experiment configuration loader, task resolver, and pre-flight validation engine."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import ValidationError

from phoenix_eval.core.exceptions import (
    ConfigurationError,
    EntityNotFoundError,
    ProviderAuthenticationError,
    TaskNotFoundError,
)
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.repository import TaskRepository
from phoenix_eval.data.serialization import read_json
from phoenix_eval.providers.model_registry import ModelRegistry, get_model_registry
from phoenix_eval.schemas.experiments import ExperimentConfig


def load_experiment_config(config_path: Path) -> ExperimentConfig:
    """Load and validate an experiment configuration file from YAML or JSON format.

    Args:
        config_path: Path to .yaml, .yml, or .json configuration file.

    Returns:
        Validated ExperimentConfig model instance.

    Raises:
        FileNotFoundError: If configuration file does not exist.
        ConfigurationError: If parsing or Pydantic validation fails.
    """
    if not config_path.is_file():
        raise FileNotFoundError(f"Experiment configuration file not found at: {config_path}")

    try:
        if config_path.suffix.lower() in (".yaml", ".yml"):
            with open(config_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
        else:
            raw_data = read_json(config_path)

        if not isinstance(raw_data, dict):
            raise ConfigurationError(
                f"Configuration file at {config_path} must be a dictionary/mapping."
            )

        # Allow loading directly from an experiment manifest file
        if "config" in raw_data and isinstance(raw_data["config"], dict):
            raw_data = raw_data["config"]

        return ExperimentConfig.model_validate(raw_data)
    except ValidationError as err:
        raise ConfigurationError(
            f"Experiment configuration schema validation error in '{config_path}': {err}"
        ) from err
    except yaml.YAMLError as err:
        raise ConfigurationError(
            f"Failed to parse YAML configuration '{config_path}': {err}"
        ) from err
    except Exception as err:
        raise ConfigurationError(
            f"Error loading experiment configuration '{config_path}': {err}"
        ) from err


class ExperimentValidator:
    """Pre-flight validator checking task availability, model registration, and credentials."""

    def __init__(
        self,
        paths: Optional[ProjectPaths] = None,
        registry: Optional[ModelRegistry] = None,
    ) -> None:
        self.paths = paths or get_paths()
        self.model_registry = registry or get_model_registry()

        # Task repositories (search generated tasks first, then seed tasks)
        self.task_repos = [
            TaskRepository(self.paths.generated_tasks_dir),
            TaskRepository(self.paths.tasks_dir),
        ]

    def resolve_task_ids(self, selected_tasks: list[str]) -> list[str]:
        """Expand wildcard or filter patterns (e.g. 'all', 'family:T01') into concrete task IDs."""
        all_task_ids: set[str] = set()
        for repo in self.task_repos:
            all_task_ids.update(repo.list_task_ids())

        resolved: set[str] = set()
        for item in selected_tasks:
            pattern = item.strip()
            if pattern == "all":
                resolved.update(all_task_ids)
            elif pattern.startswith("family:"):
                fam_code = pattern.split(":", 1)[1].strip().lower()
                matching = {
                    t
                    for t in all_task_ids
                    if f"-{fam_code}-" in t.lower() or t.lower().startswith(f"task-{fam_code}-")
                }
                if not matching:
                    raise TaskNotFoundError(f"No tasks matched family filter '{pattern}'.")
                resolved.update(matching)
            elif pattern.startswith("tier:") or pattern.startswith("difficulty:"):
                tier = pattern.split(":", 1)[1].strip().lower()
                matching = set()
                for tid in all_task_ids:
                    task = self.get_task(tid)
                    if task and task.difficulty.value.lower() == tier:
                        matching.add(tid)
                if not matching:
                    raise TaskNotFoundError(f"No tasks matched difficulty filter '{pattern}'.")
                resolved.update(matching)
            else:
                # Direct task ID
                if pattern not in all_task_ids:
                    raise TaskNotFoundError(
                        f"Specified task '{pattern}' not found in benchmark repositories."
                    )
                resolved.add(pattern)

        if not resolved:
            raise TaskNotFoundError("Task resolution resulted in an empty task list.")

        return sorted(resolved)

    def get_task(self, task_id: str) -> Optional[Any]:
        """Retrieve task model from available repositories."""
        for repo in self.task_repos:
            try:
                return repo.load_task(task_id)
            except Exception:
                continue
        return None

    def validate_pre_flight(self, config: ExperimentConfig) -> dict[str, Any]:
        """Perform comprehensive pre-flight verification of experiment configuration.

        Validates:
        1. Model registrations and provider types.
        2. Credential availability for real providers (fails fast; never falls back to mock).
        3. Task existence and expands any filters.
        4. Mode consistency (mock vs real).

        Returns:
            Dictionary of resolved execution parameters (resolved_tasks, models, mode).
        """
        # 1. Resolve and validate tasks
        resolved_tasks = self.resolve_task_ids(config.selected_tasks)

        # 2. Validate models
        model_configs = []
        has_real_model = False
        has_mock_model = False

        for model_id in config.selected_models:
            if not self.model_registry.has_model(model_id):
                raise EntityNotFoundError(
                    f"Selected model '{model_id}' is not registered in ModelRegistry. "
                    f"Available: {[m.model_id for m in self.model_registry.list_models()]}"
                )
            m_cfg = self.model_registry.get_model_config(model_id)
            model_configs.append(m_cfg)

            if m_cfg.is_mock:
                has_mock_model = True
            else:
                has_real_model = True

        # 3. Check mode constraints and enforce mock/real separation
        if has_mock_model and has_real_model and not config.allow_mixed_mode:
            raise ConfigurationError(
                f"Experiment '{config.experiment_id}' contains both mock and real models "
                f"({[m.model_id for m in model_configs]}). "
                "Running mixed mock and real models in the same campaign is prohibited by default. "
                "Set 'allow_mixed_mode: true' in your experiment configuration to explicitly permit this."
            )

        if config.mode == "mock" and has_real_model:
            raise ConfigurationError(
                f"Experiment '{config.experiment_id}' is configured with mode='mock', "
                f"but contains real models: {[m.model_id for m in model_configs if not m.is_mock]}"
            )

        if config.mode == "real" and has_mock_model:
            raise ConfigurationError(
                f"Experiment '{config.experiment_id}' is configured with mode='real', "
                f"but contains mock models: {[m.model_id for m in model_configs if m.is_mock]}"
            )

        if config.mode == "mixed" and not config.allow_mixed_mode:
            raise ConfigurationError(
                f"Experiment '{config.experiment_id}' specifies mode='mixed' but 'allow_mixed_mode' is False. "
                "Set 'allow_mixed_mode: true' to evaluate mixed mock and real campaigns."
            )

        # 4. Check credentials for real providers
        missing_credentials: list[str] = []
        for m_cfg in model_configs:
            if not m_cfg.is_mock:
                env_var = m_cfg.api_key_env_var
                val = os.environ.get(env_var, "").strip()
                if not val:
                    missing_credentials.append(
                        f"Model '{m_cfg.model_id}' requires env var '{env_var}'"
                    )

        if missing_credentials:
            raise ProviderAuthenticationError(
                "Pre-flight credential verification failed:\n"
                + "\n".join(f"  - {c}" for c in missing_credentials)
                + "\nPlease set required environment variables prior to running real provider experiments."
            )

        if has_mock_model and has_real_model:
            effective_mode = "mixed"
        elif has_mock_model:
            effective_mode = "mock"
        else:
            effective_mode = "real"

        return {
            "resolved_tasks": resolved_tasks,
            "models": [m.model_id for m in model_configs],
            "total_runs": len(resolved_tasks) * len(model_configs) * config.number_of_trials,
            "mode": effective_mode,
        }
