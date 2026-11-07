"""Unit tests for performance, scale benchmarking, and graph complexity scaling."""

import json
import pytest

from phoenix_eval.benchmark.scale_benchmark import (
    build_scale_scenario,
    run_scale_benchmark,
    ScaleBenchmarkReport,
)
from phoenix_eval.evaluation.independent_graph_verifier import IndependentGraphVerifier


def test_scale_scenario_generation_structural_invariants():
    """Verify that scale scenarios across 100, 500, and 1000 nodes maintain strict structural DAG invariants."""
    for n in [100, 500, 1000]:
        scenario, task, gt, contract = build_scale_scenario(n, seed=42)

        assert len(scenario.system_components) == n
        assert len(scenario.dependencies) >= n  # Dense multi-tier dependencies
        assert len(scenario.evidence_records) == n
        assert len(contract.migration_plan) == n

        verifier = IndependentGraphVerifier(scenario)
        assert verifier.is_dag is True, f"Scenario with {n} nodes failed DAG invariant."
        assert len(verifier.cycles) == 0

        # Verify plan ordering is causally sound
        plan_res = verifier.verify_plan(contract.migration_plan)
        assert plan_res.is_valid is True
        assert len(plan_res.causal_violations) == 0


def test_scale_benchmark_execution_and_scaling_bounds():
    """Verify that scale benchmark executes without timeout or OOM, maintaining polynomial scaling."""
    report = run_scale_benchmark(sizes=[100, 500, 1000], seed=42)

    assert isinstance(report, ScaleBenchmarkReport)
    assert len(report.results) == 3
    assert report.linear_scaling_verified is True

    for pt in report.results:
        # Correctness invariants under scale
        assert pt.safety_gate_passed is True
        assert pt.overall_status == "PASSED"

        # Performance invariants: sub-second latency and minimal memory
        assert pt.full_evaluation_ms < 5000.0, f"Full eval exceeded 5s for {pt.num_components} nodes"
        assert pt.peak_memory_mb < 100.0, f"Peak memory exceeded 100MB for {pt.num_components} nodes"
        assert pt.throughput_components_per_sec > 500.0

    # Ensure 1000 nodes completes in under 2 seconds
    pt_1000 = report.results[-1]
    assert pt_1000.num_components == 1000
    assert pt_1000.full_evaluation_ms < 2000.0


def test_scale_benchmark_serialization_and_reporting():
    """Verify JSON export and summary table formatting."""
    report = run_scale_benchmark(sizes=[100, 500], seed=123)

    data = report.to_dict()
    assert "benchmark_timestamp" in data
    assert len(data["results"]) == 2
    json_str = json.dumps(data)
    assert len(json_str) > 0

    table = report.format_table()
    assert "Components" in table
    assert "Throughput" in table
    assert "100" in table
    assert "500" in table
