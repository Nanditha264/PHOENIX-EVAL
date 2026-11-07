"""Unit tests for Phase 4.2 Recording Actual Model Version and Provider Metadata."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from phoenix_eval.experiment.runner import ExperimentRunner
from phoenix_eval.providers.openai_provider import OpenAICompatibleProvider
from phoenix_eval.schemas.experiments import ExperimentConfig, ExperimentRunRecord


def test_experiment_run_record_preserves_configured_vs_returned_metadata() -> None:
    """Verify configured model metadata is never overwritten by returned model identity."""
    record = ExperimentRunRecord(
        experiment_id="exp-meta-001",
        run_id="run-meta-001",
        task_id="task-dummy",
        scenario_id="scen-dummy",
        provider_name="openai",
        model_identifier="gpt-4o",  # configured alias
        model_version="2024-08-06",  # configured version
        configured_model_identifier="gpt-4o",
        configured_model_version="2024-08-06",
        returned_model_identifier="gpt-4o-2024-08-06-preview",  # actual upstream ID
        returned_model_version=None,  # absent from API, must be None (never fabricated)
        provider_request_id="chatcmpl-9xyz123abc",
        prompt_hash="dummy_prompt_hash",
    )

    # Configured identity is intact
    assert record.configured_model_identifier == "gpt-4o"
    assert record.configured_model_version == "2024-08-06"
    assert record.model_identifier == "gpt-4o"
    assert record.model_version == "2024-08-06"

    # Upstream returned metadata is separately recorded
    assert record.returned_model_identifier == "gpt-4o-2024-08-06-preview"
    assert record.returned_model_version is None
    assert record.provider_request_id == "chatcmpl-9xyz123abc"


def test_openai_provider_records_returned_model_and_request_id() -> None:
    """Verify OpenAI provider populates returned_model_identifier and request_id from API response."""
    provider = OpenAICompatibleProvider(
        provider_name="openai",
        model_identifier="gpt-4o",
        model_version="2024-08-06",
        api_key_env_var="MOCK_KEY",
    )

    fake_api_response = {
        "id": "chatcmpl-test-request-id-777",
        "model": "gpt-4o-2024-08-06-snapshot",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"task_id": "t1", "decision": "MIGRATION_READY"}',
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_api_response

    from phoenix_eval.providers.base import ProviderPromptRequest

    req = ProviderPromptRequest(task_id="task-001", prompt="Analyze")

    with (
        patch.object(provider, "_get_api_key", return_value="sk-validmockkey12345678"),
        patch("httpx.Client.post", return_value=mock_resp),
    ):
        resp = provider.generate_response(req)

    # Configured identifier not overwritten
    assert resp.model_identifier == "gpt-4o"
    assert resp.model_version == "2024-08-06"

    # Returned metadata captured
    assert resp.returned_model_identifier == "gpt-4o-2024-08-06-snapshot"
    assert resp.returned_model_version is None
    assert resp.provider_request_id == "chatcmpl-test-request-id-777"


def test_runner_records_model_metadata_end_to_end(tmp_path: Path) -> None:
    """End-to-end runner test: verify runs in manifest and runs.jsonl contain populated model metadata."""
    exp_dir = tmp_path / "exp_metadata"
    config = ExperimentConfig(
        experiment_id="exp-meta-e2e-001",
        experiment_name="Model Metadata Verification",
        selected_models=["mock-model-v1"],
        selected_tasks=["task-seq-pqc-001"],
        number_of_trials=1,
        output_dir=str(exp_dir),
        mode="mock",
    )

    runner = ExperimentRunner(config=config)
    manifest = runner.run()

    assert len(manifest.runs) == 1
    run = manifest.runs[0]

    assert run.configured_model_identifier == "mock-model-v1"
    assert run.configured_model_version == "1.0.0"
    assert run.returned_model_identifier == "mock-model-v1"
    assert run.returned_model_version == "1.0.0"
    assert run.provider_request_id == "mock-req-task-seq-pqc-001"
