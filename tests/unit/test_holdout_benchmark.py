"""Unit tests for the hidden holdout benchmark suite, oracle independence, and evaluator (Phase 9)."""

import json
from pathlib import Path
import pytest

from phoenix_eval.benchmark.holdout import (
    HoldoutEvaluationSummary,
    HoldoutEvaluator,
    check_holdout_near_duplicates,
    generate_holdout_benchmark,
    validate_oracle_independence,
)
from phoenix_eval.benchmark.prompt_builder import PromptBuilder
from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.generator.config import ArchitectureDomain, TaskFamily
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel


@pytest.fixture
def holdout_paths():
    return get_paths()


def test_holdout_dataset_completeness(holdout_paths):
    """Verify holdout dataset contains exactly 60 tasks, scenarios, and ground truths."""
    manifest_file = holdout_paths.holdout_dir / "holdout_manifest.json"
    if not manifest_file.is_file():
        generate_holdout_benchmark(paths=holdout_paths)

    manifest = read_json(manifest_file)
    assert manifest["total_tasks"] == 60
    assert len(manifest["tasks"]) == 60

    tasks = list(holdout_paths.holdout_tasks_dir.glob("*.json"))
    scenarios = list(holdout_paths.holdout_scenarios_dir.glob("*.json"))
    ground_truths = list(holdout_paths.holdout_ground_truth_dir.glob("*.json"))

    assert len(tasks) == 60
    assert len(scenarios) == 60
    assert len(ground_truths) == 60


def test_holdout_task_families_coverage(holdout_paths):
    """Verify all 10 task families (T01-T10) are represented with exactly 6 variants each."""
    manifest_file = holdout_paths.holdout_dir / "holdout_manifest.json"
    manifest = read_json(manifest_file)

    family_counts = {}
    for t in manifest["tasks"]:
        fam = t["task_family"]
        family_counts[fam] = family_counts.get(fam, 0) + 1

    for family in TaskFamily:
        assert family.value in family_counts
        assert family_counts[family.value] == 6


def test_holdout_domains_and_difficulties_coverage(holdout_paths):
    """Verify all 5 architecture domains (12 each) and all 3 difficulty tiers (20 each) are balanced."""
    manifest_file = holdout_paths.holdout_dir / "holdout_manifest.json"
    manifest = read_json(manifest_file)

    domain_counts = {}
    diff_counts = {}
    for t in manifest["tasks"]:
        dom = t["domain"]
        diff = t["difficulty"]
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
        diff_counts[diff] = diff_counts.get(diff, 0) + 1

    # 5 domains * 12 tasks = 60 tasks
    for dom in ArchitectureDomain:
        assert domain_counts[dom.value] == 12

    # 3 difficulty levels * 20 tasks = 60 tasks
    for diff in (DifficultyLevel.INTRODUCTORY, DifficultyLevel.INTERMEDIATE, DifficultyLevel.ADVANCED):
        assert diff_counts[diff.value] == 20


def test_holdout_ground_truth_isolation(holdout_paths):
    """Verify prompt builder never accesses or leaks ground truth into model prompts."""
    manifest_file = holdout_paths.holdout_dir / "holdout_manifest.json"
    manifest = read_json(manifest_file)
    rec = manifest["tasks"][0]

    task_file = holdout_paths.holdout_tasks_dir / f"{rec['task_id']}.json"
    scen_file = holdout_paths.holdout_scenarios_dir / f"{rec['scenario_id']}.json"

    task = BenchmarkTask.model_validate(read_json(task_file))
    scen = ScenarioModel.model_validate(read_json(scen_file))

    prompt = PromptBuilder.build_model_prompt(task, scen)
    assert rec["ground_truth_id"] not in prompt
    assert "authoritative_readiness_decision" not in prompt
    assert "expected_violations" not in prompt


def test_holdout_near_duplicate_detection(holdout_paths):
    """Verify holdout scenarios are not trivial structural duplicates of development tasks."""
    res = check_holdout_near_duplicates(paths=holdout_paths)
    assert res["is_independent"] is True
    assert res["duplicate_count"] == 0
    assert res["total_holdout_scanned"] == 60


def test_oracle_independence_validation(holdout_paths):
    """Verify oracle independence: ground truth contains required specifications without evaluator execution."""
    manifest_file = holdout_paths.holdout_dir / "holdout_manifest.json"
    manifest = read_json(manifest_file)

    for rec in manifest["tasks"][:10]:
        gt_file = holdout_paths.holdout_ground_truth_dir / f"{rec['ground_truth_id']}.json"
        gt = read_json(gt_file)
        val = validate_oracle_independence(gt)
        assert val["is_valid"] is True
        assert val["has_decision"] is True
        assert val["has_ordering"] is True
        assert len(val["accepted_outcomes"]) > 0
        assert "oracle_generation_method" in gt


def test_holdout_evaluator_execution(holdout_paths):
    """Verify HoldoutEvaluator executes cleanly on valid and unsafe mock fixtures across the holdout suite."""
    evaluator = HoldoutEvaluator(paths=holdout_paths)

    summary_valid = evaluator.run_holdout_evaluation(
        model_identifier="mock-valid-migration",
        is_mock=True,
        fixture_name="valid_contract",
    )
    assert isinstance(summary_valid, HoldoutEvaluationSummary)
    assert summary_valid.total_tasks == 60
    assert summary_valid.mean_effective_score > 60.0
    assert summary_valid.safety_gate_pass_rate > 75.0
