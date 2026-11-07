"""Core foundation module for PHOENIX-EVAL."""

from phoenix_eval.core.config import Settings, get_settings
from phoenix_eval.core.constants import (
    APP_NAME,
    BENCHMARK_SPEC_VERSION,
    SUPPORTED_ALGORITHMS,
)
from phoenix_eval.core.exceptions import (
    ConfigurationError,
    DatasetError,
    EvaluationError,
    ExperimentError,
    GroundTruthError,
    PhoenixEvalError,
    ProviderError,
    RegistryError,
    ScenarioError,
    SchemaValidationError,
    TaskNotFoundError,
)
from phoenix_eval.core.logging import configure_logging, get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.core.version import __version__

__all__ = [
    "APP_NAME",
    "BENCHMARK_SPEC_VERSION",
    "ConfigurationError",
    "DatasetError",
    "EvaluationError",
    "ExperimentError",
    "GroundTruthError",
    "PhoenixEvalError",
    "ProjectPaths",
    "ProviderError",
    "RegistryError",
    "ScenarioError",
    "SchemaValidationError",
    "Settings",
    "SUPPORTED_ALGORITHMS",
    "TaskNotFoundError",
    "__version__",
    "configure_logging",
    "get_logger",
    "get_paths",
    "get_settings",
]
