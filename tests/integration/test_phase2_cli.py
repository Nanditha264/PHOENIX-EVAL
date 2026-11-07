"""Integration tests verifying Phase 2 CLI subcommands."""

import tempfile
from pathlib import Path

from phoenix_eval.main import (
    cmd_generate_dataset,
    cmd_inspect_dataset,
    cmd_inspect_task_family,
    cmd_list_dataset_runs,
    cmd_run_metamorphic_tests,
    cmd_validate_dataset,
    cmd_validate_paired_cases,
)


def test_cli_phase2_commands_execution() -> None:
    """Verify that all Phase 2 CLI commands execute successfully and return code 0."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "gen"

        # 1. generate-dataset
        exit_code = cmd_generate_dataset(
            seed=42,
            variants_per_family=1,
            domain="BANKING_PAYMENTS",
            complexity="SMALL",
            task_family="T01",
            paired_cases=1,
            metamorphic_cases=2,
            output_dir=str(out_dir),
        )
        assert exit_code == 0

        # 2. validate-dataset
        exit_code = cmd_validate_dataset(dataset_dir=str(out_dir))
        assert exit_code == 0

        # 3. list-dataset-runs
        manifests_dir = out_dir / "manifests"
        exit_code = cmd_list_dataset_runs(manifests_dir=str(manifests_dir))
        assert exit_code == 0

        # 4. inspect-dataset
        manifest_file = next(manifests_dir.glob("generation_manifest_*.json"))
        exit_code = cmd_inspect_dataset(str(manifest_file))
        assert exit_code == 0

        # 5. inspect-task-family
        exit_code = cmd_inspect_task_family("T01")
        assert exit_code == 0

        # 6. validate-paired-cases
        paired_dir = out_dir / "paired_cases"
        exit_code = cmd_validate_paired_cases(paired_dir=str(paired_dir))
        assert exit_code == 0

        # 7. run-metamorphic-tests
        exit_code = cmd_run_metamorphic_tests(seed=42, output_dir=str(out_dir / "metamorphic_run"))
        assert exit_code == 0
