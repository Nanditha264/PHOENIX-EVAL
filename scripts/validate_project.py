"""Stand-alone project validation script for PHOENIX-EVAL Phase 1."""

import sys
from pathlib import Path

# Ensure src is on sys.path
root_dir = Path(__file__).resolve().parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from phoenix_eval.benchmark.prompt_builder import build_model_prompt
from phoenix_eval.benchmark.registry import BenchmarkRegistry
from phoenix_eval.core.config import get_settings
from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.repository import GroundTruthRepository, ScenarioRepository


def run_checks() -> int:
    print("=" * 60)
    print(" PHOENIX-EVAL Phase 1 Comprehensive Project Validation")
    print("=" * 60)

    failures = 0
    paths = get_paths(root_dir)

    # 1. Directory Checks
    print("\n[1/5] Verifying Directory Layout...")
    paths.ensure_directories()
    for name, p in [
        ("Config", paths.config_dir),
        ("Datasets", paths.datasets_dir),
        ("Scenarios", paths.scenarios_dir),
        ("Tasks", paths.tasks_dir),
        ("Ground Truth", paths.ground_truth_dir),
        ("Results", paths.results_dir),
        ("Docs", paths.docs_dir),
        ("Tests", paths.tests_dir),
    ]:
        if p.exists():
            print(f"  [OK] {name:<14} -> {p}")
        else:
            print(f"  [FAIL] {name:<14} missing at {p}")
            failures += 1

    # 2. Configuration Initialization Check (Without API keys)
    print("\n[2/5] Verifying Clean Configuration Initialization...")
    try:
        settings = get_settings()
        print(f"  [OK] Config loaded successfully for environment: {settings.environment}")
        print(f"  [OK] Default provider: {settings.providers.default_provider}")
        print("  [OK] Verification passed: System starts cleanly with zero API keys required.")
    except Exception as err:
        print(f"  [FAIL] Configuration error: {err}")
        failures += 1

    # 3. Registry Discovery & Cross-Artifact Integrity Check
    print("\n[3/5] Verifying Benchmark Discovery & Cross-Artifact Integrity...")
    registry = BenchmarkRegistry()
    summary = registry.discover_and_load(paths)
    gt_repo = GroundTruthRepository(paths.ground_truth_dir)
    gt_ids = set(gt_repo.list_ground_truth_ids())

    print(
        f"  [OK] Discovered {summary['scenarios_loaded']} scenario(s), "
        f"{summary['tasks_loaded']} task(s), {len(gt_ids)} ground truth(s)."
    )

    errors = registry.validate_registry_integrity(ground_truth_ids=gt_ids)
    if errors:
        for e in errors:
            print(f"  [FAIL] Integrity violation: {e}")
        failures += len(errors)
    else:
        print("  [OK] Cross-artifact referential integrity verified.")

    # 4. Ground Truth Isolation Architecture Check
    print("\n[4/5] Verifying Ground Truth Architectural Segregation...")
    # A. BenchmarkRegistry must not hold ground truth
    if hasattr(registry, "get_ground_truth") or hasattr(registry, "_ground_truths"):
        print("  [FAIL] BenchmarkRegistry contains ground-truth storage or access methods!")
        failures += 1
    else:
        print("  [OK] BenchmarkRegistry does not hold or expose ground truth.")

    # B. ScenarioRepository must not access ground truth
    scen_repo = ScenarioRepository(paths.scenarios_dir)
    if hasattr(scen_repo, "load_ground_truth"):
        print("  [FAIL] ScenarioRepository exposes ground-truth loading methods!")
        failures += 1
    else:
        print("  [OK] ScenarioRepository is strictly isolated from ground truth.")

    # C. Task model-facing payload excludes ground truth reference
    task = registry.get_task("task-seq-pqc-001")
    model_payload = task.to_model_dict()
    if "ground_truth_reference" in model_payload:
        print("  [FAIL] Model-facing task payload leaked ground_truth_reference!")
        failures += 1
    else:
        print("  [OK] Model-facing task payload strictly excludes ground_truth_reference.")

    # D. Prompt construction does not contain ground truth answers
    scenario = registry.get_scenario(task.scenario_reference)
    prompt = build_model_prompt(task, scenario)
    if "gt-seq-pqc-001" in prompt:
        print("  [FAIL] Model prompt leaked ground-truth reference string!")
        failures += 1
    else:
        print("  [OK] PromptBuilder generates clean model prompt with no ground truth references.")

    # 5. Core Pipeline Contract Check
    print("\n[5/5] Verifying Provider and Evaluator Pipeline Execution...")
    try:
        from phoenix_eval.evaluator.result import MockEvaluator
        from phoenix_eval.providers.base import MockModelProvider, ProviderPromptRequest

        provider = MockModelProvider()
        req = ProviderPromptRequest(task_id=task.task_id, prompt=prompt)
        resp = provider.generate_response(req)

        # Evaluator loads ground truth via GroundTruthRepository
        evaluator = MockEvaluator()
        gt = gt_repo.load_ground_truth(task.ground_truth_reference)
        eval_result = evaluator.evaluate(task, resp, gt)

        print(f"  [OK] Mock provider invocation: response_id={resp.response_id}")
        print(
            f"  [OK] Evaluator invocation: score={eval_result.raw_score}, status={eval_result.final_status}"
        )
    except Exception as err:
        print(f"  [FAIL] Provider or evaluator pipeline error: {err}")
        failures += 1

    print("\n" + "=" * 60)
    if failures == 0:
        print(" ALL CHECKS PASSED: PHOENIX-EVAL Phase 1 foundation is operational.")
        print("=" * 60)
        return 0
    else:
        print(f" CHECKS FAILED: {failures} issue(s) detected.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(run_checks())
