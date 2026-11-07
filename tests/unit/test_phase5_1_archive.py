"""Regression tests for Phase 5.1 Defect 8: Clean source archive packaging and verification."""

import zipfile
from pathlib import Path

from scripts.package_archive import build_archive, is_excluded_path, verify_archive


def test_is_excluded_path_logic() -> None:
    """Ensure exclusion filter correctly flags caches, virtualenvs, credentials, and temp files."""
    assert is_excluded_path(Path(".git/config")) is True
    assert is_excluded_path(Path(".venv/lib/site-packages")) is True
    assert is_excluded_path(Path("src/phoenix_eval/__pycache__/main.cpython-311.pyc")) is True
    assert is_excluded_path(Path(".pytest_cache/v/cache")) is True
    assert is_excluded_path(Path(".mypy_cache/3.11/cache")) is True
    assert is_excluded_path(Path(".ruff_cache/cache")) is True
    assert is_excluded_path(Path(".env")) is True
    assert is_excluded_path(Path(".env.local")) is True
    assert is_excluded_path(Path(".env.example")) is False  # Allowed example file
    assert is_excluded_path(Path("secret_keys.json")) is True
    assert is_excluded_path(Path("test_credentials.txt")) is True
    assert is_excluded_path(Path("archive.zip")) is True
    assert is_excluded_path(Path("build/lib")) is True


def test_built_archive_conforms_to_strict_specification(tmp_path: Path) -> None:
    """Ensure the built archive contains all required source trees and zero forbidden files."""
    test_zip = tmp_path / "test_archive.zip"
    build_archive(output_path=test_zip)

    assert test_zip.is_file()
    assert test_zip.stat().st_size > 1000

    ok, violations = verify_archive(test_zip)
    assert ok is True, f"Archive verification failed: {violations}"

    with zipfile.ZipFile(test_zip, "r") as zf:
        names = set(zf.namelist())

        # Check required files
        assert "pyproject.toml" in names
        assert "README.md" in names
        assert ".env.example" in names
        assert "src/phoenix_eval/__init__.py" in names
        assert "src/phoenix_eval/main.py" in names

        # Check that NO forbidden files leaked
        for n in names:
            assert not n.startswith(".git/")
            assert not n.startswith(".venv/")
            assert "__pycache__" not in n
            assert not n.endswith(".pyc")
            assert not n.endswith(".zip")
            assert not n.endswith(".coverage")
            assert n != ".env"
