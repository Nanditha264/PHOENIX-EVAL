"""Statistical engine for PHOENIX-EVAL Phase 5.

Provides descriptive statistics, Wilson score intervals for binomial proportions,
non-parametric percentile bootstrap confidence intervals, and paired model comparisons.
Strictly reproducible with seed control and standard-library math.
"""

import math
import random
import statistics
from typing import Optional

from phoenix_eval.analysis.schemas import (
    BootstrapConfidenceInterval,
    DescriptiveStats,
    PairedModelComparison,
    WilsonScoreInterval,
)
from phoenix_eval.core.logging import get_logger

logger = get_logger("analysis.statistics")


def calculate_descriptive_stats(values: list[float]) -> DescriptiveStats:
    """Calculate standard descriptive statistics for a sequence of numeric values.

    Args:
        values: List of numeric values (e.g. raw or effective scores).

    Returns:
        DescriptiveStats containing count, mean, median, std_dev, min_val, max_val.
    """
    if not values:
        return DescriptiveStats(
            count=0,
            mean=0.0,
            median=0.0,
            std_dev=0.0,
            min_val=0.0,
            max_val=0.0,
        )

    count = len(values)
    mean_val = float(statistics.mean(values))
    median_val = float(statistics.median(values))
    std_val = float(statistics.stdev(values)) if count > 1 else 0.0
    min_v = float(min(values))
    max_v = float(max(values))

    return DescriptiveStats(
        count=count,
        mean=round(mean_val, 4),
        median=round(median_val, 4),
        std_dev=round(std_val, 4),
        min_val=round(min_v, 4),
        max_val=round(max_v, 4),
    )


def calculate_wilson_interval(
    successes: int,
    total: int,
    confidence: float = 0.95,
) -> WilsonScoreInterval:
    """Calculate the Wilson score confidence interval for a binomial proportion.

    Preferred over normal approximation for evaluation benchmarks because it maintains
    strict nominal coverage even near 0.0 or 1.0 and with small denominators.

    Args:
        successes: Number of successes / positive outcomes (e.g., safety gate passed or failed).
        total: Total denominator / number of trials.
        confidence: Desired confidence level (default 0.95).

    Returns:
        WilsonScoreInterval with exact proportion and lower/upper bounds in [0.0, 1.0].
    """
    if total <= 0:
        return WilsonScoreInterval(
            count=0,
            successes=0,
            proportion=0.0,
            lower_bound=0.0,
            upper_bound=0.0,
            confidence_level=confidence,
        )

    # Standard normal critical value z for standard confidence levels
    z_table = {
        0.90: 1.6448536269514722,
        0.95: 1.959963984540054,
        0.99: 2.5758293035489004,
    }
    z = z_table.get(confidence, 1.959963984540054)

    p_hat = successes / total
    z_sq = z * z
    denom = 1.0 + (z_sq / total)
    center = (p_hat + (z_sq / (2.0 * total))) / denom
    margin = (z / denom) * math.sqrt(
        (p_hat * (1.0 - p_hat) / total) + (z_sq / (4.0 * total * total))
    )

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return WilsonScoreInterval(
        count=total,
        successes=successes,
        proportion=round(p_hat, 4),
        lower_bound=round(lower, 4),
        upper_bound=round(upper, 4),
        confidence_level=confidence,
    )


def calculate_bootstrap_ci(
    data: list[float],
    metric_name: str = "mean_score",
    resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapConfidenceInterval:
    """Compute non-parametric percentile bootstrap confidence intervals with task-level resampling.

    Args:
        data: List of metrics (e.g. task scores).
        metric_name: Description of the metric.
        resamples: Number of bootstrap iterations (default 1000).
        confidence: Confidence level (default 0.95).
        seed: Random seed for deterministic reproducibility.

    Returns:
        BootstrapConfidenceInterval with point mean and percentile interval.
    """
    if not data:
        return BootstrapConfidenceInterval(
            metric_name=metric_name,
            mean=0.0,
            lower_bound=0.0,
            upper_bound=0.0,
            confidence_level=confidence,
            resamples=resamples,
        )

    n = len(data)
    if n == 1:
        val = float(data[0])
        return BootstrapConfidenceInterval(
            metric_name=metric_name,
            mean=round(val, 4),
            lower_bound=round(val, 4),
            upper_bound=round(val, 4),
            confidence_level=confidence,
            resamples=resamples,
        )

    rng = random.Random(seed)
    bootstrap_means: list[float] = []

    for _ in range(resamples):
        sample = [data[rng.randint(0, n - 1)] for _ in range(n)]
        bootstrap_means.append(statistics.mean(sample))

    bootstrap_means.sort()

    alpha = 1.0 - confidence
    lower_idx = int(math.floor((alpha / 2.0) * resamples))
    upper_idx = int(math.ceil((1.0 - alpha / 2.0) * resamples)) - 1

    lower_idx = max(0, min(lower_idx, resamples - 1))
    upper_idx = max(0, min(upper_idx, resamples - 1))

    point_mean = float(statistics.mean(data))
    lower_b = float(bootstrap_means[lower_idx])
    upper_b = float(bootstrap_means[upper_idx])

    return BootstrapConfidenceInterval(
        metric_name=metric_name,
        mean=round(point_mean, 4),
        lower_bound=round(lower_b, 4),
        upper_bound=round(upper_b, 4),
        confidence_level=confidence,
        resamples=resamples,
    )


def calculate_paired_comparison(
    model_a_scores: dict[str, float],
    model_b_scores: dict[str, float],
    model_a_name: str = "Model A",
    model_b_name: str = "Model B",
    model_a_trial_count: int = 0,
    model_b_trial_count: int = 0,
    resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 42,
) -> PairedModelComparison:
    """Perform a paired statistical comparison between two models over identical tasks.

    Args:
        model_a_scores: Mapping from task_id to score for Model A.
        model_b_scores: Mapping from task_id to score for Model B.
        model_a_name: Identifier for Model A.
        model_b_name: Identifier for Model B.
        resamples: Number of bootstrap iterations.
        confidence: Confidence level.
        seed: Random seed for bootstrap.

    Returns:
        PairedModelComparison including mean difference, std dev, t-statistic, and bootstrap CI.
    """
    common_tasks = sorted(set(model_a_scores.keys()) & set(model_b_scores.keys()))
    n = len(common_tasks)

    if n == 0:
        return PairedModelComparison(
            model_a=model_a_name,
            model_b=model_b_name,
            common_tasks_count=0,
            model_a_trial_count=model_a_trial_count,
            model_b_trial_count=model_b_trial_count,
            mean_difference=0.0,
            std_difference=0.0,
            t_statistic=None,
            p_value=None,
            bootstrap_ci=None,
            interpretation="No common tasks found between models to perform paired comparison.",
        )

    differences = [model_a_scores[t] - model_b_scores[t] for t in common_tasks]
    mean_diff = float(statistics.mean(differences))
    std_diff = float(statistics.stdev(differences)) if n > 1 else 0.0

    t_stat: Optional[float] = None
    if n > 1 and std_diff > 1e-9:
        t_stat = round(mean_diff / (std_diff / math.sqrt(n)), 4)

    # Percentile bootstrap CI on mean difference
    boot_ci = calculate_bootstrap_ci(
        data=differences,
        metric_name="score_difference",
        resamples=resamples,
        confidence=confidence,
        seed=seed,
    )
    ci_tuple = (boot_ci.lower_bound, boot_ci.upper_bound)

    # Formulate defensible scientific interpretation
    if n < 30:
        caveat = f"Small sample size (N={n} < 30); interpret inferential statistics with caution."
    else:
        caveat = f"Sample size N={n} provides adequate task-level power."

    if ci_tuple[0] > 0.0:
        significance = (
            f"{model_a_name} significantly outperformed {model_b_name} "
            f"(95% bootstrap CI [{ci_tuple[0]}, {ci_tuple[1]}] excludes zero)."
        )
    elif ci_tuple[1] < 0.0:
        significance = (
            f"{model_b_name} significantly outperformed {model_a_name} "
            f"(95% bootstrap CI [{ci_tuple[0]}, {ci_tuple[1]}] excludes zero)."
        )
    else:
        significance = (
            f"No statistically significant difference between {model_a_name} and {model_b_name} "
            f"(95% bootstrap CI [{ci_tuple[0]}, {ci_tuple[1]}] spans zero)."
        )

    interpretation = f"{significance} {caveat}"

    return PairedModelComparison(
        model_a=model_a_name,
        model_b=model_b_name,
        common_tasks_count=n,
        model_a_trial_count=model_a_trial_count,
        model_b_trial_count=model_b_trial_count,
        mean_difference=round(mean_diff, 4),
        std_difference=round(std_diff, 4),
        t_statistic=t_stat,
        p_value=None,  # Exact p-value omitted in favor of non-parametric bootstrap CI
        bootstrap_ci=ci_tuple,
        interpretation=interpretation,
    )
