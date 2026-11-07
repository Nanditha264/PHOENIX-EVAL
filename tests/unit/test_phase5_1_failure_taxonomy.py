"""Regression tests for Phase 5.1 Defect 6: Failure taxonomy coverage, unknown violations, and incident extraction."""

import re
from pathlib import Path

from phoenix_eval.analysis.failures import FailureIntelligenceEngine
from phoenix_eval.analysis.ingestion import ExperimentIngestionValidator
from phoenix_eval.analysis.schemas import FailureCategory


def test_taxonomy_complete_coverage_across_codebase() -> None:
    """Assert 100% coverage of VIOLATION_TAXONOMY_MAP across all violation codes in src/."""
    engine = FailureIntelligenceEngine()

    # Discover all VIO_ codes defined across src/
    code_pattern = re.compile(r"VIO_[A-Z0-9_]+")
    discovered_codes: set[str] = set()

    src_dir = Path("src")
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for match in code_pattern.finditer(content):
            discovered_codes.add(match.group(0))

    assert len(discovered_codes) == 38

    cov = engine.compute_taxonomy_coverage(list(discovered_codes))
    assert cov["total_codes"] == 38
    assert cov["mapped_codes"] == 38
    assert cov["unmapped_codes"] == []
    assert cov["coverage_percentage"] == 100.0


def test_unknown_violation_returns_unclassified_never_safety() -> None:
    """Assert that unknown violation codes strictly map to UNCLASSIFIED, never defaulting to SAFETY."""
    engine = FailureIntelligenceEngine()

    # Test an unknown code that has words like 'SAFE' or 'DEP' or completely random
    assert engine.categorize_violation("VIO_UNKNOWN_SAFETY_NEW") == FailureCategory.UNCLASSIFIED
    assert engine.categorize_violation("VIO_NONEXISTENT_RULE") == FailureCategory.UNCLASSIFIED
    assert engine.categorize_violation("CUSTOM_ALERT_CODE") == FailureCategory.UNCLASSIFIED


def test_extract_incidents_includes_both_critical_and_non_critical() -> None:
    """Verify that extract_incidents extracts both critical and non-critical violations."""
    validator = ExperimentIngestionValidator()
    data = validator.ingest_experiment("exp-mock-phase5-1-001")

    engine = FailureIntelligenceEngine()
    incidents = engine.extract_incidents(data)

    assert len(incidents) > 0
    categories = {inc.category for inc in incidents}
    assert FailureCategory.PARSING in categories
    assert FailureCategory.PLANNING in categories or FailureCategory.SAFETY in categories

    # Also test synthetic report with explicit non_critical_violations
    from phoenix_eval.evaluation.evaluation_report import DetailedEvaluationReport

    test_report = DetailedEvaluationReport(
        evaluation_id="eval-test-non-crit",
        task_id="task-test",
        scenario_id="scen-test",
        model_identifier="test-model",
        contract_version="1.0.0",
        evaluator_version="3.0.0",
        is_valid_json=True,
        is_valid_contract=True,
        raw_weighted_score=75.0,
        effective_score=75.0,
        safety_gate_passed=True,
        overall_status="PASSED",
        critical_violations=[],
        non_critical_violations=[
            {
                "rule_name": "VIO_UNKNOWN_ASSUMED_SUPPORTED",
                "severity": "MAJOR",
                "description": "Compatibility assumed without evidence",
                "evidence": "comp-1",
            }
        ],
        authoritative_readiness_decision="MIGRATION_READY",
    )

    data.evaluation_reports[data.valid_runs[0].run_id] = test_report
    incidents_updated = engine.extract_incidents(data)
    non_crit_incidents = [
        inc for inc in incidents_updated if inc.violation_code == "VIO_UNKNOWN_ASSUMED_SUPPORTED"
    ]
    assert len(non_crit_incidents) == 1
    assert non_crit_incidents[0].category == FailureCategory.COMPATIBILITY
