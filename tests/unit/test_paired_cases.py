"""Unit tests validating adversarial paired benchmark cases and single-fact divergence."""

import pytest

from phoenix_eval.generator.paired_cases import (
    PairedCaseType,
    PairedCaseValidator,
    generate_paired_case,
)
from phoenix_eval.generator.seed_manager import SeedManager


@pytest.mark.parametrize("pair_type", list(PairedCaseType))
def test_generate_and_validate_all_paired_types(pair_type: PairedCaseType) -> None:
    """Verify that all paired case types generate valid pairs satisfying invariant validation."""
    seed_mgr = SeedManager(42)
    pair = generate_paired_case(
        pair_type=pair_type,
        pair_id=f"test-{pair_type.value.lower()}",
        seed_mgr=seed_mgr,
    )

    is_valid, errors = PairedCaseValidator.validate_pair(pair)
    assert is_valid is True, f"Paired validation failed for {pair_type}: {errors}"
    assert len(errors) == 0

    # Ensure metadata export contains expected fields
    d = pair.to_dict()
    assert d["pair_type"] == pair_type.value
    assert d["scenario_a_id"] == pair.scenario_a.scenario_id
    assert d["scenario_b_id"] == pair.scenario_b.scenario_id
    assert "expected_divergence" in d


def test_paired_case_divergence_properties() -> None:
    """Verify that paired scenarios diverge on the target property while preserving component counts."""
    seed_mgr = SeedManager(42)
    pair = generate_paired_case(
        pair_type=PairedCaseType.DEPENDENCY_CYCLE,
        pair_id="cycle-test-01",
        seed_mgr=seed_mgr,
    )

    # Component counts must be identical
    assert len(pair.scenario_a.system_components) == len(pair.scenario_b.system_components)

    # Dependency counts must differ by exactly 1 (the injected reverse back-edge)
    assert len(pair.scenario_b.dependencies) == len(pair.scenario_a.dependencies) + 1

    # Ground truth cycle detection must differ
    assert pair.ground_truth_a["cycle_detected"] is False
    assert pair.ground_truth_b["cycle_detected"] is True
