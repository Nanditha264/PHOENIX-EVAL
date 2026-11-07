"""Regression tests for Phase 5.1 Defect 3: Metamorphic relation task pairing integrity."""

from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.metamorphic import METAMORPHIC_TASK_MAPPING, MetamorphicAnalyzer
from phoenix_eval.analysis.schemas import MetamorphicOutcome


def test_metamorphic_authoritative_mapping_exists() -> None:
    """Ensure all core metamorphic relations (MR1-MR6) have explicit task mapping definitions."""
    required_relations = [
        "MR1_STATUS_UNSUPPORTED",
        "MR2_STATUS_UNKNOWN",
        "MR3_INTEROP_TEST_FAIL",
        "MR4_ADD_CYCLE",
        "MR5_UNUSED_CRYPTO_REF",
        "MR6_REMOVE_VALIDATION",
    ]
    for rel in required_relations:
        assert rel in METAMORPHIC_TASK_MAPPING
        base_t, trans_t = METAMORPHIC_TASK_MAPPING[rel]
        assert base_t != trans_t
        assert base_t.endswith("-a")
        assert trans_t.endswith("-b")


def test_missing_mapped_tasks_marked_not_evaluable() -> None:
    """Ensure relations whose mapped tasks were not evaluated are strictly marked NOT_EVALUABLE."""
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-phase5-1-001")

    analyzer = MetamorphicAnalyzer()
    items = analyzer.analyze_experiment(data)

    # In exp-mock-phase5-1-001, only task-pair-hsm-support-01-a and -b were evaluated (MR1)
    # Relations MR2, MR3, MR4, MR5, MR6 must be NOT_EVALUABLE
    mr2_items = [it for it in items if it.relation_type == "MR2_STATUS_UNKNOWN"]
    assert len(mr2_items) > 0
    assert all(it.outcome == MetamorphicOutcome.NOT_EVALUABLE for it in mr2_items)

    mr3_items = [it for it in items if it.relation_type == "MR3_INTEROP_TEST_FAIL"]
    assert len(mr3_items) > 0
    assert all(it.outcome == MetamorphicOutcome.NOT_EVALUABLE for it in mr3_items)


def test_evaluated_mapped_tasks_preserve_invariants() -> None:
    """Ensure evaluated mapped tasks (MR1) correctly compute PRESERVED or VIOLATED."""
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-phase5-1-001")

    analyzer = MetamorphicAnalyzer()
    items = analyzer.analyze_experiment(data)

    mr1_items = [it for it in items if it.relation_type == "MR1_STATUS_UNSUPPORTED"]
    assert len(mr1_items) > 0
    # MR1 tasks were evaluated in exp-mock-phase5-1-001, so outcome must NOT be NOT_EVALUABLE
    for item in mr1_items:
        assert item.outcome in (MetamorphicOutcome.PRESERVED, MetamorphicOutcome.VIOLATED)
        assert item.baseline_run_id is not None
        assert item.transformed_run_id is not None
