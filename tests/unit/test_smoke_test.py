"""Tests for Phase 6 provider credential verification and smoke testing engine."""

import os
from pathlib import Path

from phoenix_eval.experiment.smoke_test import (
    CANONICAL_SMOKE_TASKS,
    SmokeTestReport,
    SmokeTestRunner,
)


def test_canonical_smoke_tasks_specification() -> None:
    """Verify canonical smoke tasks cover all three critical benchmark archetypes."""
    assert len(CANONICAL_SMOKE_TASKS) == 3
    archetypes = {t["archetype"] for t in CANONICAL_SMOKE_TASKS}
    assert archetypes == {"ORDINARY_VALID", "UNSAFE_BLOCKER", "EPISTEMIC_UNCERTAINTY"}
    task_ids = [t["task_id"] for t in CANONICAL_SMOKE_TASKS]
    assert "task-gen-t09-bank-02" in task_ids
    assert "task-gen-t03-telco-01" in task_ids
    assert "task-gen-t04-bank-02" in task_ids


def test_smoke_test_mock_execution(tmp_path: Path) -> None:
    """Verify smoke test passes in mock simulation mode with 100% contract validity."""
    runner = SmokeTestRunner()
    report: SmokeTestReport = runner.run_smoke_test(
        model_id="mock-valid-migration",
        is_mock=True,
        output_dir=tmp_path / "smoke_mock",
    )

    assert report.model_id == "mock-valid-migration"
    assert report.is_mock is True
    assert report.status == "PASSED"
    assert report.total_tasks == 3
    assert report.successful_requests == 3
    assert report.valid_contracts == 3
    assert len(report.task_results) == 3

    # Verify ground truth isolation for every task
    for tr in report.task_results:
        assert tr.prompt_sent is True
        assert tr.ground_truth_isolated is True
        assert tr.response_received is True
        assert tr.contract_valid is True
        assert tr.effective_score > 0.0

    # Verify raw responses were persisted
    raw_files = list((tmp_path / "smoke_mock" / "raw_responses").glob("*.json"))
    assert len(raw_files) == 3


def test_smoke_test_real_model_auth_failure_without_credentials() -> None:
    """Verify real provider smoke test returns AUTH_FAILED gracefully when keys are missing."""
    # Ensure keys are unset
    orig_openai = os.environ.pop("OPENAI_API_KEY", None)
    orig_gemini = os.environ.pop("GEMINI_API_KEY", None)
    orig_google = os.environ.pop("GOOGLE_API_KEY", None)

    try:
        runner = SmokeTestRunner()

        # Test OpenAI provider
        report_openai = runner.run_smoke_test(model_id="gpt-4o", is_mock=False)
        assert report_openai.status == "AUTH_FAILED"
        assert "OPENAI_API_KEY" in report_openai.summary

        # Test Google Gemini provider
        report_gemini = runner.run_smoke_test(model_id="gemini-1.5-flash", is_mock=False)
        assert report_gemini.status == "AUTH_FAILED"
        assert ("GEMINI_API_KEY" in report_gemini.summary) or (
            "GOOGLE_API_KEY" in report_gemini.summary
        )
    finally:
        if orig_openai is not None:
            os.environ["OPENAI_API_KEY"] = orig_openai
        if orig_gemini is not None:
            os.environ["GEMINI_API_KEY"] = orig_gemini
        if orig_google is not None:
            os.environ["GOOGLE_API_KEY"] = orig_google


def test_smoke_test_persists_audit_report(tmp_path: Path) -> None:
    """Verify smoke test generates and writes smoke_test_report.json."""
    runner = SmokeTestRunner()
    out_dir = tmp_path / "custom_smoke_out"
    report = runner.run_smoke_test("mock-valid-migration", is_mock=True, output_dir=out_dir)

    report_path = out_dir / "smoke_test_report.json"
    assert report_path.is_file()
    assert report.status == "PASSED"
