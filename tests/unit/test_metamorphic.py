"""Unit tests verifying metamorphic invariant transformations and reasoning constraint shifts."""

import pytest

from phoenix_eval.generator.metamorphic import (
    MetamorphicRelationType,
    run_metamorphic_test,
)
from phoenix_eval.generator.seed_manager import SeedManager


@pytest.mark.parametrize("mr_type", list(MetamorphicRelationType))
def test_all_metamorphic_relations_evaluate_to_true(mr_type: MetamorphicRelationType) -> None:
    """Verify that all six metamorphic relations evaluate to True under property transformations."""
    seed_mgr = SeedManager(42)
    result = run_metamorphic_test(
        relation_type=mr_type,
        test_id=f"test-{mr_type.value.lower()}",
        seed_mgr=seed_mgr,
    )

    assert result.passed is True, f"Metamorphic relation {mr_type} failed: {result.message}"
    assert result.relation_type == mr_type
    assert result.baseline_value is not None
    assert result.transformed_value is not None

    d = result.to_dict()
    assert d["passed"] is True
    assert d["relation_type"] == mr_type.value
