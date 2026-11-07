"""Integration tests verifying Phase 3 CLI commands end-to-end."""

from pathlib import Path

import pytest

from phoenix_eval.core.paths import get_paths
from phoenix_eval.main import (
    cmd_evaluate_calibration,
    cmd_evaluate_response,
    cmd_export_evaluations,
    cmd_inspect_evaluation,
    cmd_list_evaluations,
    cmd_validate_response,
)


@pytest.fixture
def calib_paths() -> tuple[Path, Path, Path]:
    paths = get_paths()
    resp_dir = paths.datasets_dir / "calibration" / "responses"
    kg_01 = resp_dir / "kg_01_valid_migration.json"
    kb_01 = resp_dir / "kb_01_reversed_order.json"
    ec_03 = resp_dir / "ec_03_malformed_truncated.txt"
    return kg_01, kb_01, ec_03


def test_cli_validate_response_valid(calib_paths: tuple[Path, Path, Path]) -> None:
    kg_01, _, _ = calib_paths
    code = cmd_validate_response(task_id="task-gen-t09-bank-02", input_path=str(kg_01))
    assert code == 0


def test_cli_validate_response_malformed(calib_paths: tuple[Path, Path, Path]) -> None:
    _, _, ec_03 = calib_paths
    code = cmd_validate_response(task_id="task-gen-t09-bank-02", input_path=str(ec_03))
    assert code == 1


def test_cli_evaluate_response_known_good(
    tmp_path: Path, calib_paths: tuple[Path, Path, Path]
) -> None:
    kg_01, _, _ = calib_paths
    code = cmd_evaluate_response(
        task_id="task-gen-t09-bank-02",
        input_path=str(kg_01),
        output_dir=str(tmp_path),
    )
    assert code == 0
    # Verify report JSON written
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1


def test_cli_evaluate_response_critical_violation(
    tmp_path: Path, calib_paths: tuple[Path, Path, Path]
) -> None:
    _, kb_01, _ = calib_paths
    code = cmd_evaluate_response(
        task_id="task-gen-t09-bank-02",
        input_path=str(kb_01),
        output_dir=str(tmp_path),
    )
    # Critical violation should return 1
    assert code == 1


def test_cli_evaluate_calibration() -> None:
    code = cmd_evaluate_calibration()
    assert code == 0


def test_cli_list_inspect_export_lifecycle(
    tmp_path: Path, calib_paths: tuple[Path, Path, Path]
) -> None:
    kg_01, _, _ = calib_paths
    # Generate an evaluation report in tmp_path
    cmd_evaluate_response(
        task_id="task-gen-t09-bank-02",
        input_path=str(kg_01),
        output_dir=str(tmp_path),
    )
    report_file = next(tmp_path.glob("*.json"))

    # 1. list-evaluations
    list_code = cmd_list_evaluations(eval_dir=str(tmp_path))
    assert list_code == 0

    # 2. inspect-evaluation
    inspect_code = cmd_inspect_evaluation(
        evaluation_id=report_file.stem,
        eval_dir=str(tmp_path),
    )
    assert inspect_code == 0

    # 3. export-evaluations
    export_csv = tmp_path / "test_export.csv"
    export_code = cmd_export_evaluations(
        eval_dir=str(tmp_path),
        output_path=str(export_csv),
    )
    assert export_code == 0
    assert export_csv.is_file()
    assert export_csv.stat().st_size > 0
