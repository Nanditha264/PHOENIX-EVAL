"""Integration tests verifying end-to-end generation pipeline and ground-truth isolation on generated artifacts."""

import tempfile
from pathlib import Path

from phoenix_eval.benchmark.prompt_builder import build_model_prompt
from phoenix_eval.data.repository import GroundTruthRepository
from phoenix_eval.generator.config import ArchitectureDomain, GenerationConfig, TaskFamily
from phoenix_eval.generator.generation_pipeline import GenerationPipeline


def test_generation_pipeline_end_to_end_and_ground_truth_isolation() -> None:
    """Verify that generation pipeline produces valid artifacts that strictly obey ground-truth isolation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "generated"

        cfg = GenerationConfig(
            seed=42,
            variants_per_family=1,
            task_families=[TaskFamily.T01_HIDDEN_DEPENDENCY, TaskFamily.T09_VALID_MIGRATION],
            domains=[ArchitectureDomain.BANKING_PAYMENTS],
            num_paired_cases=1,
            num_metamorphic_cases=2,
            output_dir=out_path,
        )

        pipeline = GenerationPipeline(config=cfg)
        summary = pipeline.run()

        assert summary.scenarios_generated >= 4
        assert summary.tasks_generated >= 4
        assert summary.manifest_path.is_file()

        # 1. Model task payload serialization test
        # Verify that task serialized for model consumption strictly excludes ground_truth_reference
        tasks_dir = out_path / "tasks"
        for t_file in tasks_dir.glob("*.json"):
            from phoenix_eval.benchmark.task_loader import load_task_from_file

            task = load_task_from_file(t_file)
            model_dict = task.to_model_dict()

            assert "ground_truth_reference" not in model_dict
            assert "task_id" in model_dict
            assert "task_instructions" in model_dict

        # 2. Prompt builder isolation test
        # Build model prompt using PromptBuilder and ensure no ground truth artifact content is leaked
        scenarios_dir = out_path / "scenarios"
        from phoenix_eval.benchmark.scenario_loader import load_scenario_from_file

        sample_scen = load_scenario_from_file(next(scenarios_dir.glob("*.json")))
        sample_task = load_task_from_file(next(tasks_dir.glob("*.json")))

        prompt = build_model_prompt(sample_task, sample_scen)
        assert sample_task.ground_truth_reference not in prompt
        assert "optimal_wave_order" not in prompt
        assert "critical_violations" not in prompt

        # 3. Evaluator retrieves ground truth independently
        gt_repo = GroundTruthRepository(ground_truth_dir=out_path / "ground_truth")
        assert gt_repo.has_ground_truth(sample_task.ground_truth_reference) is True
        gt_data = gt_repo.load_ground_truth(sample_task.ground_truth_reference)
        assert gt_data["ground_truth_id"] == sample_task.ground_truth_reference
        assert "optimal_wave_order" in gt_data
