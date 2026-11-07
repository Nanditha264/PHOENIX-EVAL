"""PHOENIX-EVAL Phase 5 Benchmark Execution, Results Analysis & Failure Intelligence."""

from phoenix_eval.analysis.comparability import ExperimentComparabilityEvaluator
from phoenix_eval.analysis.coordinator import Phase5AnalysisCoordinator
from phoenix_eval.analysis.failures import FailureIntelligenceEngine
from phoenix_eval.analysis.ingestion import (
    ExperimentIngestionValidator,
    ValidatedExperimentData,
)
from phoenix_eval.analysis.metamorphic import MetamorphicAnalyzer
from phoenix_eval.analysis.paired import PairedCaseAnalyzer
from phoenix_eval.analysis.patterns import FailurePatternDetector
from phoenix_eval.analysis.performance import BenchmarkPerformanceAnalyzer
from phoenix_eval.analysis.report_generator import ResearchReportGenerator
from phoenix_eval.analysis.schemas import (
    AnalysisManifest,
    BootstrapConfidenceInterval,
    ComparabilityAssessment,
    ComparabilityClassification,
    DescriptiveStats,
    DifficultyMetrics,
    DimensionMetrics,
    DomainMetrics,
    FailureCategory,
    FailureIncident,
    FailurePattern,
    FailurePatternScope,
    FailureSeverity,
    IngestionRecordStatus,
    IngestionReport,
    MetamorphicAnalysisItem,
    MetamorphicOutcome,
    ModelPairComparability,
    ModelTaskTrialConsistency,
    OverallModelMetrics,
    PairedCaseAnalysisItem,
    PairedModelComparison,
    PairedSensitivityOutcome,
    RunValidationIssue,
    TaskFamilyMetrics,
    TrialConsistencyOutcome,
    WilsonScoreInterval,
)
from phoenix_eval.analysis.statistics import (
    calculate_bootstrap_ci,
    calculate_descriptive_stats,
    calculate_paired_comparison,
    calculate_wilson_interval,
)
from phoenix_eval.analysis.storage import AnalysisStorageManager

__all__ = [
    "AnalysisManifest",
    "AnalysisStorageManager",
    "BenchmarkPerformanceAnalyzer",
    "BootstrapConfidenceInterval",
    "ComparabilityAssessment",
    "ComparabilityClassification",
    "DescriptiveStats",
    "DifficultyMetrics",
    "DimensionMetrics",
    "DomainMetrics",
    "ExperimentComparabilityEvaluator",
    "ExperimentIngestionValidator",
    "FailureCategory",
    "FailureIncident",
    "FailureIntelligenceEngine",
    "FailurePattern",
    "FailurePatternDetector",
    "FailurePatternScope",
    "FailureSeverity",
    "IngestionRecordStatus",
    "IngestionReport",
    "MetamorphicAnalysisItem",
    "MetamorphicAnalyzer",
    "MetamorphicOutcome",
    "ModelPairComparability",
    "ModelTaskTrialConsistency",
    "OverallModelMetrics",
    "PairedCaseAnalysisItem",
    "PairedCaseAnalyzer",
    "PairedModelComparison",
    "PairedSensitivityOutcome",
    "Phase5AnalysisCoordinator",
    "ResearchReportGenerator",
    "RunValidationIssue",
    "TaskFamilyMetrics",
    "TrialConsistencyOutcome",
    "ValidatedExperimentData",
    "WilsonScoreInterval",
    "calculate_bootstrap_ci",
    "calculate_descriptive_stats",
    "calculate_paired_comparison",
    "calculate_wilson_interval",
]
