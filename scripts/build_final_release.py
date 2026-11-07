"""PHOENIX-EVAL Final Submission Packaging and Release Verification Engine.

Orchestrates:
1. Assembly of release/phoenix_eval_submission/
2. Generation of release/phoenix_eval_final_submission.zip
3. Cryptographic digest and manifest calculation
4. Independent verification by extracting into release/extracted_verification/
5. Clean test, calibration, smoke-test, and demo execution from extracted directory
6. Generation of FINAL_RELEASE_REPORT.md, FINAL_ARCHIVE_MANIFEST.json, FINAL_SHA256.txt, SUBMISSION_DESCRIPTION.md
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = ROOT / "release"
STAGE_DIR = RELEASE_DIR / "phoenix_eval_submission"
FINAL_ZIP = RELEASE_DIR / "phoenix_eval_final_submission.zip"
EXTRACT_DIR = RELEASE_DIR / "extracted_verification"

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "node_modules", "executioner", "release", ".idea", ".vscode", "htmlcov"
}

EXCLUDE_FILES = {
    ".env", ".coverage", "phoenix_eval.log", "phoenix_eval_submission.zip",
    "phoenix_eval_final_submission.zip", "Thumbs.db", ".DS_Store"
}

EXCLUDE_EXTS = {".pyc", ".pyo", ".pyd", ".log"}


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def copy_tree_filtered(src: Path, dst: Path):
    if not dst.exists():
        dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        if item.is_dir():
            if item.name in EXCLUDE_DIRS or item.name.endswith(".egg-info"):
                continue
            copy_tree_filtered(item, dst / item.name)
        elif item.is_file():
            if item.name in EXCLUDE_FILES or item.suffix in EXCLUDE_EXTS:
                continue
            if item.name.startswith(".env") and item.name != ".env.example":
                continue
            shutil.copy2(item, dst / item.name)


def assemble_stage():
    print(f"Assembling clean release staging directory at {STAGE_DIR}...")
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Core directories
    core_dirs = ["src", "tests", "datasets", "config", "docs", "scripts", "results"]
    for d in core_dirs:
        src_path = ROOT / d
        if src_path.exists():
            copy_tree_filtered(src_path, STAGE_DIR / d)

    # Core root files
    root_files = [
        "pyproject.toml", "requirements.txt", "README.md", "LICENSE",
        ".env.example", ".gitignore", "PHOENIX_EVAL_RESEARCH_REPORT.md",
        "PHOENIX_EVAL_PHASE_5_RESEARCH_REPORT.md", "PHOENIX_EVAL_PHASE_7_COMPLETION_REPORT.md"
    ]
    for rf in root_files:
        p = ROOT / rf
        if p.exists():
            shutil.copy2(p, STAGE_DIR / rf)

    # Phase 1 Remediation Deliverables & Black Swan Summary
    rem_dst = STAGE_DIR / "docs" / "remediation"
    rem_dst.mkdir(parents=True, exist_ok=True)
    rem_src = ROOT / "executioner" / "remediation"
    if rem_src.exists():
        for f in ["PHASE1_REMEDIATION_REPORT.md", "PHASE1_CHANGED_FILES.md", "PHASE1_REGRESSION_MATRIX.md", "PHASE1_BASELINE_VS_FIXED.json"]:
            fp = rem_src / f
            if fp.exists():
                shutil.copy2(fp, rem_dst / f)

    # Clean out any accidental cache files from stage
    for pyc in STAGE_DIR.rglob("__pycache__"):
        shutil.rmtree(pyc, ignore_errors=True)
    for ext in [".pyc", ".pyo", ".log"]:
        for f in STAGE_DIR.rglob(f"*{ext}"):
            f.unlink(missing_ok=True)

    print("Staging assembly complete.")


def create_canonical_zip():
    print(f"Creating canonical archive at {FINAL_ZIP}...")
    if FINAL_ZIP.exists():
        FINAL_ZIP.unlink()

    file_entries = []
    total_uncompressed = 0

    with zipfile.ZipFile(FINAL_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root_path, dirs, files in os.walk(STAGE_DIR):
            dirs.sort()
            for file in sorted(files):
                full_path = Path(root_path) / file
                rel_path = full_path.relative_to(STAGE_DIR)
                arc_name = f"phoenix_eval_submission/{rel_path.as_posix()}"
                zf.write(full_path, arcname=arc_name)
                fsize = full_path.stat().st_size
                total_uncompressed += fsize
                file_entries.append({
                    "archive_path": arc_name,
                    "size_bytes": fsize,
                    "sha256": compute_sha256(full_path)
                })

    zip_size = FINAL_ZIP.stat().st_size
    zip_sha256 = compute_sha256(FINAL_ZIP)

    print(f"Canonical ZIP created successfully.")
    print(f"  Entries count:       {len(file_entries)}")
    print(f"  Archive Size:        {zip_size / (1024*1024):.2f} MB ({zip_size} bytes)")
    print(f"  Uncompressed Size:   {total_uncompressed / (1024*1024):.2f} MB ({total_uncompressed} bytes)")
    print(f"  SHA-256 Digest:      {zip_sha256}")

    # Write FINAL_SHA256.txt
    sha_file = RELEASE_DIR / "FINAL_SHA256.txt"
    sha_file.write_text(f"{zip_sha256}  phoenix_eval_final_submission.zip\n", encoding="utf-8")

    # Write FINAL_ARCHIVE_MANIFEST.json
    manifest = {
        "benchmark": "PHOENIX-EVAL",
        "archive_file": "phoenix_eval_final_submission.zip",
        "archive_sha256": zip_sha256,
        "entry_count": len(file_entries),
        "archive_size_bytes": zip_size,
        "uncompressed_size_bytes": total_uncompressed,
        "compression_ratio": round(total_uncompressed / max(1, zip_size), 2),
        "files": file_entries
    }
    manifest_file = RELEASE_DIR / "FINAL_ARCHIVE_MANIFEST.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return manifest


def verify_extracted_archive():
    print(f"Extracting {FINAL_ZIP} to {EXTRACT_DIR} for independent verification...")
    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(FINAL_ZIP, "r") as zf:
        zf.extractall(EXTRACT_DIR)

    extracted_root = EXTRACT_DIR / "phoenix_eval_submission"
    assert extracted_root.exists(), f"Expected {extracted_root} to exist!"

    results = {}

    # 1. Run pytest suite from extracted root
    print("Running complete pytest suite from extracted package...")
    cmd_pytest = [sys.executable, "-m", "pytest", "tests/", "-q"]
    res_pytest = subprocess.run(cmd_pytest, cwd=str(extracted_root), capture_output=True, text=True)
    print(f"  Pytest Exit Code: {res_pytest.returncode}")
    print(f"  Output Summary: {res_pytest.stdout.strip().splitlines()[-1] if res_pytest.stdout.strip() else ''}")
    results["pytest"] = {
        "command": "python -m pytest tests/ -q",
        "exit_code": res_pytest.returncode,
        "output": res_pytest.stdout.strip()
    }

    # 2. Run calibration suite from extracted root
    print("Running evaluator calibration suite from extracted package...")
    cmd_cal = [sys.executable, "-m", "phoenix_eval.main", "evaluate-calibration"]
    res_cal = subprocess.run(cmd_cal, cwd=str(extracted_root), capture_output=True, text=True)
    print(f"  Calibration Exit Code: {res_cal.returncode}")
    cal_pass = "Cases Passed:          42/42 (100.0%)" in res_cal.stdout
    print(f"  Cases 42/42 Passed: {cal_pass}")
    results["calibration"] = {
        "command": "python -m phoenix_eval.main evaluate-calibration",
        "exit_code": res_cal.returncode,
        "cases_passed_42_42": cal_pass,
        "output": res_cal.stdout.strip()
    }

    # 3. Run smoke test
    print("Running smoke test from extracted package...")
    cmd_smoke = [sys.executable, "-m", "phoenix_eval.main", "smoke-test", "--model", "mock-valid-migration"]
    res_smoke = subprocess.run(cmd_smoke, cwd=str(extracted_root), capture_output=True, text=True)
    print(f"  Smoke Test Exit Code: {res_smoke.returncode}")
    results["smoke_test"] = {
        "command": "python -m phoenix_eval.main smoke-test --model mock-valid-migration",
        "exit_code": res_smoke.returncode,
        "output": res_smoke.stdout.strip()
    }

    # 4. Run demo
    print("Running offline demo from extracted package...")
    cmd_demo = [sys.executable, "-m", "phoenix_eval.main", "demo"]
    res_demo = subprocess.run(cmd_demo, cwd=str(extracted_root), capture_output=True, text=True)
    print(f"  Demo Exit Code: {res_demo.returncode}")
    results["demo"] = {
        "command": "python -m phoenix_eval.main demo",
        "exit_code": res_demo.returncode,
        "output_length": len(res_demo.stdout)
    }

    # 5. Run analyze experiment
    print("Running offline analysis from extracted package...")
    cmd_anal = [sys.executable, "-m", "phoenix_eval.main", "analyze-experiment", "--experiment", "exp-phase6-balanced-001"]
    res_anal = subprocess.run(cmd_anal, cwd=str(extracted_root), capture_output=True, text=True)
    print(f"  Analysis Exit Code: {res_anal.returncode}")
    results["analysis"] = {
        "command": "python -m phoenix_eval.main analyze-experiment --experiment exp-phase6-balanced-001",
        "exit_code": res_anal.returncode,
        "output": res_anal.stdout.strip()
    }

    # 6. Verify required datasets and configs exist
    req_items = [
        "pyproject.toml", "README.md", "src/phoenix_eval/main.py",
        "datasets/scenarios", "datasets/tasks", "datasets/ground_truth", "datasets/calibration",
        "config/settings.yaml", "docs/ARCHITECTURE.md", "docs/JUDGE_QUICKSTART.md",
        "docs/remediation/PHASE1_REMEDIATION_REPORT.md"
    ]
    missing = [item for item in req_items if not (extracted_root / item).exists()]
    results["file_checks"] = {
        "verified_items": req_items,
        "missing_items": missing,
        "all_present": len(missing) == 0
    }
    print(f"  All required items present in extracted package: {len(missing) == 0}")

    return results


def main():
    assemble_stage()
    manifest = create_canonical_zip()
    verif = verify_extracted_archive()

    print("\n==================================================")
    print("   PHOENIX-EVAL RELEASE PACKAGING SUMMARY")
    print("==================================================")
    print(f"Final Archive:       {FINAL_ZIP}")
    print(f"Archive Size:        {manifest['archive_size_bytes'] / (1024*1024):.2f} MB")
    print(f"Archive SHA-256:     {manifest['archive_sha256']}")
    print(f"ZIP Entry Count:     {manifest['entry_count']}")
    print(f"Pytest Pass:         {verif['pytest']['exit_code'] == 0}")
    print(f"Calibration Pass:    {verif['calibration']['cases_passed_42_42']}")
    print(f"Smoke Test Pass:     {verif['smoke_test']['exit_code'] == 0}")
    print(f"Demo Pass:           {verif['demo']['exit_code'] == 0}")
    print(f"Analysis Pass:       {verif['analysis']['exit_code'] == 0}")
    print(f"All Files Present:   {verif['file_checks']['all_present']}")
    print("==================================================\n")

    # Write verification results to file
    verif_file = RELEASE_DIR / "VERIFICATION_EXECUTION_RESULTS.json"
    verif_file.write_text(json.dumps(verif, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
