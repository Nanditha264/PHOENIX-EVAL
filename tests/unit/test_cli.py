"""Unit tests for the CLI command-line entrypoint."""

import pytest

from phoenix_eval.main import (
    build_parser,
    cmd_inspect_scenario,
    cmd_inspect_task,
    cmd_list_scenarios,
    cmd_list_tasks,
    cmd_validate_config,
    cmd_validate_project,
)


def test_cli_parser_commands() -> None:
    """Verify that build_parser configures all required subcommands."""
    parser = build_parser()
    subparsers_action = [action for action in parser._actions if action.dest == "command"][0]
    expected_cmds = {
        "validate-config",
        "validate-project",
        "list-tasks",
        "list-scenarios",
        "inspect-task",
        "inspect-scenario",
        "run-experiment",
        "evaluate",
    }
    assert expected_cmds.issubset(set(subparsers_action.choices.keys()))


def test_cmd_validate_config(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify validate-config CLI execution returns 0 and prints status."""
    code = cmd_validate_config()
    captured = capsys.readouterr()
    assert code == 0
    assert "VALID [OK]" in captured.out


def test_cmd_validate_project(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify validate-project CLI execution returns 0 on healthy repository."""
    code = cmd_validate_project()
    captured = capsys.readouterr()
    assert code == 0
    assert "PASSED [OK]" in captured.out


def test_cmd_list_tasks(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify list-tasks CLI execution."""
    code = cmd_list_tasks()
    captured = capsys.readouterr()
    assert code == 0
    assert "Benchmark Tasks" in captured.out


def test_cmd_list_scenarios(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify list-scenarios CLI execution."""
    code = cmd_list_scenarios()
    captured = capsys.readouterr()
    assert code == 0
    assert "Enterprise Scenarios" in captured.out


def test_cmd_inspect_task(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify inspect-task CLI command for existing and missing task."""
    code_valid = cmd_inspect_task("task-seq-pqc-001")
    captured = capsys.readouterr()
    assert code_valid == 0
    assert "Task: task-seq-pqc-001" in captured.out

    code_missing = cmd_inspect_task("task-non-existent")
    assert code_missing == 1


def test_cmd_inspect_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify inspect-scenario CLI command for existing and missing scenario."""
    code_valid = cmd_inspect_scenario("scen-pqc-tls-banking-001")
    captured = capsys.readouterr()
    assert code_valid == 0
    assert "Scenario: scen-pqc-tls-banking-001" in captured.out
    assert "Topology Analysis" in captured.out

    code_missing = cmd_inspect_scenario("scen-non-existent")
    assert code_missing == 1


def test_cmd_inspect_generated_task_and_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify inspect-task and inspect-scenario successfully resolve generated tasks."""
    code_task = cmd_inspect_task("task-gen-t09-bank-02")
    captured = capsys.readouterr()
    assert code_task == 0
    assert "Task: task-gen-t09-bank-02" in captured.out

    code_scen = cmd_inspect_scenario("scen-gen-t09-bank-02")
    captured_scen = capsys.readouterr()
    assert code_scen == 0
    assert "Scenario: scen-gen-t09-bank-02" in captured_scen.out
