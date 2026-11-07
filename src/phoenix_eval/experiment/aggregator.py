"""Experiment metrics aggregator and model comparison artifact generator."""

import csv
import json
import statistics
from pathlib import Path
from typing import Any, Optional

from phoenix_eval.benchmark.task_loader import load_tasks_from_dir
from phoenix_eval.core.logging import get_logger
from phoenix_eval.core.paths import ProjectPaths, get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.schemas.common import ExecutionStatus
from phoenix_eval.schemas.experiments import ExperimentConfig, ExperimentRunRecord

logger = get_logger("experiment.aggregator")


class ExperimentAggregator:
    """Aggregates execution records across models, tasks, and trials into statistical summaries."""

    def __init__(
        self,
        config: ExperimentConfig,
        runs: list[ExperimentRunRecord],
        task_metadata: Optional[dict[str, dict[str, Any]]] = None,
        paths: Optional[ProjectPaths] = None,
    ) -> None:
        self.config = config
        self.runs = runs
        self.task_metadata = task_metadata or {}
        self.paths = paths or get_paths()
        self._cached_tasks: Optional[dict[str, Any]] = None
        self._cached_scenarios: Optional[dict[str, Any]] = None

    def _ensure_metadata_cache(self) -> None:
        if self._cached_tasks is not None:
            return
        self._cached_tasks = {}
        self._cached_scenarios = {}
        for t_dir in [self.paths.generated_tasks_dir, self.paths.tasks_dir]:
            if t_dir.is_dir():
                for t in load_tasks_from_dir(t_dir):
                    self._cached_tasks[t.task_id] = t
        for s_dir in [self.paths.generated_scenarios_dir, self.paths.scenarios_dir]:
            if s_dir.is_dir():
                for s_file in s_dir.glob("*.json"):
                    try:
                        s_data = read_json(s_file)
                        scen_id = s_data.get("scenario_id") or s_file.stem
                        self._cached_scenarios[scen_id] = s_data
                    except Exception:
                        pass

    def compute_summary(self) -> dict[str, Any]:
        """Compute complete per-model and experiment-level metrics."""
        runs_by_model: dict[str, list[ExperimentRunRecord]] = {}
        for r in self.runs:
            runs_by_model.setdefault(r.model_identifier, []).append(r)

        models_summary: dict[str, Any] = {}

        for model_id, m_runs in runs_by_model.items():
            attempted = len(m_runs)
            completed_runs = [r for r in m_runs if r.execution_status == ExecutionStatus.COMPLETED]
            failed_runs = [r for r in m_runs if r.execution_status != ExecutionStatus.COMPLETED]
            completed_count = len(completed_runs)
            failed_count = len(failed_runs)
            completion_rate = round(completed_count / attempted, 4) if attempted > 0 else 0.0

            # Score aggregations (STRICT RULE: Exclude failed provider calls from score averages)
            raw_scores = [
                r.raw_weighted_score for r in completed_runs if r.raw_weighted_score is not None
            ]
            eff_scores = [
                r.effective_score for r in completed_runs if r.effective_score is not None
            ]

            mean_raw = round(statistics.mean(raw_scores), 2) if raw_scores else None
            median_raw = round(statistics.median(raw_scores), 2) if raw_scores else None
            mean_eff = round(statistics.mean(eff_scores), 2) if eff_scores else None
            median_eff = round(statistics.median(eff_scores), 2) if eff_scores else None

            # Trial score variation (standard deviation across trials)
            trial_std: Optional[float] = None
            if len(eff_scores) >= 2:
                trial_std = round(statistics.stdev(eff_scores), 2)

            # Safety metrics
            safety_passed = sum(1 for r in completed_runs if r.safety_gate_passed is True)
            safety_failed = sum(1 for r in completed_runs if r.safety_gate_passed is False)
            safety_failure_rate = (
                round(safety_failed / completed_count, 4) if completed_count > 0 else 0.0
            )
            critical_viols = sum(r.critical_violations_count for r in completed_runs)

            # Latency
            latencies = [r.latency_seconds for r in completed_runs]
            mean_latency = round(statistics.mean(latencies), 3) if latencies else 0.0

            # Token usage & Cost
            p_tokens = [r.prompt_tokens for r in completed_runs if r.prompt_tokens is not None]
            c_tokens = [
                r.completion_tokens for r in completed_runs if r.completion_tokens is not None
            ]
            tot_tokens = [r.total_tokens for r in completed_runs if r.total_tokens is not None]
            costs = [
                r.estimated_cost_usd for r in completed_runs if r.estimated_cost_usd is not None
            ]

            total_p_tokens = sum(p_tokens) if p_tokens else None
            total_c_tokens = sum(c_tokens) if c_tokens else None
            total_tokens = sum(tot_tokens) if tot_tokens else None
            total_cost = round(sum(costs), 6) if costs else None

            provider_name = m_runs[0].provider_name if m_runs else "unknown"
            is_mock = m_runs[0].is_mock if m_runs else False

            # Breakdowns by task family, domain, and difficulty
            by_family: dict[str, list[ExperimentRunRecord]] = {}
            by_domain: dict[str, list[ExperimentRunRecord]] = {}
            by_difficulty: dict[str, list[ExperimentRunRecord]] = {}

            for r in completed_runs:
                t_meta = self.task_metadata.get(r.task_id, {})
                fam = t_meta.get("family", "Unknown")
                dom = t_meta.get("domain", "Unknown")
                diff = t_meta.get("difficulty", "Unknown")

                # Fallback resolution for family (T01-T10)
                if fam == "Unknown" or fam in {
                    "COMPATIBILITY_ASSESSMENT",
                    "DEPENDENCY_DISCOVERY",
                    "EVIDENCE_VERIFICATION",
                    "MIGRATION_SEQUENCING",
                    "RISK_ASSESSMENT",
                }:
                    self._ensure_metadata_cache()
                    if self._cached_tasks and r.task_id in self._cached_tasks:
                        t_obj = self._cached_tasks[r.task_id]
                        if getattr(t_obj, "task_family", None):
                            fam = str(t_obj.task_family)
                    if fam == "Unknown" or len(fam) > 3:
                        parts = r.task_id.lower().split("-")
                        for part in parts:
                            if part.startswith("t") and len(part) == 3 and part[1:].isdigit():
                                fam = part.upper()
                                break

                # Fallback resolution for domain
                if dom == "Unknown":
                    self._ensure_metadata_cache()
                    if self._cached_tasks and r.task_id in self._cached_tasks:
                        t_obj = self._cached_tasks[r.task_id]
                        scen_ref = getattr(t_obj, "scenario_reference", None)
                        if (
                            scen_ref
                            and self._cached_scenarios
                            and scen_ref in self._cached_scenarios
                        ):
                            scen_data = self._cached_scenarios[scen_ref]
                            dom_custom = (
                                scen_data.get("metadata", {}).get("custom", {}).get("domain")
                            )
                            if dom_custom:
                                dom = str(dom_custom)
                            else:
                                for tag in scen_data.get("metadata", {}).get("tags", []):
                                    tag_u = tag.upper()
                                    if "BANK" in tag_u:
                                        dom = "BANKING_PAYMENTS"
                                        break
                                    elif "TELCO" in tag_u or "TELECOM" in tag_u:
                                        dom = "TELECOM_NETWORK"
                                        break
                                    elif "IDP" in tag_u or "IDENTITY" in tag_u:
                                        dom = "CLOUD_IDENTITY"
                                        break
                                    elif "GOV" in tag_u:
                                        dom = "GOVERNMENT_CRITICAL"
                                        break
                                    elif "ERP" in tag_u or "ENTERPRISE" in tag_u:
                                        dom = "ENTERPRISE_SERVICES"
                                        break

                    if dom == "Unknown":
                        t_lower = r.task_id.lower()
                        if "bank" in t_lower:
                            dom = "BANKING_PAYMENTS"
                        elif "telco" in t_lower:
                            dom = "TELECOM_NETWORK"
                        elif "idp" in t_lower or "cloud" in t_lower:
                            dom = "CLOUD_IDENTITY"
                        elif "gov" in t_lower:
                            dom = "GOVERNMENT_CRITICAL"
                        elif "erp" in t_lower or "ent" in t_lower:
                            dom = "ENTERPRISE_SERVICES"

                by_family.setdefault(fam, []).append(r)
                by_domain.setdefault(dom, []).append(r)
                by_difficulty.setdefault(diff, []).append(r)

            def _summarize_group(runs_group: list[ExperimentRunRecord]) -> dict[str, Any]:
                group_eff = [r.effective_score for r in runs_group if r.effective_score is not None]
                group_raw = [
                    r.raw_weighted_score for r in runs_group if r.raw_weighted_score is not None
                ]
                group_passed = sum(1 for r in runs_group if r.safety_gate_passed is True)
                return {
                    "count": len(runs_group),
                    "mean_raw_score": round(statistics.mean(group_raw), 2) if group_raw else 0.0,
                    "mean_effective_score": round(statistics.mean(group_eff), 2)
                    if group_eff
                    else 0.0,
                    "safety_pass_rate": round(group_passed / len(runs_group), 4)
                    if runs_group
                    else 0.0,
                }

            family_breakdown = {k: _summarize_group(v) for k, v in sorted(by_family.items())}
            domain_breakdown = {k: _summarize_group(v) for k, v in sorted(by_domain.items())}
            difficulty_breakdown = {
                k: _summarize_group(v) for k, v in sorted(by_difficulty.items())
            }

            models_summary[model_id] = {
                "model_identifier": model_id,
                "provider_name": provider_name,
                "is_mock": is_mock,
                "attempted_runs": attempted,
                "completed_runs": completed_count,
                "failed_runs": failed_count,
                "completion_rate": completion_rate,
                "mean_raw_score": mean_raw,
                "median_raw_score": median_raw,
                "mean_effective_score": mean_eff,
                "median_effective_score": median_eff,
                "trial_score_std": trial_std,
                "safety_gate_passed_count": safety_passed,
                "safety_gate_failed_count": safety_failed,
                "safety_gate_failure_rate": safety_failure_rate,
                "critical_violations_count": critical_viols,
                "mean_latency_seconds": mean_latency,
                "total_prompt_tokens": total_p_tokens,
                "total_completion_tokens": total_c_tokens,
                "total_tokens": total_tokens,
                "total_estimated_cost_usd": total_cost,
                "per_task_family": family_breakdown,
                "per_domain": domain_breakdown,
                "per_difficulty": difficulty_breakdown,
            }

        total_runs_count = len(self.runs)
        completed_all = sum(1 for r in self.runs if r.execution_status == ExecutionStatus.COMPLETED)
        failed_all = sum(1 for r in self.runs if r.execution_status != ExecutionStatus.COMPLETED)

        real_models = {k: v for k, v in models_summary.items() if not v["is_mock"]}
        mock_models = {k: v for k, v in models_summary.items() if v["is_mock"]}

        return {
            "experiment_id": self.config.experiment_id,
            "experiment_name": self.config.experiment_name,
            "total_runs": total_runs_count,
            "completed_runs": completed_all,
            "failed_runs": failed_all,
            "models_evaluated_count": len(models_summary),
            "real_models_count": len(real_models),
            "mock_models_count": len(mock_models),
            "models": models_summary,
            "real_models": real_models,
            "mock_models": mock_models,
        }

    def write_summary_json(self, target_path: Path) -> Path:
        """Export model summary dictionary to JSON file."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        summary = self.compute_summary()
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        return target_path

    def write_comparison_csv(self, target_path: Path) -> Path:
        """Export standardized model comparison table to CSV, separating real and mock models."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        summary = self.compute_summary()
        models = summary.get("models", {})

        fieldnames = [
            "model_identifier",
            "provider_name",
            "is_mock",
            "attempted_runs",
            "completed_runs",
            "failed_runs",
            "completion_rate",
            "mean_raw_score",
            "median_raw_score",
            "mean_effective_score",
            "median_effective_score",
            "trial_score_std",
            "safety_gate_failed_count",
            "safety_gate_failure_rate",
            "critical_violations_count",
            "mean_latency_seconds",
            "total_tokens",
            "total_estimated_cost_usd",
        ]

        # Order: Real models first (sorted by mean effective score descending), then mock models
        real_list = sorted(
            [m for m in models.values() if not m.get("is_mock")],
            key=lambda x: x.get("mean_effective_score") or 0.0,
            reverse=True,
        )
        mock_list = sorted(
            [m for m in models.values() if m.get("is_mock")],
            key=lambda x: x.get("model_identifier", ""),
        )
        sorted_models = real_list + mock_list

        with open(target_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m_data in sorted_models:
                row = {k: m_data.get(k) for k in fieldnames}
                writer.writerow(row)

        return target_path

    def write_markdown_summary(self, target_path: Path) -> Path:
        """Export publication-grade Markdown experiment summary with separated real and mock tables."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        summary = self.compute_summary()
        real_models = summary.get("real_models", {})
        mock_models = summary.get("mock_models", {})

        lines: list[str] = [
            f"# PHOENIX-EVAL Experiment Report: {self.config.experiment_name}",
            "",
            f"**Experiment ID:** `{self.config.experiment_id}`  ",
            f"**Execution Mode:** `{self.config.mode}`  ",
            f"**Total Runs Scheduled:** {summary.get('total_runs', 0)}  ",
            f"**Completed Runs:** {summary.get('completed_runs', 0)}  ",
            f"**Failed Runs:** {summary.get('failed_runs', 0)}  ",
            "",
        ]

        def _format_table(models_subset: dict[str, Any]) -> list[str]:
            tbl = [
                "| Model | Provider | Comp Rate | Raw Score (Mean/Med) | Effective Score (Mean/Med) | Safety Fail Rate | Critical Viols | Mean Latency |",
                "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
            ]
            for m_id, m in models_subset.items():
                comp_rate_str = f"{m['completion_rate'] * 100:.1f}%"
                raw_str = f"{m['mean_raw_score'] or 0.0:.1f} / {m['median_raw_score'] or 0.0:.1f}"
                eff_str = f"{m['mean_effective_score'] or 0.0:.1f} / {m['median_effective_score'] or 0.0:.1f}"
                safety_fail_str = (
                    f"{m['safety_gate_failure_rate'] * 100:.1f}% ({m['safety_gate_failed_count']})"
                )
                latency_str = f"{m['mean_latency_seconds']:.2f}s"
                tbl.append(
                    f"| `{m_id}` | {m['provider_name']} | {comp_rate_str} | {raw_str} | **{eff_str}** | {safety_fail_str} | {m['critical_violations_count']} | {latency_str} |"
                )
            return tbl

        if real_models:
            lines.extend(
                [
                    "## 1. Real Frontier AI Models Evaluation",
                    "",
                    *_format_table(real_models),
                    "",
                ]
            )

        if mock_models:
            section_num = 2 if real_models else 1
            lines.extend(
                [
                    f"## {section_num}. Simulated Baseline Models (Mock / Offline Testing)",
                    "",
                    "> [!NOTE]",
                    "> **Simulated Baseline:** These models represent deterministic offline mock fixtures used for pipeline validation and calibration, not real frontier model evaluations.",
                    "",
                    *_format_table(mock_models),
                    "",
                ]
            )

        lines.extend(
            [
                "> [!IMPORTANT]",
                "> **Safety-Gate Scoring Policy:** Effective score is vetoed to `0.0` upon any critical safety violation (e.g. cutting over unsupported algorithms, violating dependencies, certifying readiness with pending/failing tests).",
                "",
                "## Methodology & Scientific Validity",
                "",
                "- **Evaluator:** DeterministicEvaluator v3.0.0 (Zero LLM judge dependencies)",
                f"- **Trials per Task:** {self.config.number_of_trials}",
                f"- **Temperature:** {self.config.temperature}",
                "- **Ground Truth Isolation:** Evaluator ground truth loaded strictly post-response; model prompt contains zero solution criteria.",
                "",
            ]
        )

        all_models = {**real_models, **mock_models}
        if all_models:
            lines.extend(
                [
                    "## Breakdown Analysis (Task Families & Enterprise Domains)",
                    "",
                ]
            )
            for m_id, m in all_models.items():
                p_fam = m.get("per_task_family", {})
                p_dom = m.get("per_domain", {})
                lines.append(f"### Model: `{m_id}`")
                lines.append("")
                if p_fam:
                    lines.append("**Task Family Breakdown (T01–T10):**")
                    lines.append("")
                    lines.append("| Family | Runs | Mean Raw | Mean Eff | Safety Pass Rate |")
                    lines.append("| :--- | :---: | :---: | :---: | :---: |")
                    for fam_k, fam_v in sorted(p_fam.items()):
                        lines.append(
                            f"| **{fam_k}** | {fam_v['count']} | {fam_v['mean_raw_score']:.1f} | {fam_v['mean_effective_score']:.1f} | {fam_v['safety_pass_rate'] * 100:.1f}% |"
                        )
                    lines.append("")
                if p_dom:
                    lines.append("**Domain Breakdown:**")
                    lines.append("")
                    lines.append("| Domain | Runs | Mean Raw | Mean Eff | Safety Pass Rate |")
                    lines.append("| :--- | :---: | :---: | :---: | :---: |")
                    for dom_k, dom_v in sorted(p_dom.items()):
                        lines.append(
                            f"| `{dom_k}` | {dom_v['count']} | {dom_v['mean_raw_score']:.1f} | {dom_v['mean_effective_score']:.1f} | {dom_v['safety_pass_rate'] * 100:.1f}% |"
                        )
                    lines.append("")

        with open(target_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return target_path
