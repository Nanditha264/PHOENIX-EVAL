"""Regression tests for Phase 5.1 Defect 7: Research report conclusions and scientific integrity."""

from pathlib import Path

from phoenix_eval.core.paths import get_paths


def test_research_report_contains_all_26_sections() -> None:
    """Ensure the generated research report contains all 26 numbered sections."""
    paths = get_paths()
    report_file = paths.root / "PHOENIX_EVAL_PHASE_5_RESEARCH_REPORT.md"
    assert report_file.is_file(), "PHOENIX_EVAL_PHASE_5_RESEARCH_REPORT.md must exist."

    content = report_file.read_text(encoding="utf-8")
    for sec_num in range(1, 27):
        assert f"## {sec_num}." in content, f"Section {sec_num} is missing from research report."


def test_research_report_for_mock_experiment_clearly_distinguishes_conclusions() -> None:
    """Ensure mock experiments do not manufacture real empirical conclusions."""
    paths = get_paths()
    report_file = paths.root / "PHOENIX_EVAL_PHASE_5_RESEARCH_REPORT.md"
    content = report_file.read_text(encoding="utf-8")

    # 1. Prominent banner in Section 1
    assert "NO REAL MODEL EXPERIMENTS AVAILABLE" in content
    assert "EMPIRICAL RESEARCH CONCLUSIONS NOT YET AVAILABLE" in content
    assert "Engineering Validation & Synthetic Pipeline Demonstration Notice" in content

    # 2. Section 25 conclusions
    assert "Empirical Benchmark Conclusions: NOT YET AVAILABLE" in content
    assert "Platform Engineering & Evaluation Engine Conclusions" in content

    # 3. Mode is explicitly simulation / mock
    assert "SIMULATION / MOCK DEMONSTRATION" in content


def test_live_production_flag_branch() -> None:
    """Ensure report generator correctly renders live mode when is_mock is False."""
    from phoenix_eval.analysis.ingestion import ValidatedExperimentData
    from phoenix_eval.analysis.report_generator import ResearchReportGenerator
    from phoenix_eval.analysis.schemas import IngestionRecordStatus, IngestionReport
    from phoenix_eval.schemas.experiments import ExperimentConfig, ExperimentManifest

    manifest = ExperimentManifest(
        experiment_id="exp-real-demo",
        experiment_name="Real Demo Campaign",
        config=ExperimentConfig(
            experiment_id="exp-real-demo",
            experiment_name="Real Demo Campaign",
            selected_models=["gpt-4o"],
            selected_tasks=["task-1"],
            mode="real",
        ),
        runs=[],
    )

    data = ValidatedExperimentData(
        manifest=manifest,
        valid_runs=[],
        failed_runs=[],
        corrupted_runs=[],
        raw_responses={},
        evaluation_reports={},
        ingestion_report=IngestionReport(
            experiment_id="exp-real-demo",
            import_status=IngestionRecordStatus.VALID,
            total_scheduled_runs=1,
            total_attempts=1,
            completed_runs=0,
            failed_runs=0,
            summary="real demo",
        ),
        is_mock=False,
    )

    gen = ResearchReportGenerator()
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test_report.md"
        gen.generate_report(
            validated_data=data,
            overall=[],
            dimensions=[],
            families=[],
            domains=[],
            difficulties=[],
            consistency=[],
            incidents=[],
            patterns=[],
            paired_items=[],
            metamorphic_items=[],
            comparisons=[],
            output_path=out_path,
        )

        content = out_path.read_text(encoding="utf-8")
        assert "LIVE MODEL EVALUATION" in content
        assert "Live API Production Campaign" in content
