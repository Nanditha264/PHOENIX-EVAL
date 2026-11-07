"""Deterministic clean source archive packaging and verification for PHOENIX-EVAL Phase 5.1."""

import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "build",
    "dist",
    ".idea",
    ".vscode",
}

EXCLUDED_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".zip",
    ".tar",
    ".gz",
    ".coverage",
}

EXCLUDED_EXACT_NAMES = {
    ".env",
    ".coverage",
    ".DS_Store",
    "Thumbs.db",
}

INCLUDED_ROOT_DIRS = [
    "src",
    "tests",
    "datasets",
    "config",
    "docs",
    "scripts",
    "results",
]

INCLUDED_ROOT_FILES = [
    "pyproject.toml",
    "README.md",
    "LICENSE",
    ".env.example",
    ".gitignore",
    "requirements.txt",
    "PHOENIX_EVAL_PHASE_5_RESEARCH_REPORT.md",
    "PHOENIX_EVAL_RESEARCH_REPORT.md",
    "PHOENIX_EVAL_PHASE_7_COMPLETION_REPORT.md",
]


def is_excluded_path(rel_path: Path) -> bool:
    """Check if a relative path matches any exclusion rule."""
    parts = rel_path.parts

    # Check directory exclusions
    for part in parts:
        if part in EXCLUDED_DIR_NAMES:
            return True
        if part.endswith(".egg-info"):
            return True

    # Check file name
    name = rel_path.name
    if name in EXCLUDED_EXACT_NAMES:
        return True
    if name.startswith(".env") and name != ".env.example":
        return True
    if any(name.endswith(suffix) for suffix in EXCLUDED_FILE_SUFFIXES):
        return True
    return bool("credential" in name.lower() or "secret" in name.lower())


def is_excluded_outer_path(rel_path: Path) -> bool:
    """Check if relative path matches outer archive exclusion rules.

    Allows phoenix_eval_submission.zip but strictly excludes caches, bytecode,
    coverage files, and previous phase ZIPs (e.g. phoenix_eval_phase5_1.zip).
    """
    parts = rel_path.parts
    for part in parts:
        if part in EXCLUDED_DIR_NAMES or part.endswith(".egg-info"):
            return True

    name = rel_path.name
    if name in EXCLUDED_EXACT_NAMES:
        return True
    if name.startswith(".env") and name != ".env.example":
        return True
    # Strictly exclude previous phase ZIPs
    if name.startswith("phoenix_eval_phase") and name.endswith(".zip"):
        return True
    if any(
        name.endswith(suffix) for suffix in [".pyc", ".pyo", ".pyd", ".tar", ".gz", ".coverage"]
    ):
        return True
    if name.endswith(".zip") and name != "phoenix_eval_submission.zip":
        return True
    return bool("credential" in name.lower() or "secret" in name.lower())


def build_archive(output_path: Path | None = None) -> Path:
    """Build the clean source archive phoenix_eval_submission.zip."""
    target_zip = output_path or (ROOT_DIR / "phoenix_eval_submission.zip")
    if target_zip.exists():
        target_zip.unlink()

    files_to_add: list[tuple[Path, str]] = []

    # 1. Directories
    for root_dir_name in INCLUDED_ROOT_DIRS:
        dir_path = ROOT_DIR / root_dir_name
        if not dir_path.is_dir():
            continue
        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(ROOT_DIR)
            if not is_excluded_path(rel_path):
                files_to_add.append((file_path, rel_path.as_posix()))

    # 2. Root files
    for root_file_name in INCLUDED_ROOT_FILES:
        file_path = ROOT_DIR / root_file_name
        if file_path.is_file():
            rel_path = file_path.relative_to(ROOT_DIR)
            if not is_excluded_path(rel_path):
                files_to_add.append((file_path, rel_path.as_posix()))

    # Sort deterministically
    files_to_add.sort(key=lambda x: x[1])

    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_file, archive_name in files_to_add:
            zf.write(abs_file, archive_name)

    return target_zip


def build_outer_archive(output_path: Path | None = None) -> Path:
    """Build the clean outer archive phoenix_eval_phase6_1.zip containing the clean project tree
    and nested phoenix_eval_submission.zip, strictly excluding all caches, bytecode, coverage,
    and previous phase ZIPs."""
    # Ensure fresh nested submission zip exists first
    build_archive()

    target_zip = output_path or (ROOT_DIR / "phoenix_eval_phase6_1.zip")
    if target_zip.exists():
        target_zip.unlink()

    files_to_add: list[tuple[Path, str]] = []

    # 1. Directories
    for root_dir_name in INCLUDED_ROOT_DIRS:
        dir_path = ROOT_DIR / root_dir_name
        if not dir_path.is_dir():
            continue
        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(ROOT_DIR)
            if not is_excluded_outer_path(rel_path):
                files_to_add.append((file_path, rel_path.as_posix()))

    # 2. Root files + nested submission archive
    root_files = list(INCLUDED_ROOT_FILES) + [
        "PHOENIX_EVAL_PHASE_5_COMPLETION_REPORT.md",
        "phoenix_eval_submission.zip",
    ]
    for root_file_name in root_files:
        file_path = ROOT_DIR / root_file_name
        if file_path.is_file():
            rel_path = file_path.relative_to(ROOT_DIR)
            if not is_excluded_outer_path(rel_path):
                files_to_add.append((file_path, rel_path.as_posix()))

    files_to_add.sort(key=lambda x: x[1])

    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_file, archive_name in files_to_add:
            zf.write(abs_file, archive_name)

    return target_zip


def verify_outer_archive(archive_path: Path) -> tuple[bool, list[str]]:
    """Verify that outer archive contains nested submission package and has 0 forbidden files."""
    if not archive_path.is_file():
        return False, [f"Outer archive file does not exist: {archive_path}"]

    violations: list[str] = []
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = zf.namelist()
        if not names:
            return False, ["Outer archive is empty"]

        # Check required files
        if "phoenix_eval_submission.zip" not in names:
            violations.append("Missing nested phoenix_eval_submission.zip in outer archive")
        if not any(n.startswith("src/") for n in names):
            violations.append("Missing src/ directory in outer archive")
        if not any(n.startswith("tests/") for n in names):
            violations.append("Missing tests/ directory in outer archive")

        for name in names:
            rel = Path(name)
            if is_excluded_outer_path(rel):
                violations.append(f"Forbidden file found in outer archive: {name}")

    return len(violations) == 0, violations


def verify_archive(archive_path: Path) -> tuple[bool, list[str]]:
    """Inspect every entry in the archive to verify no forbidden files are present."""
    if not archive_path.is_file():
        return False, [f"Archive file does not exist: {archive_path}"]

    violations: list[str] = []
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = zf.namelist()

        if not names:
            return False, ["Archive is empty"]

        # Check required files exist
        has_src = any(n.startswith("src/") for n in names)
        has_tests = any(n.startswith("tests/") for n in names)
        has_datasets = any(n.startswith("datasets/") for n in names)
        has_pyproject = "pyproject.toml" in names

        if not has_src:
            violations.append("Missing src/ directory")
        if not has_tests:
            violations.append("Missing tests/ directory")
        if not has_datasets:
            violations.append("Missing datasets/ directory")
        if not has_pyproject:
            violations.append("Missing pyproject.toml")

        # Check exclusions
        for name in names:
            rel = Path(name)
            if is_excluded_path(rel):
                violations.append(f"Forbidden file found in archive: {name}")

    return len(violations) == 0, violations


def build_final_submission_archive(output_path: Path | None = None) -> Path:
    """Build the clean final submission archive phoenix_eval_final_submission.zip."""
    target_zip = output_path or (ROOT_DIR / "phoenix_eval_final_submission.zip")
    return build_archive(output_path=target_zip)


def verify_final_submission_archive(archive_path: Path) -> tuple[bool, list[str]]:
    """Verify that phoenix_eval_final_submission.zip contains all required deliverables and zero forbidden files."""
    if not archive_path.is_file():
        return False, [f"Archive file does not exist: {archive_path}"]

    violations: list[str] = []
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = zf.namelist()
        if not names:
            return False, ["Archive is empty"]

        required_exact = [
            "pyproject.toml",
            "README.md",
            "LICENSE",
            ".env.example",
            ".gitignore",
            "requirements.txt",
            "PHOENIX_EVAL_RESEARCH_REPORT.md",
            "src/phoenix_eval/main.py",
            "datasets/calibration/calibration_cases.json",
            "docs/JUDGE_PROJECT_EXPLANATION.md",
            "docs/JUDGE_QUICKSTART.md",
            "docs/FINAL_FIVE_MINUTE_DEMO_SCRIPT.md",
            "docs/HACKATHON_SUBMISSION_DESCRIPTION.md",
            "docs/JUDGE_QA.md",
            "results/exports/overall_metrics.csv",
        ]
        for req in required_exact:
            if req not in names:
                violations.append(f"Missing required file in final submission: {req}")

        for name in names:
            rel = Path(name)
            if is_excluded_path(rel):
                violations.append(f"Forbidden file found in final submission: {name}")

    return len(violations) == 0, violations


if __name__ == "__main__":
    # 1. Build & verify nested submission archive
    sub_zip = build_archive()
    print(f"Built nested submission archive: {sub_zip}")
    ok_sub, errors_sub = verify_archive(sub_zip)
    if not ok_sub:
        print("Nested submission archive verification FAILED:")
        for err in errors_sub:
            print(f"  - {err}")
        sys.exit(1)
    print("Nested submission archive verification PASSED (0 violations).")

    # 2. Build & verify final hackathon submission package (phoenix_eval_final_submission.zip)
    final_zip = build_final_submission_archive()
    print(f"Built final submission archive: {final_zip}")
    ok_final, errors_final = verify_final_submission_archive(final_zip)
    if not ok_final:
        print("Final submission archive verification FAILED:")
        for err in errors_final:
            print(f"  - {err}")
        sys.exit(1)
    print("Final submission archive verification PASSED (0 violations).")

    # 3. Build & verify clean outer archive
    outer_zip = build_outer_archive()
    print(f"Built outer archive: {outer_zip}")
    ok_outer, errors_outer = verify_outer_archive(outer_zip)
    if not ok_outer:
        print("Outer archive verification FAILED:")
        for err in errors_outer:
            print(f"  - {err}")
        sys.exit(1)
    print("Outer archive verification PASSED (0 violations).")
    sys.exit(0)
