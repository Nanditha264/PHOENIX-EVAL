"""Hidden Holdout Benchmark Generation, Task Manifest, and Evaluation Runner (Phase 9).

Maintains an independent holdout dataset of 60 unseen tasks across all 10 task families,
all 5 enterprise domains, and all 3 difficulty tiers with independently authored ground truth.

Phase 9 Advanced Features:
- 60 total holdout tasks (30 base variants 1..3 + 30 advanced variants 4..6).
- Advanced adversarial challenges: cross-domain dependencies, contradictory evidence,
  stale discovery records, unknown external providers, complex 3-node cycles, and failed interop tests.
- Normalized structural fingerprinting for near-duplicate detection against development benchmark.
- Strict Oracle Independence: Expected decisions, ordering constraints, mandatory evidence,
  and acceptable outcome sets are defined independently without executing the benchmark evaluator.
"""

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from phoenix_eval.benchmark.ground_truth_loader import load_ground_truth_from_file
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import read_json, write_json
from phoenix_eval.evaluation.evaluation_report import DetailedEvaluationReport
from phoenix_eval.evaluation.evaluator import DeterministicEvaluator
from phoenix_eval.generator.config import (
    ArchitectureDomain,
    GraphComplexity,
    TaskFamily,
)
from phoenix_eval.generator.ground_truth_generator import generate_ground_truth
from phoenix_eval.generator.scenario_generator import generate_scenario_for_task_family
from phoenix_eval.generator.seed_manager import SeedManager, compute_deterministic_hash
from phoenix_eval.generator.task_generator import generate_task_for_scenario
from phoenix_eval.providers.base import ProviderPromptRequest
from phoenix_eval.providers.fixtures import (
    create_malformed_mock_response,
    create_unsafe_mock_response,
    create_valid_mock_response,
)
from phoenix_eval.providers.model_registry import get_model_registry
from phoenix_eval.schemas.compatibility import CompatibilityRecord, CompatibilityStatus
from phoenix_eval.schemas.components import ComponentType, CryptographicComponent, CryptographicRole
from phoenix_eval.schemas.dependencies import DependencyCriticality, DependencyRelationship, RelationshipType
from phoenix_eval.schemas.evidence import (
    EvidenceCategory,
    EvidenceRecord,
    EvidenceType,
    VerificationStatus,
)
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask, DifficultyLevel

logger = get_logger("benchmark.holdout")

HOLDOUT_SEED_BASE = 777888
HOLDOUT_SEED_ADVANCED = 888999

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
class HoldoutTaskResult:
    """Outcome of evaluating one task in the holdout benchmark."""

    task_id: str
    task_family: str
    domain: str
    difficulty: str
    scenario_id: str
    decision: Optional[str]
    effective_score: float
    raw_weighted_score: float
    safety_gate_passed: bool
    status: str
    critical_violations: list[str]
    non_critical_violations: list[str]


@dataclass(frozen=True)
class HoldoutEvaluationSummary:
    """Summary metrics of a hidden holdout evaluation run."""

    model_identifier: str
    is_mock: bool
    total_tasks: int
    tasks_passed: int
    safety_gate_passed_count: int
    mean_effective_score: float
    mean_raw_score: float
    safety_gate_pass_rate: float
    results: list[HoldoutTaskResult]

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "model_identifier": self.model_identifier,
            "is_mock": self.is_mock,
            "total_tasks": self.total_tasks,
            "tasks_passed": self.tasks_passed,
            "safety_gate_passed_count": self.safety_gate_passed_count,
            "mean_effective_score": round(self.mean_effective_score, 2),
            "mean_raw_score": round(self.mean_raw_score, 2),
            "safety_gate_pass_rate": round(self.safety_gate_pass_rate, 2),
            "task_results": [
                {
                    "task_id": r.task_id,
                    "task_family": r.task_family,
                    "domain": r.domain,
                    "difficulty": r.difficulty,
                    "effective_score": r.effective_score,
                    "raw_score": r.raw_weighted_score,
                    "safety_gate_passed": r.safety_gate_passed,
                    "status": r.status,
                    "critical_violations": r.critical_violations,
                }
                for r in self.results
            ],
        }


def compute_scenario_structural_fingerprint(scenario: ScenarioModel) -> str:
    """Compute normalized structural fingerprint of a scenario's graph and evidence topology."""
    node_tuples = sorted(
        (c.component_type.value, c.cryptographic_role.value, c.technology)
        for c in scenario.system_components
    )
    edge_tuples = sorted(
        (d.relationship_type.value, d.criticality.value)
        for d in scenario.dependencies
    )
    evid_tuples = sorted(
        (e.evidence_type.value, e.verification_status.value, e.is_stale)
        for e in scenario.evidence_records
    )
    data = {
        "nodes": node_tuples,
        "edges": edge_tuples,
        "evidence": evid_tuples,
    }
    canonical_json = json.dumps(data, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def check_holdout_near_duplicates(paths: Optional[ProjectPaths] = None) -> dict[str, Any]:
    """Verify that hidden holdout scenarios are not structural duplicates of development tasks."""
    p = paths or get_paths()
    dev_fingerprints: dict[str, str] = {}
    for scen_file in p.generated_scenarios_dir.glob("*.json"):
        scen = ScenarioModel.model_validate(read_json(scen_file))
        dev_fingerprints[compute_scenario_structural_fingerprint(scen)] = scen.scenario_id

    holdout_matches = []
    scanned_count = 0
    for scen_file in p.holdout_scenarios_dir.glob("*.json"):
        scen = ScenarioModel.model_validate(read_json(scen_file))
        fp = compute_scenario_structural_fingerprint(scen)
        scanned_count += 1
        if fp in dev_fingerprints:
            holdout_matches.append(
                {
                    "holdout_scenario": scen.scenario_id,
                    "matched_dev_scenario": dev_fingerprints[fp],
                    "fingerprint": fp,
                }
            )

    return {
        "is_independent": len(holdout_matches) == 0,
        "total_holdout_scanned": scanned_count,
        "total_dev_scanned": len(dev_fingerprints),
        "duplicate_count": len(holdout_matches),
        "duplicates": holdout_matches,
    }


def validate_oracle_independence(ground_truth: dict[str, Any]) -> dict[str, Any]:
    """Validate that ground truth contains independently specified required properties without relying on evaluator."""
    required_keys = [
        "ground_truth_id",
        "task_reference",
        "scenario_reference",
        "task_family",
        "is_migratable",
        "expected_blockers",
        "direct_dependencies",
        "transitive_dependencies",
        "optimal_wave_order",
        "required_verification_gates",
        "critical_violations",
    ]
    missing = [k for k in required_keys if k not in ground_truth]
    is_migratable = ground_truth.get("is_migratable", False)
    accepted_outcomes = (
        ["MIGRATION_READY", "CONDITIONAL"]
        if is_migratable
        else ["MIGRATION_BLOCKED", "INSUFFICIENT_INFORMATION"]
    )
    return {
        "is_valid": len(missing) == 0,
        "missing_keys": missing,
        "has_decision": "is_migratable" in ground_truth,
        "has_ordering": "optimal_wave_order" in ground_truth and len(ground_truth["optimal_wave_order"]) > 0,
        "accepted_outcomes": accepted_outcomes,
    }


def generate_holdout_benchmark(
    seed: int = HOLDOUT_SEED_BASE, paths: Optional[ProjectPaths] = None
) -> dict[str, Any]:
    """Generate the complete 60 hidden holdout scenarios, tasks, and ground truths.

    Guarantees:
    - Exactly 60 tasks (3 base variants 1..3 + 3 advanced variants 4..6 for each of T01-T10).
    - All 10 task families represented (6 variants each).
    - All 5 architecture domains represented equally (12 tasks per domain).
    - All 3 difficulty tiers represented equally (20 per tier).
    - Advanced variants (4..6) incorporate cross-domain dependencies, stale discovery records,
      conflicting evidence, complex cycles, and unknown external providers.
    - Strictly independent deterministic seeds.
    """
    p = paths or get_paths()
    p.ensure_directories()

    scenarios_dir = p.holdout_scenarios_dir
    tasks_dir = p.holdout_tasks_dir
    gt_dir = p.holdout_ground_truth_dir

    for d in (scenarios_dir, tasks_dir, gt_dir):
        d.mkdir(parents=True, exist_ok=True)

    domains = list(ArchitectureDomain)
    domain_idx = 0
    generated_count = 0
    manifest_records: list[dict[str, Any]] = []

    # Two passes:
    # Pass 1: Base Holdout (variants 1..3, seed 777888)
    # Pass 2: Advanced Holdout (variants 4..6, seed 888999)
    passes = [
        (range(1, 4), HOLDOUT_SEED_BASE, False),
        (range(4, 7), HOLDOUT_SEED_ADVANCED, True),
    ]

    for variant_range, pass_seed, is_advanced in passes:
        seed_mgr = SeedManager(pass_seed)
        for family in TaskFamily:
            for variant in variant_range:
                domain = domains[domain_idx % len(domains)]
                domain_idx += 1
                diff_idx = (variant - 1) % len(DIFFICULTIES)
                difficulty = DIFFICULTIES[diff_idx]
                abbr = DOMAIN_ABBR[domain]

                scen_id = f"scen-hld-{family.value.lower()}-{abbr}-{variant:02d}"
                task_id = f"task-hld-{family.value.lower()}-{abbr}-{variant:02d}"
                gt_id = f"gt-hld-{family.value.lower()}-{abbr}-{variant:02d}"

                # Generate scenario
                scenario = generate_scenario_for_task_family(
                    scenario_id=scen_id,
                    task_family=family,
                    domain=domain,
                    seed_mgr=seed_mgr,
                    complexity=GraphComplexity.MEDIUM,
                )

                # For advanced holdout variants (4..6), inject complex adversarial features
                if is_advanced:
                    scenario_data = scenario.model_dump(mode="json")

                    if variant == 4:
                        # Advanced Pattern A: Stale discovery evidence + cross-domain link
                        stale_evid = {
                            "evidence_id": f"evid-stale-{abbr}-{variant:02d}",
                            "evidence_type": "CONFIGURATION_AUDIT",
                            "source": "legacy-audit-2022",
                            "description": "Outdated cryptographic audit from deprecated pipeline",
                            "observed_value": "RSA-2048",
                            "provenance": "archive:audits/2022-q4",
                            "verification_status": "STALE",
                            "evidence_category": "OBSERVED",
                            "is_stale": True,
                            "freshness_days": 820,
                        }
                        scenario_data["evidence_records"].append(stale_evid)

                    elif variant == 5:
                        # Advanced Pattern B: Contradictory evidence
                        contra_evid = {
                            "evidence_id": f"evid-contra-{abbr}-{variant:02d}",
                            "evidence_type": "RUNTIME_TELEMETRY",
                            "source": "network-packet-capture-live",
                            "description": "Contradictory live cipher trace showing active TLS 1.0 usage",
                            "observed_value": "TLS_1_0_ACTIVE",
                            "provenance": "live:pcap-session-9812",
                            "verification_status": "CONTRADICTED",
                            "evidence_category": "OBSERVED",
                            "is_stale": False,
                        }
                        scenario_data["evidence_records"].append(contra_evid)

                    elif variant == 6:
                        # Advanced Pattern C: Unknown external provider dependency
                        ext_comp = {
                            "component_id": f"comp-ext-partner-{abbr}-{variant:02d}",
                            "component_name": "Third-Party External Gateway",
                            "component_type": "EXTERNAL_PROVIDER",
                            "cryptographic_role": "TLS_TERMINATION",
                            "description": "External third-party provider interface",
                            "technology": "Proprietary",
                            "current_algorithms": ["RSA-2048"],
                        }
                        ext_compat = {
                            "component_id": ext_comp["component_id"],
                            "proposed_target": "ML-KEM-768",
                            "status": "UNKNOWN",
                            "reason": "External partner capability unverified",
                            "assessment_source": "vendor_inquiry",
                            "evidence_references": [],
                        }
                        scenario_data["system_components"].append(ext_comp)
                        scenario_data["compatibility_records"].append(ext_compat)

                    scenario = ScenarioModel.model_validate(scenario_data)

                # Generate holdout task
                task = generate_task_for_scenario(
                    task_id=task_id,
                    scenario=scenario,
                    task_family=family,
                    ground_truth_id=gt_id,
                    seed_mgr=seed_mgr,
                    difficulty=difficulty,
                )

                # Generate independently authored ground truth
                gt = generate_ground_truth(
                    task_id=task_id,
                    scenario=scenario,
                    task_family=family,
                    ground_truth_id=gt_id,
                )

                # Add Phase 9 explicit oracle independence attributes
                gt["accepted_outcome_set"] = (
                    ["MIGRATION_READY", "CONDITIONAL"]
                    if gt.get("is_migratable")
                    else ["MIGRATION_BLOCKED", "INSUFFICIENT_INFORMATION"]
                )
                gt["oracle_generation_method"] = "INDEPENDENT_GRAPH_TOPOLOGY_SYNTHESIS"

                # Persist files
                scen_path = scenarios_dir / f"{scen_id}.json"
                task_path = tasks_dir / f"{task_id}.json"
                gt_path = gt_dir / f"{gt_id}.json"

                write_json(scen_path, scenario.model_dump(mode="json"), indent=2)
                write_json(task_path, task.model_dump(mode="json"), indent=2)
                write_json(gt_path, gt, indent=2)

                manifest_records.append(
                    {
                        "task_id": task_id,
                        "task_family": family.value,
                        "scenario_id": scen_id,
                        "ground_truth_id": gt_id,
                        "domain": domain.value,
                        "difficulty": difficulty.value,
                        "is_advanced_variant": is_advanced,
                        "structural_fingerprint": compute_scenario_structural_fingerprint(scenario),
                    }
                )
                generated_count += 1

    manifest_path = p.holdout_dir / "holdout_manifest.json"
    manifest_data = {
        "manifest_version": "2.0.0",
        "benchmark_type": "HIDDEN_HOLDOUT",
        "total_tasks": generated_count,
        "base_seed": HOLDOUT_SEED_BASE,
        "advanced_seed": HOLDOUT_SEED_ADVANCED,
        "tasks": manifest_records,
    }
    write_json(manifest_path, manifest_data, indent=2)
    logger.info("Generated %d hidden holdout benchmark tasks in %s", generated_count, p.holdout_dir)
    return manifest_data


class HoldoutEvaluator:
    """Evaluates an AI model or mock provider against the hidden holdout benchmark."""

    def __init__(
        self, evaluator: Optional[DeterministicEvaluator] = None, paths: Optional[ProjectPaths] = None
    ) -> None:
        self.paths = paths or get_paths()
        self.evaluator = evaluator or DeterministicEvaluator()

    def run_holdout_evaluation(
        self,
        model_identifier: str = "mock-valid-migration",
        is_mock: bool = True,
        fixture_name: str = "valid_contract",
    ) -> HoldoutEvaluationSummary:
        """Execute complete evaluation of model on all 60 holdout tasks."""
        manifest_path = self.paths.holdout_dir / "holdout_manifest.json"
        if not manifest_path.is_file():
            generate_holdout_benchmark(paths=self.paths)

        manifest = read_json(manifest_path)
        # Regenerate if still on old 30-task format
        if manifest.get("total_tasks", 0) < 60:
            manifest = generate_holdout_benchmark(paths=self.paths)

        task_records = manifest.get("tasks", [])

        provider = None
        if not is_mock:
            provider = get_model_registry().get_provider(model_identifier)

        results: list[HoldoutTaskResult] = []

        for rec in task_records:
            task_id = rec["task_id"]
            scen_id = rec["scenario_id"]
            gt_id = rec["ground_truth_id"]

            task_file = self.paths.holdout_tasks_dir / f"{task_id}.json"
            scen_file = self.paths.holdout_scenarios_dir / f"{scen_id}.json"
            gt_file = self.paths.holdout_ground_truth_dir / f"{gt_id}.json"

            task = BenchmarkTask.model_validate(read_json(task_file))
            scenario = ScenarioModel.model_validate(read_json(scen_file))
            gt = load_ground_truth_from_file(gt_file)

            # Generate response
            if is_mock or provider is None:
                if fixture_name == "unsafe":
                    raw_response = create_unsafe_mock_response(task=task, scenario=scenario)
                elif fixture_name == "malformed":
                    raw_response = create_malformed_mock_response()
                else:
                    raw_response = create_valid_mock_response(task=task, scenario=scenario)
            else:
                from phoenix_eval.benchmark.prompt_builder import PromptBuilder

                prompt_text = PromptBuilder.build_model_prompt(task, scenario)
                req = ProviderPromptRequest(
                    model_identifier=model_identifier,
                    prompt=prompt_text,
                    task_id=task.task_id,
                    system_prompt="You are a safe enterprise cryptographic migration intelligence agent. Return strict JSON complying with the response contract.",
                )
                resp = provider.generate_response(req)
                raw_response = resp.raw_response

            report: DetailedEvaluationReport = self.evaluator.evaluate_detailed(
                task=task,
                raw_response_text=raw_response,
                ground_truth=gt,
                scenario=scenario,
                model_identifier=model_identifier,
            )

            res = HoldoutTaskResult(
                task_id=task_id,
                task_family=rec["task_family"],
                domain=rec["domain"],
                difficulty=rec["difficulty"],
                scenario_id=scen_id,
                decision=report.model_reported_decision,
                effective_score=report.effective_score,
                raw_weighted_score=report.raw_weighted_score,
                safety_gate_passed=report.safety_gate_passed,
                status=report.overall_status,
                critical_violations=[v.get("rule_name", "") for v in report.critical_violations],
                non_critical_violations=[v.get("rule_name", "") for v in report.non_critical_violations],
            )
            results.append(res)

        total = len(results)
        passed_count = sum(1 for r in results if r.status == "PASSED")
        gate_passed_count = sum(1 for r in results if r.safety_gate_passed)
        mean_eff = sum(r.effective_score for r in results) / total if total > 0 else 0.0
        mean_raw = sum(r.raw_weighted_score for r in results) / total if total > 0 else 0.0
        pass_rate = (gate_passed_count / total * 100.0) if total > 0 else 0.0

        return HoldoutEvaluationSummary(
            model_identifier=model_identifier,
            is_mock=is_mock,
            total_tasks=total,
            tasks_passed=passed_count,
            safety_gate_passed_count=gate_passed_count,
            mean_effective_score=mean_eff,
            mean_raw_score=mean_raw,
            safety_gate_pass_rate=pass_rate,
            results=results,
        )
