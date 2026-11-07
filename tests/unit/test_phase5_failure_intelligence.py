"""Unit tests for Phase 5 failure intelligence engine and pattern detector."""

from phoenix_eval.analysis.failures import FailureIntelligenceEngine
from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.patterns import FailurePatternDetector
from phoenix_eval.analysis.schemas import (
    FailureCategory,
    FailurePatternScope,
    FailureSeverity,
)


def test_failure_taxonomy_mapping():
    engine = FailureIntelligenceEngine()

    assert engine.categorize_violation("VIO_KNOWN_DEPENDENCY_OMITTED") == FailureCategory.DEPENDENCY
    assert engine.categorize_violation("VIO_CYCLE_IGNORED") == FailureCategory.DEPENDENCY
    assert (
        engine.categorize_violation("VIO_UNKNOWN_ASSUMED_SUPPORTED")
        == FailureCategory.COMPATIBILITY
    )
    assert engine.categorize_violation("VIO_UNSUPPORTED_CUTOVER") == FailureCategory.COMPATIBILITY
    assert engine.categorize_violation("VIO_UNSUPPORTED_EVIDENCE_CLAIM") == FailureCategory.EVIDENCE
    assert engine.categorize_violation("VIO_FAILED_TEST_IGNORED") == FailureCategory.EVIDENCE
    assert engine.categorize_violation("VIO_FALSE_VERIFICATION_CLAIM") == FailureCategory.SAFETY
    assert engine.categorize_violation("VIO_REQUIRED_TEST_MISSING") == FailureCategory.SAFETY
    assert engine.categorize_violation("VIO_DEPENDENCY_ORDER_REVERSED") == FailureCategory.PLANNING
    assert engine.categorize_violation("VIO_CONTRADICTORY_DECISION") == FailureCategory.UNCERTAINTY
    assert engine.categorize_violation("VIO_MALFORMED_RESPONSE") == FailureCategory.PARSING


def test_extract_incidents_and_frequency_matrix():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    engine = FailureIntelligenceEngine()

    incidents = engine.extract_incidents(data)
    assert len(incidents) == 8  # 4 runs x 2 models, deduplicated per run
    for inc in incidents:
        assert inc.category == FailureCategory.PARSING
        assert inc.violation_code == "VIO_MALFORMED_RESPONSE"
        assert inc.severity == FailureSeverity.CRITICAL

    matrix = engine.compute_failure_frequency_matrix(incidents)
    assert matrix["mock-model-v1"]["PARSING"] == 4
    assert matrix["mock-refusal-v1"]["PARSING"] == 4

    freqs = engine.compute_violation_code_frequencies(incidents)
    assert freqs["VIO_MALFORMED_RESPONSE"] == 8


def test_failure_pattern_detection_thresholds():
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-comparison-001")
    engine = FailureIntelligenceEngine()
    detector = FailurePatternDetector()

    incidents = engine.extract_incidents(data)
    patterns = detector.detect_patterns(incidents, data)

    # Both models ran across 2 tasks in 2 distinct domains (BANKING_PAYMENTS and TELECOM_NETWORK)
    assert len(patterns) == 2
    for p in patterns:
        assert p.category == FailureCategory.PARSING
        assert p.scope == FailurePatternScope.CROSS_DOMAIN_RECURRING
        assert p.confidence > 0.85
        assert p.number_of_affected_runs == 4
        assert len(p.supporting_task_ids) == 2
        assert "systematically breaches JSON syntax" in p.suggested_interpretation
