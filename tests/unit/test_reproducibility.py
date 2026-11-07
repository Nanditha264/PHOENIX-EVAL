"""Unit tests verifying deterministic generation reproducibility under fixed random seeds."""

import tempfile
from pathlib import Path

from phoenix_eval.generator.config import ArchitectureDomain, GenerationConfig, TaskFamily
from phoenix_eval.generator.generation_pipeline import GenerationPipeline
from phoenix_eval.generator.seed_manager import SeedManager, compute_deterministic_hash


def test_seed_manager_deterministic_sequence() -> None:
    """Verify that two SeedManagers initialized with the same seed yield identical sequences."""
    mgr1 = SeedManager(42)
    mgr2 = SeedManager(42)

    seq1 = [mgr1.next_id("test") for _ in range(10)]
    seq2 = [mgr2.next_id("test") for _ in range(10)]
    assert seq1 == seq2

    # Different seeds yield different sequences
    mgr3 = SeedManager(99)
    seq3 = [mgr3.next_id("test") for _ in range(10)]
    assert seq1 != seq3


def test_generation_pipeline_identical_hashes_under_same_seed() -> None:
    """Verify that running the pipeline twice with identical seeds produces identical artifact hashes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out1 = Path(tmp_dir) / "run1"
        out2 = Path(tmp_dir) / "run2"

        cfg1 = GenerationConfig(
            seed=1234,
            variants_per_family=1,
            task_families=[TaskFamily.T01_HIDDEN_DEPENDENCY, TaskFamily.T05_MIGRATION_ORDERING],
            domains=[ArchitectureDomain.BANKING_PAYMENTS],
            num_paired_cases=1,
            num_metamorphic_cases=2,
            output_dir=out1,
        )
        cfg2 = GenerationConfig(
            seed=1234,
            variants_per_family=1,
            task_families=[TaskFamily.T01_HIDDEN_DEPENDENCY, TaskFamily.T05_MIGRATION_ORDERING],
            domains=[ArchitectureDomain.BANKING_PAYMENTS],
            num_paired_cases=1,
            num_metamorphic_cases=2,
            output_dir=out2,
        )

        pipe1 = GenerationPipeline(config=cfg1)
        summary1 = pipe1.run()

        pipe2 = GenerationPipeline(config=cfg2)
        summary2 = pipe2.run()

        assert summary1.scenarios_generated == summary2.scenarios_generated
        assert summary1.tasks_generated == summary2.tasks_generated
        assert summary1.artifact_hashes == summary2.artifact_hashes


def test_deterministic_hashing_stability() -> None:
    """Verify that compute_deterministic_hash produces identical digests regardless of key insertion order."""
    dict_a = {"alpha": 1, "beta": [1, 2, 3], "gamma": {"x": True}}
    dict_b = {"gamma": {"x": True}, "alpha": 1, "beta": [1, 2, 3]}

    assert compute_deterministic_hash(dict_a) == compute_deterministic_hash(dict_b)


def test_full_input_hash_reproducibility() -> None:
    """Verify that compute_full_input_hash is reproducible and sensitive to all parameters."""
    from phoenix_eval.core.constants import BENCHMARK_SYSTEM_PROMPT
    from phoenix_eval.utils.hashing import compute_full_input_hash

    h1 = compute_full_input_hash(
        prompt="Analyze cryptographic architecture for migration",
        system_prompt=BENCHMARK_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=2048,
    )
    h2 = compute_full_input_hash(
        prompt="Analyze cryptographic architecture for migration",
        system_prompt=BENCHMARK_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=2048,
    )
    assert h1 == h2

    # Different system prompt
    h3 = compute_full_input_hash(
        prompt="Analyze cryptographic architecture for migration",
        system_prompt="Different system prompt",
        temperature=0.0,
        max_tokens=2048,
    )
    assert h1 != h3

    # Different temperature
    h4 = compute_full_input_hash(
        prompt="Analyze cryptographic architecture for migration",
        system_prompt=BENCHMARK_SYSTEM_PROMPT,
        temperature=0.7,
        max_tokens=2048,
    )
    assert h1 != h4

    # Different prompt text
    h5 = compute_full_input_hash(
        prompt="Different user prompt",
        system_prompt=BENCHMARK_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=2048,
    )
    assert h1 != h5
