"""Unit tests for Phase 5 statistical engine."""

import math

from phoenix_eval.analysis.statistics import (
    calculate_bootstrap_ci,
    calculate_descriptive_stats,
    calculate_paired_comparison,
    calculate_wilson_interval,
)


def test_calculate_descriptive_stats_empty():
    stats = calculate_descriptive_stats([])
    assert stats.count == 0
    assert stats.mean == 0.0
    assert stats.median == 0.0
    assert stats.std_dev == 0.0


def test_calculate_descriptive_stats_normal():
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = calculate_descriptive_stats(data)
    assert stats.count == 5
    assert stats.mean == 30.0
    assert stats.median == 30.0
    assert stats.min_val == 10.0
    assert stats.max_val == 50.0
    assert stats.std_dev == round(math.sqrt(250.0), 4)


def test_calculate_wilson_interval():
    # 0 total
    res0 = calculate_wilson_interval(0, 0)
    assert res0.count == 0
    assert res0.proportion == 0.0
    assert res0.lower_bound == 0.0
    assert res0.upper_bound == 0.0

    # 0 successes out of 10
    res_zero = calculate_wilson_interval(0, 10, confidence=0.95)
    assert res_zero.proportion == 0.0
    assert res_zero.lower_bound == 0.0
    assert res_zero.upper_bound > 0.0
    assert res_zero.upper_bound < 0.35

    # 10 successes out of 10
    res_full = calculate_wilson_interval(10, 10, confidence=0.95)
    assert res_full.proportion == 1.0
    assert res_full.upper_bound == 1.0
    assert res_full.lower_bound > 0.65

    # Intermediate proportion
    res_half = calculate_wilson_interval(5, 10, confidence=0.95)
    assert res_half.proportion == 0.5
    assert 0.20 <= res_half.lower_bound <= 0.30
    assert 0.70 <= res_half.upper_bound <= 0.80


def test_calculate_bootstrap_ci():
    # Empty data
    res_empty = calculate_bootstrap_ci([])
    assert res_empty.mean == 0.0

    # Single element
    res_single = calculate_bootstrap_ci([42.0])
    assert res_single.mean == 42.0
    assert res_single.lower_bound == 42.0
    assert res_single.upper_bound == 42.0

    # Multi-element list
    data = [10.0, 12.0, 11.0, 13.0, 10.5]
    ci = calculate_bootstrap_ci(data, resamples=500, seed=123)
    assert ci.mean == round(sum(data) / len(data), 4)
    assert ci.lower_bound <= ci.mean <= ci.upper_bound


def test_calculate_paired_comparison():
    # Disjoint tasks
    res_disjoint = calculate_paired_comparison({"t1": 10.0}, {"t2": 20.0}, "A", "B")
    assert res_disjoint.common_tasks_count == 0
    assert res_disjoint.mean_difference == 0.0
    assert "No common tasks" in res_disjoint.interpretation

    # Identical scores
    scores_a = {f"t{i}": 50.0 for i in range(10)}
    scores_b = {f"t{i}": 50.0 for i in range(10)}
    res_identical = calculate_paired_comparison(scores_a, scores_b, "ModelA", "ModelB")
    assert res_identical.common_tasks_count == 10
    assert res_identical.mean_difference == 0.0
    assert "spans zero" in res_identical.interpretation
    assert "Small sample size" in res_identical.interpretation

    # Model A clearly superior
    scores_a_hi = {f"t{i}": 90.0 for i in range(15)}
    scores_b_lo = {f"t{i}": 10.0 for i in range(15)}
    res_diff = calculate_paired_comparison(scores_a_hi, scores_b_lo, "ModelA", "ModelB")
    assert res_diff.common_tasks_count == 15
    assert res_diff.mean_difference == 80.0
    assert "ModelA significantly outperformed ModelB" in res_diff.interpretation
