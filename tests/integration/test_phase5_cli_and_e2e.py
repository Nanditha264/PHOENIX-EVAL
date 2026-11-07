"""Integration and end-to-end tests for Phase 5 CLI commands and analysis workflows."""

from pathlib import Path

from phoenix_eval.analysis.coordinator import Phase5AnalysisCoordinator
from phoenix_eval.core.paths import get_paths
from phoenix_eval.main import (
    cmd_analyze_all,
    cmd_analyze_experiment,
    cmd_failure_analysis,
    cmd_generate_research_report,
    cmd_inspect_analysis,
    cmd_metamorphic_analysis,
    cmd_paired_analysis,
    cmd_validate_results,
)


def test_coordinator_end_to_end_analysis(tmp_path):
    paths = get_paths()
    coordinator = Phase5AnalysisCoordinator(paths)

    report_out = tmp_path / "TEST_RESEARCH_REPORT.md"
    manifest = coordinator.analyze_experiment(
        experiment_id="exp-mock-comparison-001",
        generate_report=True,
        output_report_path=report_out,
    )

    assert manifest.analysis_id.startswith("anal-")
    assert manifest.source_experiment_ids == ["exp-mock-comparison-001"]
    assert manifest.benchmark_version == "5.0.0"
    assert manifest.evaluator_version == "3.0.0"

    # Verify report generated with all 26 sections
    assert report_out.is_file()
    content = report_out.read_text(encoding="utf-8")
    for sec_num in range(1, 27):
        assert f"## {sec_num}." in content

    # Verify CSV exports created
    assert (paths.exports_dir / "overall_metrics.csv").is_file()
    assert (paths.exports_dir / "dimension_metrics.csv").is_file()
    assert (paths.exports_dir / "task_family_metrics.csv").is_file()
    assert (paths.exports_dir / "domain_metrics.csv").is_file()
    assert (paths.exports_dir / "difficulty_metrics.csv").is_file()
    assert (paths.exports_dir / "failure_patterns.csv").is_file()


def test_cli_validate_results():
    ret = cmd_validate_results("exp-mock-phase5-1-001")
    assert ret == 0


def test_cli_failure_analysis():
    ret = cmd_failure_analysis("exp-mock-comparison-001")
    assert ret == 0


def test_cli_paired_analysis():
    ret = cmd_paired_analysis("exp-mock-comparison-001")
    assert ret == 0


def test_cli_metamorphic_analysis():
    ret = cmd_metamorphic_analysis("exp-mock-comparison-001")
    assert ret == 0


def test_cli_analyze_experiment_and_inspect():
    ret = cmd_analyze_experiment("exp-mock-comparison-001")
    assert ret == 0

    coordinator = Phase5AnalysisCoordinator()
    manifests = coordinator.paths.analysis_dir.glob("manifest_*.json")
    manifest_files = list(manifests)
    assert len(manifest_files) > 0
    anal_id = manifest_files[0].stem.replace("manifest_", "")

    ret_insp = cmd_inspect_analysis(anal_id)
    assert ret_insp == 0


def test_cli_generate_research_report(tmp_path):
    out_file = str(tmp_path / "CUSTOM_REPORT.md")
    ret = cmd_generate_research_report("exp-mock-comparison-001", output_path=out_file)
    assert ret == 0
    assert Path(out_file).is_file()


def test_cli_analyze_all():
    ret = cmd_analyze_all()
    assert ret == 0
