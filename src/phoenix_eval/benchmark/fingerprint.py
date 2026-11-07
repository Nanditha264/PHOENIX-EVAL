"""Deterministic canonical dataset content fingerprinting for PHOENIX-EVAL experiments."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.utils.time import current_utc_timestamp

logger = get_logger("benchmark.fingerprint")


@dataclass(frozen=True)
class DatasetFingerprintResult:
    """Deterministic cryptographic fingerprint bundle characterizing benchmark dataset content."""

    dataset_fingerprint: str
    model_visible_dataset_fingerprint: str
    evaluator_dataset_fingerprint: str
    dataset_manifest_version: str = "1.0.0"
    fingerprint_algorithm: str = "sha256-canonical-json-v1"
    fingerprint_created_at: datetime = field(default_factory=current_utc_timestamp)
    model_visible_files_count: int = 0
    evaluator_files_count: int = 0


def canonical_json_bytes(data: Any) -> bytes:
    """Produce deterministic byte-for-byte canonical JSON serialization.

    Sorts all object keys recursively and enforces minimal standard whitespace separators.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def compute_file_canonical_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file's canonical representation."""
    raw_content = file_path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(raw_content)
        content_bytes = canonical_json_bytes(parsed)
    except Exception:
        # Fall back to UTF-8 normalized line endings for non-JSON text
        content_bytes = raw_content.replace("\r\n", "\n").encode("utf-8")

    return hashlib.sha256(content_bytes).hexdigest()


def compute_directory_files_fingerprint(
    files: list[Path],
    root_path: Path,
) -> tuple[str, int]:
    """Compute deterministic combined hash across a collection of files.

    Entries are sorted lexicographically by relative POSIX path.
    Each file contributes: `<relative_posix_path>:<canonical_sha256>`.
    """
    entries: list[str] = []
    valid_count = 0

    for path in sorted(files):
        if not path.is_file():
            continue
        try:
            rel_path = path.relative_to(root_path).as_posix()
        except ValueError:
            rel_path = path.name

        f_hash = compute_file_canonical_hash(path)
        entries.append(f"{rel_path}:{f_hash}")
        valid_count += 1

    manifest_str = "\n".join(sorted(entries))
    combined_hash = hashlib.sha256(manifest_str.encode("utf-8")).hexdigest()
    return combined_hash, valid_count


def compute_dataset_fingerprints(
    paths: Optional[ProjectPaths] = None,
    task_ids: Optional[list[str]] = None,
) -> DatasetFingerprintResult:
    """Compute deterministic cryptographic fingerprints for the benchmark dataset.

    Separates model-visible artifacts (tasks, scenarios, manifests) from evaluator-only
    ground-truth artifacts to ensure research integrity and detect dataset drift or tampering.

    Args:
        paths: Optional ProjectPaths instance (defaults to get_paths()).
        task_ids: Optional subset of task IDs to scope fingerprinting to.
            If None, fingerprints all files in the active dataset directories.

    Returns:
        DatasetFingerprintResult containing individual and combined fingerprints.
    """
    proj_paths = paths or get_paths()
    root = proj_paths.root

    model_visible_files: list[Path] = []
    evaluator_files: list[Path] = []

    if task_ids is not None:
        # Scoped mode: resolve exact files referenced by specified tasks
        task_set = set(task_ids)
        scenario_refs: set[str] = set()
        gt_refs: set[str] = set()

        # Find task files
        cand_task_dirs = [proj_paths.generated_tasks_dir, proj_paths.tasks_dir]
        for t_id in task_set:
            found_task_file = None
            for td in cand_task_dirs:
                cand = td / f"{t_id}.json"
                if cand.is_file():
                    found_task_file = cand
                    break
            if found_task_file:
                model_visible_files.append(found_task_file)
                try:
                    task_data = json.loads(found_task_file.read_text(encoding="utf-8"))
                    if "scenario_reference" in task_data:
                        scenario_refs.add(task_data["scenario_reference"])
                    if "ground_truth_reference" in task_data:
                        gt_refs.add(task_data["ground_truth_reference"])
                except Exception as err:
                    logger.warning(
                        "Error reading task file %s for references: %s", found_task_file, err
                    )

        # Find scenario files
        cand_scen_dirs = [proj_paths.generated_scenarios_dir, proj_paths.scenarios_dir]
        for s_ref in scenario_refs:
            for sd in cand_scen_dirs:
                cand = sd / f"{s_ref}.json"
                if cand.is_file():
                    model_visible_files.append(cand)
                    break

        # Find ground truth files
        cand_gt_dirs = [proj_paths.generated_ground_truth_dir, proj_paths.ground_truth_dir]
        for gt_ref in gt_refs:
            for gd in cand_gt_dirs:
                cand = gd / f"{gt_ref}.json"
                if cand.is_file():
                    evaluator_files.append(cand)
                    break
    else:
        # Global dataset mode: include all task, scenario, and ground truth files
        if proj_paths.tasks_dir.is_dir():
            model_visible_files.extend(proj_paths.tasks_dir.glob("*.json"))
        if proj_paths.scenarios_dir.is_dir():
            model_visible_files.extend(proj_paths.scenarios_dir.glob("*.json"))
        if proj_paths.generated_tasks_dir.is_dir():
            model_visible_files.extend(proj_paths.generated_tasks_dir.glob("*.json"))
        if proj_paths.generated_scenarios_dir.is_dir():
            model_visible_files.extend(proj_paths.generated_scenarios_dir.glob("*.json"))

        # Manifests and pairing structures
        manifest_path = proj_paths.datasets_dir / "manifest.json"
        if manifest_path.is_file():
            model_visible_files.append(manifest_path)

        gen_manifests_dir = proj_paths.datasets_dir / "generated" / "manifests"
        if gen_manifests_dir.is_dir():
            model_visible_files.extend(gen_manifests_dir.glob("*.json"))

        # Ground truth (evaluator-only boundary)
        if proj_paths.ground_truth_dir.is_dir():
            evaluator_files.extend(proj_paths.ground_truth_dir.glob("*.json"))
        if proj_paths.generated_ground_truth_dir.is_dir():
            evaluator_files.extend(proj_paths.generated_ground_truth_dir.glob("*.json"))

    mv_fp, mv_count = compute_directory_files_fingerprint(model_visible_files, root)
    gt_fp, gt_count = compute_directory_files_fingerprint(evaluator_files, root)

    combined_input = f"{mv_fp}:{gt_fp}".encode("utf-8")
    dataset_fp = hashlib.sha256(combined_input).hexdigest()

    return DatasetFingerprintResult(
        dataset_fingerprint=dataset_fp,
        model_visible_dataset_fingerprint=mv_fp,
        evaluator_dataset_fingerprint=gt_fp,
        dataset_manifest_version="1.0.0",
        fingerprint_algorithm="sha256-canonical-json-v1",
        fingerprint_created_at=current_utc_timestamp(),
        model_visible_files_count=mv_count,
        evaluator_files_count=gt_count,
    )
