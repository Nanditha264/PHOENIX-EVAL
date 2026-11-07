"""Comprehensive verification tests for PHOENIX-EVAL Phase 7 final hackathon submission package."""

import subprocess
import sys
import zipfile
from pathlib import Path

from scripts.package_archive import (
    build_final_submission_archive,
    verify_final_submission_archive,
)


def test_final_submission_package_and_extracted_execution(tmp_path: Path) -> None:
    """Verify phoenix_eval_final_submission.zip builds cleanly and executes in an isolated environment."""
    final_zip = tmp_path / "phoenix_eval_final_submission.zip"
    build_final_submission_archive(output_path=final_zip)

    assert final_zip.is_file(), "Final submission archive was not created."
    assert final_zip.stat().st_size > 50000, "Archive size unexpectedly small."

    # 1. Verify archive entries
    is_valid, violations = verify_final_submission_archive(final_zip)
    assert is_valid is True, f"Final submission archive verification failed: {violations}"

    # 2. Extract into tmp_path
    extract_dir = tmp_path / "extracted_final"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(final_zip, "r") as zf:
        zf.extractall(extract_dir)

    # 3. Verify all required judge-facing documents and deliverables exist
    required_files = [
        "pyproject.toml",
        "README.md",
        "LICENSE",
        ".env.example",
        ".gitignore",
        "requirements.txt",
        "PHOENIX_EVAL_RESEARCH_REPORT.md",
        "docs/JUDGE_PROJECT_EXPLANATION.md",
        "docs/JUDGE_QUICKSTART.md",
        "docs/FINAL_FIVE_MINUTE_DEMO_SCRIPT.md",
        "docs/HACKATHON_SUBMISSION_DESCRIPTION.md",
        "docs/JUDGE_QA.md",
        "src/phoenix_eval/main.py",
        "datasets/calibration/calibration_cases.json",
        "results/exports/overall_metrics.csv",
        "results/charts/visualizations.md",
    ]
    for rel_f in required_files:
        assert (extract_dir / rel_f).is_file(), (
            f"Required file '{rel_f}' missing in extracted tree."
        )

    # 4. Verify absolute absence of forbidden files, credentials, and caches
    for forbidden in [
        ".env",
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        ".coverage",
        "htmlcov",
    ]:
        assert not (extract_dir / forbidden).exists(), (
            f"Forbidden file/directory '{forbidden}' present."
        )

    # 5. Execute calibration inside the extracted directory
    res_cal = subprocess.run(
        [sys.executable, "-m", "phoenix_eval.main", "evaluate-calibration"],
        cwd=str(extract_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res_cal.returncode == 0, (
        f"Extracted calibration failed: {res_cal.stderr}\n{res_cal.stdout}"
    )
    assert "42/42" in res_cal.stdout, f"Calibration incomplete: {res_cal.stdout}"
    assert "CALIBRATION SUITE RESULT: PASSED" in res_cal.stdout

    # 6. Execute offline demonstration inside the extracted directory
    res_demo = subprocess.run(
        [sys.executable, "-m", "phoenix_eval.main", "demo"],
        cwd=str(extract_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res_demo.returncode == 0, f"Extracted demo failed: {res_demo.stderr}\n{res_demo.stdout}"
    assert "DEMONSTRATION COMPLETE" in res_demo.stdout

    # 7. Execute report generation / analysis inside the extracted directory
    res_anal = subprocess.run(
        [
            sys.executable,
            "-m",
            "phoenix_eval.main",
            "analyze-experiment",
            "--experiment",
            "exp-phase6-balanced-001",
        ],
        cwd=str(extract_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res_anal.returncode == 0, (
        f"Extracted analysis failed: {res_anal.stderr}\n{res_anal.stdout}"
    )
    assert "ANALYSIS SUCCESS [OK]" in res_anal.stdout
