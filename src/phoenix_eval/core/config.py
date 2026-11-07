"""Centralized configuration management for PHOENIX-EVAL using Pydantic Settings."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from phoenix_eval.core.constants import APP_NAME
from phoenix_eval.core.exceptions import ConfigurationError
from phoenix_eval.core.paths import find_project_root, get_paths
from phoenix_eval.core.version import __version__


class ProviderSettings(BaseSettings):
    """Model provider execution parameters and credentials."""

    model_config = SettingsConfigDict(
        env_prefix="PHOENIX_PROVIDER_",
        extra="ignore",
    )

    default_provider: str = Field(
        default="mock",
        description="Default model provider to use ('mock', 'openai', 'anthropic', 'google').",
    )
    default_model: str = Field(
        default="mock-model-v1",
        description="Default model identifier to query.",
    )
    openai_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Optional API key for OpenAI provider.",
    )
    anthropic_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Optional API key for Anthropic provider.",
    )
    google_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Optional API key for Google provider.",
    )


class ExperimentSettings(BaseSettings):
    """Default parameters for benchmark runs and evaluations."""

    model_config = SettingsConfigDict(
        env_prefix="PHOENIX_EXPERIMENT_",
        extra="ignore",
    )

    number_of_trials: int = Field(default=1, ge=1, description="Default number of repeated trials.")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Sampling temperature.")
    max_output_tokens: int = Field(default=2048, ge=64, description="Max response tokens.")


class Settings(BaseSettings):
    """Global configuration settings for PHOENIX-EVAL."""

    model_config = SettingsConfigDict(
        env_prefix="PHOENIX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application identity
    app_name: str = Field(default=APP_NAME, description="Application name.")
    app_version: str = Field(default=__version__, description="PHOENIX-EVAL version.")
    environment: Literal["development", "testing", "production"] = Field(
        default="development",
        description="Runtime environment.",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Application logging level.",
    )

    # Directories
    project_root: Path = Field(
        default_factory=find_project_root,
        description="Root directory of the project.",
    )
    datasets_dir: Path = Field(
        default_factory=lambda: get_paths().datasets_dir,
        description="Directory containing benchmark datasets.",
    )
    results_dir: Path = Field(
        default_factory=lambda: get_paths().results_dir,
        description="Directory for saving benchmark execution results.",
    )

    # Execution controls
    random_seed: int = Field(default=42, description="Random seed for reproducibility.")
    request_timeout: float = Field(
        default=60.0,
        gt=0.0,
        description="Model request timeout in seconds.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum request retry attempts.",
    )
    output_format: Literal["json", "jsonl", "csv"] = Field(
        default="json",
        description="Default serialization format.",
    )

    # Sub-configurations
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    experiment: ExperimentSettings = Field(default_factory=ExperimentSettings)

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: Any) -> str:
        if isinstance(v, str):
            v_upper = v.upper()
            valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            if v_upper not in valid:
                raise ValueError(f"Invalid log level '{v}'. Must be one of {valid}")
            return v_upper
        return "INFO"

    @field_validator("request_timeout", mode="before")
    @classmethod
    def validate_timeout(cls, v: Any) -> float:
        try:
            val = float(v)
            if val <= 0:
                raise ValueError("request_timeout must be greater than zero")
            return val
        except (TypeError, ValueError) as err:
            raise ValueError(f"Invalid request_timeout: {err}") from err

    @field_validator("random_seed", mode="before")
    @classmethod
    def validate_seed(cls, v: Any) -> int:
        try:
            return int(v)
        except (TypeError, ValueError) as err:
            raise ValueError(f"Invalid random_seed: {err}") from err

    def model_post_init(self, __context: Any) -> None:
        """Validate post initialization requirements."""
        if not self.datasets_dir.is_absolute():
            self.datasets_dir = (self.project_root / self.datasets_dir).resolve()
        if not self.results_dir.is_absolute():
            self.results_dir = (self.project_root / self.results_dir).resolve()


def load_settings_from_yaml(yaml_path: Optional[Path] = None) -> dict[str, Any]:
    """Load settings dictionary from YAML configuration file if it exists."""
    if yaml_path is None:
        yaml_path = find_project_root() / "config" / "settings.yaml"

    if yaml_path.exists():
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if not isinstance(data, dict):
                    raise ConfigurationError(
                        f"Config file at {yaml_path} must be a valid YAML mapping."
                    )
                return data
        except yaml.YAMLError as err:
            raise ConfigurationError(f"Failed to parse YAML config: {err}") from err
    return {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve the cached singleton application settings.

    Precedence order:
    1. Environment variables (PHOENIX_*)
    2. .env file
    3. config/settings.yaml defaults
    4. Model field defaults
    """
    try:
        yaml_data = load_settings_from_yaml()
        init_kwargs: dict[str, Any] = {}

        # Only fallback to YAML if environment variable is not explicitly defined in os.environ
        if "app_name" in yaml_data and "PHOENIX_APP_NAME" not in os.environ:
            init_kwargs["app_name"] = yaml_data["app_name"]
        if "environment" in yaml_data and "PHOENIX_ENVIRONMENT" not in os.environ:
            init_kwargs["environment"] = yaml_data["environment"]
        if "execution" in yaml_data:
            exec_data = yaml_data["execution"]
            if "random_seed" in exec_data and "PHOENIX_RANDOM_SEED" not in os.environ:
                init_kwargs["random_seed"] = exec_data["random_seed"]
            if "request_timeout" in exec_data and "PHOENIX_REQUEST_TIMEOUT" not in os.environ:
                init_kwargs["request_timeout"] = exec_data["request_timeout"]
            if "max_retries" in exec_data and "PHOENIX_MAX_RETRIES" not in os.environ:
                init_kwargs["max_retries"] = exec_data["max_retries"]
            if "output_format" in exec_data and "PHOENIX_OUTPUT_FORMAT" not in os.environ:
                init_kwargs["output_format"] = exec_data["output_format"]
        if (
            "logging" in yaml_data
            and "level" in yaml_data["logging"]
            and "PHOENIX_LOG_LEVEL" not in os.environ
        ):
            init_kwargs["log_level"] = yaml_data["logging"]["level"]

        return Settings(**init_kwargs)
    except Exception as err:
        raise ConfigurationError(f"Configuration initialization failed: {err}") from err


def reset_settings() -> None:
    """Clear cached settings (useful during unit tests)."""
    get_settings.cache_clear()
