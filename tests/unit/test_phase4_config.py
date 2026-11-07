"""Unit tests for Phase 4 experiment configuration, task resolution, and pre-flight validation."""

import pytest
from pydantic import ValidationError

from phoenix_eval.core.exceptions import (
    ConfigurationError,
    EntityNotFoundError,
    ProviderAuthenticationError,
    TaskNotFoundError,
)
from phoenix_eval.experiment.config_loader import ExperimentValidator
from phoenix_eval.providers.model_registry import ModelRegistry
from phoenix_eval.schemas.experiments import ExperimentConfig


def test_valid_experiment_config_instantiation() -> None:
    config = ExperimentConfig(
        experiment_id="exp-test-001",
        experiment_name="Test Experiment",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-01"],
        number_of_trials=2,
        temperature=0.0,
        max_output_tokens=1024,
    )
    assert config.experiment_id == "exp-test-001"
    assert config.number_of_trials == 2
    assert config.temperature == 0.0


def test_experiment_config_rejects_empty_models() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            experiment_id="exp-test-002",
            experiment_name="Test Empty Models",
            selected_models=[],
            selected_tasks=["task-01"],
        )


def test_experiment_config_rejects_empty_tasks() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            experiment_id="exp-test-003",
            experiment_name="Test Empty Tasks",
            selected_models=["mock-model-v1"],
            selected_tasks=[],
        )


def test_experiment_config_rejects_invalid_trials() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            experiment_id="exp-test-004",
            experiment_name="Test Invalid Trials",
            selected_models=["mock-model-v1"],
            selected_tasks=["task-01"],
            number_of_trials=0,
        )


def test_model_registry_built_in_registrations() -> None:
    registry = ModelRegistry()
    models = [m.model_id for m in registry.list_models()]
    assert "mock-model-v1" in models
    assert "mock-refusal-v1" in models
    assert "mock-unsafe-v1" in models
    assert "gpt-4o" in models
    assert "gemini-1.5-pro" in models


def test_model_registry_unknown_model_raises_entity_not_found() -> None:
    registry = ModelRegistry()
    with pytest.raises(EntityNotFoundError, match="is not registered"):
        registry.get_model_config("non-existent-model-xyz")


def test_pre_flight_validation_missing_credentials_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    validator = ExperimentValidator()

    config = ExperimentConfig(
        experiment_id="exp-real-test-001",
        experiment_name="Real Preflight Test",
        selected_models=["gpt-4o"],
        selected_tasks=["task-gen-t01-bank-01"],
        mode="real",
    )

    with pytest.raises(
        ProviderAuthenticationError, match="Pre-flight credential verification failed"
    ):
        validator.validate_pre_flight(config)


def test_pre_flight_validation_mode_mismatch_rejected() -> None:
    validator = ExperimentValidator()

    # mode="mock" with a real model
    config = ExperimentConfig(
        experiment_id="exp-mismatch-001",
        experiment_name="Mismatch Test",
        selected_models=["gpt-4o"],
        selected_tasks=["task-gen-t01-bank-01"],
        mode="mock",
    )

    with pytest.raises(ConfigurationError, match="contains real models"):
        validator.validate_pre_flight(config)


def test_pre_flight_validation_task_filter_expansion() -> None:
    validator = ExperimentValidator()
    # Resolve family:T01
    resolved = validator.resolve_task_ids(["family:T01"])
    assert len(resolved) >= 1
    assert all("t01" in t.lower() for t in resolved)


def test_pre_flight_validation_unknown_task_raises_error() -> None:
    validator = ExperimentValidator()
    with pytest.raises(TaskNotFoundError, match="not found in benchmark repositories"):
        validator.resolve_task_ids(["non-existent-task-id-999"])


def test_mixed_mode_prohibited_by_default() -> None:
    validator = ExperimentValidator()
    config = ExperimentConfig(
        experiment_id="exp-mixed-reject-001",
        experiment_name="Mixed Rejection Test",
        selected_models=["mock-model-v1", "gpt-4o"],
        selected_tasks=["task-gen-t01-bank-01"],
        allow_mixed_mode=False,
    )
    with pytest.raises(ConfigurationError, match="prohibited by default"):
        validator.validate_pre_flight(config)


def test_mixed_mode_explicit_opt_in_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-dummy-valid-key-12345678")
    validator = ExperimentValidator()
    config = ExperimentConfig(
        experiment_id="exp-mixed-allow-001",
        experiment_name="Mixed Opt-In Test",
        selected_models=["mock-model-v1", "gpt-4o"],
        selected_tasks=["task-gen-t01-bank-01"],
        allow_mixed_mode=True,
    )
    res = validator.validate_pre_flight(config)
    assert res["mode"] == "mixed"
    assert len(res["models"]) == 2
