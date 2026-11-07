"""Unit tests for Phase 4 experiment metrics aggregation, scoring statistics, and CSV/MD export."""

from pathlib import Path

from phoenix_eval.experiment.aggregator import ExperimentAggregator
from phoenix_eval.schemas.common import ExecutionStatus
from phoenix_eval.schemas.experiments import ExperimentConfig, ExperimentRunRecord
from phoenix_eval.utils.time import current_utc_timestamp


def _make_run(
    model_id: str,
    status: ExecutionStatus,
    raw_score: float | None = None,
    eff_score: float | None = None,
    safety_passed: bool | None = None,
    crit_viols: int = 0,
    trial: int = 1,
    task_id: str = "task-01",
    latency: float = 1.0,
) -> ExperimentRunRecord:
    return ExperimentRunRecord(
        experiment_id="exp-agg-001",
        run_id=f"run-{model_id}-{task_id}-t{trial}",
        task_id=task_id,
        scenario_id="scen-01",
        provider_name="mock" if "mock" in model_id else "openai",
        model_identifier=model_id,
        trial_number=trial,
        execution_status=status,
        timestamp_started=current_utc_timestamp(),
        timestamp_completed=current_utc_timestamp(),
        latency_seconds=latency,
        prompt_hash="dummy-prompt-hash",
        raw_weighted_score=raw_score,
        effective_score=eff_score,
        safety_gate_passed=safety_passed,
        critical_violations_count=crit_viols,
        is_mock="mock" in model_id,
    )


def test_aggregator_mean_and_median_calculation() -> None:
    config = ExperimentConfig(
        experiment_id="exp-agg-001",
        experiment_name="Aggregator Test",
        selected_models=["model-a"],
        selected_tasks=["task-01"],
    )

    runs = [
        _make_run(
            "model-a",
            ExecutionStatus.COMPLETED,
            raw_score=80.0,
            eff_score=80.0,
            safety_passed=True,
            trial=1,
        ),
        _make_run(
            "model-a",
            ExecutionStatus.COMPLETED,
            raw_score=60.0,
            eff_score=60.0,
            safety_passed=True,
            trial=2,
        ),
        _make_run(
            "model-a",
            ExecutionStatus.COMPLETED,
            raw_score=100.0,
            eff_score=100.0,
            safety_passed=True,
            trial=3,
        ),
    ]

    aggregator = ExperimentAggregator(config, runs)
    summary = aggregator.compute_summary()
    m_data = summary["models"]["model-a"]

    assert m_data["attempted_runs"] == 3
    assert m_data["completed_runs"] == 3
    assert m_data["failed_runs"] == 0
    assert m_data["completion_rate"] == 1.0
    assert m_data["mean_raw_score"] == 80.0
    assert m_data["median_raw_score"] == 80.0
    assert m_data["mean_effective_score"] == 80.0
    assert m_data["trial_score_std"] == 20.0
    assert m_data["safety_gate_failure_rate"] == 0.0


def test_aggregator_excludes_failed_calls_from_score_averages() -> None:
    config = ExperimentConfig(
        experiment_id="exp-agg-002",
        experiment_name="Failed Runs Exclusion Test",
        selected_models=["model-b"],
        selected_tasks=["task-01"],
    )

    # 2 completed runs (scores 90 and 70), 1 failed run (no score)
    runs = [
        _make_run(
            "model-b",
            ExecutionStatus.COMPLETED,
            raw_score=90.0,
            eff_score=90.0,
            safety_passed=True,
            trial=1,
        ),
        _make_run(
            "model-b",
            ExecutionStatus.COMPLETED,
            raw_score=70.0,
            eff_score=70.0,
            safety_passed=True,
            trial=2,
        ),
        _make_run("model-b", ExecutionStatus.FAILED, raw_score=None, eff_score=None, trial=3),
    ]

    aggregator = ExperimentAggregator(config, runs)
    summary = aggregator.compute_summary()
    m_data = summary["models"]["model-b"]

    assert m_data["attempted_runs"] == 3
    assert m_data["completed_runs"] == 2
    assert m_data["failed_runs"] == 1
    assert m_data["completion_rate"] == 0.6667
    # Mean of 90 and 70 is 80.0 (must NOT be divided by 3 or count failed as 0)
    assert m_data["mean_raw_score"] == 80.0
    assert m_data["mean_effective_score"] == 80.0


def test_aggregator_safety_failure_rate_calculation() -> None:
    config = ExperimentConfig(
        experiment_id="exp-agg-003",
        experiment_name="Safety Failure Test",
        selected_models=["model-c"],
        selected_tasks=["task-01"],
    )

    # 1 passed safety, 3 failed safety
    runs = [
        _make_run(
            "model-c",
            ExecutionStatus.COMPLETED,
            raw_score=95.0,
            eff_score=95.0,
            safety_passed=True,
            trial=1,
        ),
        _make_run(
            "model-c",
            ExecutionStatus.COMPLETED,
            raw_score=85.0,
            eff_score=0.0,
            safety_passed=False,
            crit_viols=1,
            trial=2,
        ),
        _make_run(
            "model-c",
            ExecutionStatus.COMPLETED,
            raw_score=80.0,
            eff_score=0.0,
            safety_passed=False,
            crit_viols=2,
            trial=3,
        ),
        _make_run(
            "model-c",
            ExecutionStatus.COMPLETED,
            raw_score=90.0,
            eff_score=0.0,
            safety_passed=False,
            crit_viols=1,
            trial=4,
        ),
    ]

    aggregator = ExperimentAggregator(config, runs)
    summary = aggregator.compute_summary()
    m_data = summary["models"]["model-c"]

    assert m_data["safety_gate_passed_count"] == 1
    assert m_data["safety_gate_failed_count"] == 3
    assert m_data["safety_gate_failure_rate"] == 0.75
    assert m_data["critical_violations_count"] == 4
    # Raw mean reflects capability without safety veto: (95+85+80+90)/4 = 87.5
    assert m_data["mean_raw_score"] == 87.5
    # Effective mean reflects safety veto: (95+0+0+0)/4 = 23.75
    assert m_data["mean_effective_score"] == 23.75


def test_aggregator_writes_csv_and_markdown(tmp_path: Path) -> None:
    config = ExperimentConfig(
        experiment_id="exp-agg-004",
        experiment_name="Export Files Test",
        selected_models=["model-d"],
        selected_tasks=["task-01"],
    )

    runs = [
        _make_run(
            "model-d",
            ExecutionStatus.COMPLETED,
            raw_score=80.0,
            eff_score=80.0,
            safety_passed=True,
            trial=1,
        ),
    ]

    aggregator = ExperimentAggregator(config, runs)
    csv_path = tmp_path / "model_comparison.csv"
    md_path = tmp_path / "experiment_summary.md"

    aggregator.write_comparison_csv(csv_path)
    aggregator.write_markdown_summary(md_path)

    assert csv_path.exists()
    assert md_path.exists()

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "model_identifier" in csv_text
    assert "model-d" in csv_text

    md_text = md_path.read_text(encoding="utf-8")
    assert "# PHOENIX-EVAL Experiment Report" in md_text
    assert "model-d" in md_text


def test_aggregator_separates_mock_and_real_models(tmp_path: Path) -> None:
    config = ExperimentConfig(
        experiment_id="exp-agg-005",
        experiment_name="Separation Test",
        selected_models=["gpt-4o", "mock-model-v1"],
        selected_tasks=["task-01"],
        allow_mixed_mode=True,
    )

    runs = [
        _make_run(
            "gpt-4o",
            ExecutionStatus.COMPLETED,
            raw_score=90.0,
            eff_score=90.0,
            safety_passed=True,
            trial=1,
        ),
        _make_run(
            "mock-model-v1",
            ExecutionStatus.COMPLETED,
            raw_score=85.0,
            eff_score=85.0,
            safety_passed=True,
            trial=1,
        ),
    ]

    aggregator = ExperimentAggregator(config, runs)
    summary = aggregator.compute_summary()

    assert "gpt-4o" in summary["real_models"]
    assert "mock-model-v1" in summary["mock_models"]
    assert summary["real_models_count"] == 1
    assert summary["mock_models_count"] == 1

    md_path = tmp_path / "experiment_summary.md"
    csv_path = tmp_path / "model_comparison.csv"
    aggregator.write_markdown_summary(md_path)
    aggregator.write_comparison_csv(csv_path)

    md_text = md_path.read_text(encoding="utf-8")
    assert "## 1. Real Frontier AI Models Evaluation" in md_text
    assert "Simulated Baseline Models" in md_text

    csv_lines = [
        line.strip() for line in csv_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    # Real model comes before mock model
    gpt_index = next(i for i, line in enumerate(csv_lines) if "gpt-4o" in line)
    mock_index = next(i for i, line in enumerate(csv_lines) if "mock-model-v1" in line)
    assert gpt_index < mock_index


def test_aggregator_resolves_all_domains_and_task_families_without_unknown() -> None:
    """Verify aggregator resolves task families T01-T10 and enterprise domains without returning Unknown."""
    config = ExperimentConfig(
        experiment_id="exp-agg-006",
        experiment_name="Domain and Task Family Test",
        selected_models=["mock-model-v1"],
        selected_tasks=[
            "task-gen-t01-bank-01",
            "task-gen-t02-erp-02",
            "task-gen-t03-telco-01",
            "task-gen-t04-telco-03",
            "task-gen-t05-gov-02",
            "task-gen-t06-idp-03",
            "task-pair-hsm-support-01-a",
        ],
    )

    runs = [
        _make_run(
            "mock-model-v1",
            ExecutionStatus.COMPLETED,
            raw_score=90.0,
            eff_score=90.0,
            safety_passed=True,
            task_id="task-gen-t01-bank-01",
        ),
        _make_run(
            "mock-model-v1",
            ExecutionStatus.COMPLETED,
            raw_score=85.0,
            eff_score=85.0,
            safety_passed=True,
            task_id="task-gen-t02-erp-02",
        ),
        _make_run(
            "mock-model-v1",
            ExecutionStatus.COMPLETED,
            raw_score=92.0,
            eff_score=92.0,
            safety_passed=True,
            task_id="task-gen-t03-telco-01",
        ),
        _make_run(
            "mock-model-v1",
            ExecutionStatus.COMPLETED,
            raw_score=88.0,
            eff_score=88.0,
            safety_passed=True,
            task_id="task-gen-t04-telco-03",
        ),
        _make_run(
            "mock-model-v1",
            ExecutionStatus.COMPLETED,
            raw_score=95.0,
            eff_score=95.0,
            safety_passed=True,
            task_id="task-gen-t05-gov-02",
        ),
        _make_run(
            "mock-model-v1",
            ExecutionStatus.COMPLETED,
            raw_score=80.0,
            eff_score=80.0,
            safety_passed=True,
            task_id="task-gen-t06-idp-03",
        ),
        _make_run(
            "mock-model-v1",
            ExecutionStatus.COMPLETED,
            raw_score=91.0,
            eff_score=91.0,
            safety_passed=True,
            task_id="task-pair-hsm-support-01-a",
        ),
    ]

    aggregator = ExperimentAggregator(config, runs)
    summary = aggregator.compute_summary()
    m_data = summary["models"]["mock-model-v1"]

    fam_keys = set(m_data["per_task_family"].keys())
    dom_keys = set(m_data["per_domain"].keys())

    assert "Unknown" not in fam_keys
    assert "Unknown" not in dom_keys
    assert {"T01", "T02", "T03", "T04", "T05", "T06", "T09"}.issubset(fam_keys)
    assert {
        "BANKING_PAYMENTS",
        "ENTERPRISE_SERVICES",
        "TELECOM_NETWORK",
        "GOVERNMENT_CRITICAL",
        "CLOUD_IDENTITY",
    }.issubset(dom_keys)
