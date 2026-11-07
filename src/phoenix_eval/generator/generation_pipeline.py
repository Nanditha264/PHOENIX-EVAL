"""End-to-end synthetic benchmark generation pipeline, artifact serialization, and manifest creation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import write_json
from phoenix_eval.generator.config import (
    ArchitectureDomain,
    GenerationConfig,
)
from phoenix_eval.generator.ground_truth_generator import generate_ground_truth
from phoenix_eval.generator.metamorphic import (
    MetamorphicRelationType,
    run_metamorphic_test,
)
from phoenix_eval.generator.paired_cases import (
    PairedCaseType,
    PairedCaseValidator,
    generate_paired_case,
)
from phoenix_eval.generator.scenario_generator import generate_scenario_for_task_family
from phoenix_eval.generator.seed_manager import SeedManager, compute_deterministic_hash
from phoenix_eval.generator.task_generator import generate_task_for_scenario
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel

logger = get_logger("generator.pipeline")

DOMAIN_ABBR: dict[ArchitectureDomain, str] = {
    ArchitectureDomain.BANKING_PAYMENTS: "bank",
    ArchitectureDomain.TELECOM_NETWORK: "telco",
    ArchitectureDomain.CLOUD_IDENTITY: "idp",
    ArchitectureDomain.GOVERNMENT_CRITICAL: "gov",
    ArchitectureDomain.ENTERPRISE_SERVICES: "erp",
}

DIFFICULTIES = [
    DifficultyLevel.INTRODUCTORY,
    DifficultyLevel.INTERMEDIATE,
    DifficultyLevel.ADVANCED,
]


@dataclass(frozen=True)
class GenerationSummary:
    """Summary metrics of a completed generation run."""

    generation_id: str
    seed: int
    scenarios_generated: int
    tasks_generated: int
    ground_truth_generated: int
    paired_cases_generated: int
    metamorphic_tests_passed: int
    metamorphic_tests_total: int
    manifest_path: Path
    artifact_hashes: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "generation_id": self.generation_id,
            "seed": self.seed,
            "scenarios_generated": self.scenarios_generated,
            "tasks_generated": self.tasks_generated,
            "ground_truth_generated": self.ground_truth_generated,
            "paired_cases_generated": self.paired_cases_generated,
            "metamorphic_tests_passed": self.metamorphic_tests_passed,
            "metamorphic_tests_total": self.metamorphic_tests_total,
            "manifest_path": str(self.manifest_path),
            "total_artifacts": len(self.artifact_hashes),
        }


class GenerationPipeline:
    """Orchestrates reproducible synthetic benchmark generation."""

    def __init__(
        self, config: Optional[GenerationConfig] = None, paths: Optional[ProjectPaths] = None
    ) -> None:
        self.config = config or GenerationConfig()
        self.paths = paths or get_paths()
        self.seed_mgr = SeedManager(self.config.seed)

    def run(self) -> GenerationSummary:
        """Execute the complete generation pipeline and persist all benchmark artifacts."""
        gen_id = f"gen-{self.seed_mgr.next_id('pqc')}"
        logger.info(
            "Starting PHOENIX-EVAL Phase 2 generation run '%s' with seed %d...",
            gen_id,
            self.config.seed,
        )

        # Output paths
        root_gen = self.config.output_dir or self.paths.generated_dir
        scenarios_dir = root_gen / "scenarios"
        tasks_dir = root_gen / "tasks"
        gt_dir = root_gen / "ground_truth"
        manifests_dir = root_gen / "manifests"
        paired_dir = root_gen / "paired_cases"
        metamorphic_dir = root_gen / "metamorphic_cases"

        for p in (scenarios_dir, tasks_dir, gt_dir, manifests_dir, paired_dir, metamorphic_dir):
            p.mkdir(parents=True, exist_ok=True)

        artifact_hashes: dict[str, str] = {}
        scenarios: list[ScenarioModel] = []
        tasks: list[BenchmarkTask] = []
        ground_truths: list[dict[str, Any]] = []

        domain_counts: dict[str, int] = {}
        family_counts: dict[str, int] = {}
        diff_counts: dict[str, int] = {}

        # 1. Generate Ten Task Families with Multiple Variants
        domains = self.config.domains
        domain_idx = 0

        for family in self.config.task_families:
            for variant in range(1, self.config.variants_per_family + 1):
                domain = domains[domain_idx % len(domains)]
                domain_idx += 1

                difficulty = DIFFICULTIES[(variant - 1) % len(DIFFICULTIES)]
                abbr = DOMAIN_ABBR[domain]

                scen_id = f"scen-gen-{family.value.lower()}-{abbr}-{variant:02d}"
                task_id = f"task-gen-{family.value.lower()}-{abbr}-{variant:02d}"
                gt_id = f"gt-gen-{family.value.lower()}-{abbr}-{variant:02d}"

                # Generate Scenario
                scenario = generate_scenario_for_task_family(
                    scenario_id=scen_id,
                    task_family=family,
                    domain=domain,
                    seed_mgr=self.seed_mgr,
                    complexity=self.config.default_complexity,
                )

                # Generate Task
                task = generate_task_for_scenario(
                    task_id=task_id,
                    scenario=scenario,
                    task_family=family,
                    ground_truth_id=gt_id,
                    seed_mgr=self.seed_mgr,
                    difficulty=difficulty,
                )

                # Generate Ground Truth
                gt = generate_ground_truth(
                    task_id=task_id,
                    scenario=scenario,
                    task_family=family,
                    ground_truth_id=gt_id,
                )

                scenarios.append(scenario)
                tasks.append(task)
                ground_truths.append(gt)

                domain_counts[domain.value] = domain_counts.get(domain.value, 0) + 1
                family_counts[family.value] = family_counts.get(family.value, 0) + 1
                diff_counts[difficulty.value] = diff_counts.get(difficulty.value, 0) + 1

                # Write individual files
                scen_path = scenarios_dir / f"{scen_id}.json"
                task_path = tasks_dir / f"{task_id}.json"
                gt_path = gt_dir / f"{gt_id}.json"

                scen_data = scenario.model_dump(mode="json")
                task_data = task.model_dump(mode="json")

                write_json(scen_path, scen_data, indent=2)
                write_json(task_path, task_data, indent=2)
                write_json(gt_path, gt, indent=2)

                artifact_hashes[f"scenarios/{scen_id}.json"] = compute_deterministic_hash(scen_data)
                artifact_hashes[f"tasks/{task_id}.json"] = compute_deterministic_hash(task_data)
                artifact_hashes[f"ground_truth/{gt_id}.json"] = compute_deterministic_hash(gt)

        # 2. Generate Paired Benchmark Cases
        paired_results: list[dict[str, Any]] = []
        pair_types = list(PairedCaseType)
        for i in range(1, self.config.num_paired_cases + 1):
            ptype = pair_types[(i - 1) % len(pair_types)]
            pair_label = f"{ptype.value.lower().replace('_', '-')}-{i:02d}"
            pair_case = generate_paired_case(
                pair_type=ptype,
                pair_id=pair_label,
                seed_mgr=self.seed_mgr,
            )

            # Validate pair invariant
            valid, errs = PairedCaseValidator.validate_pair(pair_case)
            if not valid:
                logger.warning("Paired case %s failed validation: %s", pair_label, errs)

            # Save Scenario A, Scenario B, Task A, Task B, GT A, GT B
            for sc in (pair_case.scenario_a, pair_case.scenario_b):
                p = scenarios_dir / f"{sc.scenario_id}.json"
                d = sc.model_dump(mode="json")
                write_json(p, d, indent=2)
                artifact_hashes[f"scenarios/{sc.scenario_id}.json"] = compute_deterministic_hash(d)

            for tk in (pair_case.task_a, pair_case.task_b):
                p = tasks_dir / f"{tk.task_id}.json"
                d = tk.model_dump(mode="json")
                write_json(p, d, indent=2)
                artifact_hashes[f"tasks/{tk.task_id}.json"] = compute_deterministic_hash(d)

            for g in (pair_case.ground_truth_a, pair_case.ground_truth_b):
                p = gt_dir / f"{g['ground_truth_id']}.json"
                write_json(p, g, indent=2)
                artifact_hashes[f"ground_truth/{g['ground_truth_id']}.json"] = (
                    compute_deterministic_hash(g)
                )

            paired_results.append(pair_case.to_dict())

        paired_index_data = {"paired_cases": paired_results}
        paired_index_path = paired_dir / "paired_cases_index.json"
        write_json(paired_index_path, paired_index_data, indent=2)
        artifact_hashes["paired_cases/paired_cases_index.json"] = compute_deterministic_hash(
            paired_index_data
        )

        # 3. Generate Metamorphic Test Cases
        metamorphic_results: list[dict[str, Any]] = []
        mr_types = list(MetamorphicRelationType)
        meta_passed = 0

        for i in range(1, self.config.num_metamorphic_cases + 1):
            mr = mr_types[(i - 1) % len(mr_types)]
            m_res = run_metamorphic_test(
                relation_type=mr,
                test_id=f"meta-{mr.value.lower().replace('_', '-')}-{i:02d}",
                seed_mgr=self.seed_mgr,
            )
            if m_res.passed:
                meta_passed += 1
            metamorphic_results.append(m_res.to_dict())

        meta_index_data = {"metamorphic_tests": metamorphic_results}
        meta_index_path = metamorphic_dir / "metamorphic_results.json"
        write_json(meta_index_path, meta_index_data, indent=2)
        artifact_hashes["metamorphic_cases/metamorphic_results.json"] = compute_deterministic_hash(
            meta_index_data
        )

        # 4. Write Generation Manifest
        stats: dict[str, Any] = {
            "scenarios_generated": len(scenarios) + (len(paired_results) * 2),
            "tasks_generated": len(tasks) + (len(paired_results) * 2),
            "ground_truth_generated": len(ground_truths) + (len(paired_results) * 2),
            "paired_cases_generated": len(paired_results),
            "metamorphic_tests_total": len(metamorphic_results),
            "metamorphic_tests_passed": meta_passed,
            "domain_distribution": domain_counts,
            "task_family_distribution": family_counts,
            "difficulty_distribution": diff_counts,
        }

        manifest_data: dict[str, Any] = {
            "generation_id": gen_id,
            "generator_version": "0.2.0",
            "seed": self.config.seed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": self.config.model_dump(mode="json"),
            "statistics": stats,
            "artifact_hashes": artifact_hashes,
        }

        manifest_file = manifests_dir / f"generation_manifest_{gen_id}.json"
        write_json(manifest_file, manifest_data, indent=2)

        logger.info(
            "Generation run '%s' complete: %d scenarios, %d tasks, %d paired cases, %d/%d metamorphic tests passed.",
            gen_id,
            stats["scenarios_generated"],
            stats["tasks_generated"],
            stats["paired_cases_generated"],
            meta_passed,
            len(metamorphic_results),
        )

        return GenerationSummary(
            generation_id=gen_id,
            seed=self.config.seed,
            scenarios_generated=stats["scenarios_generated"],
            tasks_generated=stats["tasks_generated"],
            ground_truth_generated=stats["ground_truth_generated"],
            paired_cases_generated=stats["paired_cases_generated"],
            metamorphic_tests_passed=meta_passed,
            metamorphic_tests_total=len(metamorphic_results),
            manifest_path=manifest_file,
            artifact_hashes=artifact_hashes,
        )
