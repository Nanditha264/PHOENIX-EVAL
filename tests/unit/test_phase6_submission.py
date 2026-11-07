"""Tests for Phase 6 hackathon submission packaging and clean extraction verification."""

import subprocess
import sys
import zipfile
from pathlib import Path

from scripts.package_archive import (
    build_archive,
    build_outer_archive,
    verify_archive,
    verify_outer_archive,
)


def test_submission_archive_build_and_clean_extraction(tmp_path: Path) -> None:
    """Verify phoenix_eval_submission.zip builds cleanly and extracts to a fully functional tree."""
    submission_zip = tmp_path / "phoenix_eval_submission.zip"
    build_archive(output_path=submission_zip)

    assert submission_zip.is_file(), "Submission archive was not created."
    assert submission_zip.stat().st_size > 50000, "Archive size unexpectedly small."

    # 1. Verify archive entries
    is_valid, violations = verify_archive(submission_zip)
    assert is_valid is True, f"Submission archive verification failed: {violations}"

    # 2. Extract into tmp_path
    extract_dir = tmp_path / "extracted_project"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(submission_zip, "r") as zf:
        zf.extractall(extract_dir)

    # 3. Verify extracted tree layout
    assert (extract_dir / "pyproject.toml").is_file()
    assert (extract_dir / "README.md").is_file()
    assert (extract_dir / "LICENSE").is_file()
    assert (extract_dir / ".env.example").is_file()
    assert (extract_dir / "src" / "phoenix_eval" / "main.py").is_file()
    assert (extract_dir / "datasets" / "calibration" / "calibration_cases.json").is_file()
    assert (extract_dir / "docs" / "FIVE_MINUTE_WALKTHROUGH_SCRIPT.md").is_file()
    assert (extract_dir / "results" / "exports" / "overall_metrics.csv").is_file()

    # Verify no leaked credentials or caches in extracted directory
    for forbidden in [".env", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache"]:
        assert not (extract_dir / forbidden).exists()

    # 4. Verify that calibration runs inside the extracted tree
    # Run python -m phoenix_eval.main evaluate-calibration using subprocess in extract_dir
    res = subprocess.run(
        [sys.executable, "-m", "phoenix_eval.main", "evaluate-calibration"],
        cwd=str(extract_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0, (
        f"Extracted calibration execution failed: {res.stderr}\n{res.stdout}"
    )
    assert "42/42" in res.stdout, f"Calibration incomplete in extracted tree: {res.stdout}"
    assert "CALIBRATION SUITE RESULT: PASSED" in res.stdout, (
        f"Calibration did not pass: {res.stdout}"
    )


def test_outer_archive_packaging_and_exclusion_of_caches_and_old_zips(tmp_path: Path) -> None:
    """Verify phoenix_eval_phase6_1.zip packages cleanly, contains nested submission zip,
    and strictly excludes previous phase zips, caches, and bytecode."""
    outer_zip = tmp_path / "phoenix_eval_phase6_1.zip"
    build_outer_archive(output_path=outer_zip)

    assert outer_zip.is_file(), "Outer archive was not created."
    assert outer_zip.stat().st_size > 50000, "Outer archive size unexpectedly small."

    # 1. Verify outer archive entries
    is_valid, violations = verify_outer_archive(outer_zip)
    assert is_valid is True, f"Outer archive verification failed: {violations}"

    # 2. Extract into tmp_path
    extract_dir = tmp_path / "extracted_outer"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(outer_zip, "r") as zf:
        zf.extractall(extract_dir)

    # 3. Verify nested submission package is present
    assert (extract_dir / "phoenix_eval_submission.zip").is_file()

    # 4. Verify no old phase zips or forbidden cache directories are in the extracted tree
    for old_zip in [
        "phoenix_eval_phase4_1.zip",
        "phoenix_eval_phase4_2.zip",
        "phoenix_eval_phase5.zip",
        "phoenix_eval_phase5_1.zip",
    ]:
        assert not (extract_dir / old_zip).exists()

    for forbidden in [
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        ".coverage",
        "htmlcov",
    ]:
        assert not (extract_dir / forbidden).exists()
