"""Unit tests for Phase 5 paired counterfactual and metamorphic relation analysis."""

from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.metamorphic import MetamorphicAnalyzer
from phoenix_eval.analysis.paired import PairedCaseAnalyzer
from phoenix_eval.analysis.schemas import (
    MetamorphicOutcome,
    PairedSensitivityOutcome,
)


def test_paired_analysis_on_existing_experiment():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    analyzer = PairedCaseAnalyzer()

    items = analyzer.analyze_experiment(data)
    # 5 paired cases in index x 2 models = 10 items
    assert len(items) == 10
    for item in items:
        # None of the paired tasks were in exp-mock-comparison-001 task set
        assert item.classification == PairedSensitivityOutcome.INSUFFICIENT_DATA
        assert "Neither Task A nor Task B was evaluated" in item.reasoning


def test_metamorphic_analysis_on_existing_experiment():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    analyzer = MetamorphicAnalyzer()

    items = analyzer.analyze_experiment(data)
    # 10 metamorphic tests in index x 2 models = 20 items
    assert len(items) == 20
    for item in items:
        # Metamorphic tasks were not in exp-mock-comparison-001 run set
        assert item.outcome == MetamorphicOutcome.NOT_EVALUABLE
        assert "did not contain matching baseline and transformed tasks" in item.details
