"""Deterministic evaluation engine coordinating parsing, dimension grading, and safety gate execution."""

from typing import Any, Optional

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json
from phoenix_eval.evaluation.compatibility_grader import (
    CompatibilityGrader,
    CompatibilityGradingResult,
)
from phoenix_eval.evaluation.constraint_grader import (
    ConstraintGrader,
    ConstraintGradingResult,
)
from phoenix_eval.evaluation.dependency_grader import (
    DependencyGrader,
    DependencyGradingResult,
)
from phoenix_eval.evaluation.evaluation_report import DetailedEvaluationReport
from phoenix_eval.evaluation.evidence_grader import EvidenceGrader, EvidenceGradingResult
from phoenix_eval.evaluation.explanation_grader import (
    ExplanationGrader,
    ExplanationGradingResult,
)
from phoenix_eval.evaluation.migration_plan_grader import (
    MigrationPlanGrader,
    MigrationPlanGradingResult,
)
from phoenix_eval.evaluation.response_parser import parse_model_response
from phoenix_eval.evaluation.response_validator import validate_response_semantics
from phoenix_eval.evaluation.safety_gate import SafetyGateEngine
from phoenix_eval.evaluation.scoring_engine import ScoringEngine, ScoringWeights
from phoenix_eval.evaluation.verification_gate_grader import (
    VerificationGateGrader,
    VerificationGateGradingResult,
)
from phoenix_eval.evaluator.base import BaseEvaluator
from phoenix_eval.schemas.common import SafetyGateStatus
from phoenix_eval.schemas.evaluation import (
    CriterionScore,
    CriticalViolation,
    EvaluationResult,
    ViolationSeverity,
)
from phoenix_eval.schemas.model_outputs import ModelResponse
from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask
from phoenix_eval.utils.identifiers import generate_id


class DeterministicEvaluator(BaseEvaluator):
    """Production evaluation engine for machine-checkable cryptographic migration benchmarks."""

    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
        pass_threshold: float = 70.0,
        evaluator_version: str = "3.0.0",
    ) -> None:
        super().__init__(
            evaluator_name="deterministic-evaluator", evaluator_version=evaluator_version
        )
        self.scoring_weights = weights or ScoringWeights()
        self.pass_threshold = pass_threshold

        # Initialize dimension graders
        self.dependency_grader = DependencyGrader(
            max_score=self.scoring_weights.dependency_identification
        )
        self.compatibility_grader = CompatibilityGrader(
            max_score=self.scoring_weights.compatibility_reasoning
        )
        self.migration_plan_grader = MigrationPlanGrader(
            max_score=self.scoring_weights.migration_plan_correctness
        )
        self.evidence_grader = EvidenceGrader(
            max_score=self.scoring_weights.evidence_and_uncertainty
        )
        self.verification_gate_grader = VerificationGateGrader(
            max_score=self.scoring_weights.validation_and_safety_gates
        )
        self.explanation_grader = ExplanationGrader(
            max_score=self.scoring_weights.explanation_and_traceability
        )
        self.constraint_grader = ConstraintGrader()

        self.safety_gate_engine = SafetyGateEngine()
        self.scoring_engine = ScoringEngine(
            weights=self.scoring_weights, pass_threshold=self.pass_threshold
        )

    def _resolve_scenario(
        self, task: BenchmarkTask, scenario: Optional[ScenarioModel] = None
    ) -> ScenarioModel:
        """Resolve scenario instance from parameter or repository search paths."""
        if scenario is not None:
            return scenario

        paths = get_paths()
        # Search generated scenarios first, then holdout scenarios, then seed scenarios
        cand_paths = [
            paths.generated_scenarios_dir / f"{task.scenario_reference}.json",
            paths.holdout_scenarios_dir / f"{task.scenario_reference}.json",
            paths.scenarios_dir / f"{task.scenario_reference}.json",
        ]
        for p in cand_paths:
            if p.is_file():
                data = read_json(p)
                return ScenarioModel.model_validate(data)

        raise FileNotFoundError(
            f"Scenario '{task.scenario_reference}' for task '{task.task_id}' not found in {cand_paths}."
        )

    def evaluate_detailed(
        self,
        task: BenchmarkTask,
        raw_response_text: str,
        ground_truth: dict[str, Any],
        scenario: Optional[ScenarioModel] = None,
        model_identifier: str = "unknown",
        model_version: str = "unknown",
    ) -> DetailedEvaluationReport:
        """Execute full deterministic evaluation and produce a DetailedEvaluationReport."""
        scen = self._resolve_scenario(task, scenario)

        # 1. Parse and validate response structure
        parsed = parse_model_response(raw_response_text)
        contract = parsed.model_contract

        semantic_errors: list[str] = []
        if contract:
            sem_res = validate_response_semantics(contract, scen)
            if not sem_res.is_semantically_consistent:
                semantic_errors.extend(sem_res.contradictory_decisions)
                if sem_res.unknown_components:
                    semantic_errors.append(
                        f"Non-existent component IDs referenced: {sem_res.unknown_components}."
                    )
                if sem_res.unknown_evidence_ids:
                    semantic_errors.append(
                        f"Non-existent evidence IDs referenced: {sem_res.unknown_evidence_ids}."
                    )
                if sem_res.unknown_test_ids:
                    semantic_errors.append(
                        f"Non-existent test IDs referenced: {sem_res.unknown_test_ids}."
                    )
                if sem_res.duplicate_tests:
                    semantic_errors.append(
                        f"Duplicate test reports detected: {sem_res.duplicate_tests}."
                    )
                if sem_res.duplicate_compatibilities:
                    semantic_errors.append(
                        f"Duplicate compatibility assessments detected: {sem_res.duplicate_compatibilities}."
                    )
                if sem_res.invalid_test_evidence:
                    semantic_errors.extend(sem_res.invalid_test_evidence)

        # 2. Run all individual dimension graders and constraint verifier with fail-safe isolation
        internal_fault_violations: list[CriticalViolation] = []

        try:
            dep_res = self.dependency_grader.grade(contract, scen, ground_truth)
        except Exception as exc:
            semantic_errors.append(f"Internal evaluator failure in dependency_grader: {type(exc).__name__}: {str(exc)}")
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description=f"Evaluator internal failure in dependency_grader: {type(exc).__name__}: {str(exc)}",
                severity=ViolationSeverity.CRITICAL,
                evidence=str(exc),
            )
            internal_fault_violations.append(viol)
            dep_res = DependencyGradingResult(
                dimension_name="dependency_identification",
                raw_score=0.0,
                max_score=self.scoring_weights.dependency_identification,
                normalized_score=0.0,
                passed=False,
                correct_edges=[],
                missing_edges=[],
                invented_edges=[],
                inverted_edges=[],
                deductions=[(self.scoring_weights.dependency_identification, f"Grader failed: {exc}")],
                violations=[viol],
                details={"error": str(exc)},
            )

        try:
            comp_res = self.compatibility_grader.grade(contract, scen, ground_truth)
        except Exception as exc:
            semantic_errors.append(f"Internal evaluator failure in compatibility_grader: {type(exc).__name__}: {str(exc)}")
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description=f"Evaluator internal failure in compatibility_grader: {type(exc).__name__}: {str(exc)}",
                severity=ViolationSeverity.CRITICAL,
                evidence=str(exc),
            )
            internal_fault_violations.append(viol)
            comp_res = CompatibilityGradingResult(
                dimension_name="compatibility_reasoning",
                raw_score=0.0,
                max_score=self.scoring_weights.compatibility_reasoning,
                normalized_score=0.0,
                passed=False,
                correct_assessments={},
                incorrect_assessments={},
                unknown_assumed_supported=[],
                unsupported_assumed_supported=[],
                deductions=[(self.scoring_weights.compatibility_reasoning, f"Grader failed: {exc}")],
                violations=[viol],
                details={"error": str(exc)},
            )

        try:
            plan_res = self.migration_plan_grader.grade(contract, scen, ground_truth)
        except Exception as exc:
            semantic_errors.append(f"Internal evaluator failure in migration_plan_grader: {type(exc).__name__}: {str(exc)}")
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description=f"Evaluator internal failure in migration_plan_grader: {type(exc).__name__}: {str(exc)}",
                severity=ViolationSeverity.CRITICAL,
                evidence=str(exc),
            )
            internal_fault_violations.append(viol)
            plan_res = MigrationPlanGradingResult(
                dimension_name="migration_plan_correctness",
                raw_score=0.0,
                max_score=self.scoring_weights.migration_plan_correctness,
                normalized_score=0.0,
                passed=False,
                is_dag=False,
                plan_valid=False,
                causal_violations=[],
                unsupported_scheduled=[],
                omitted_components=[],
                deductions=[(self.scoring_weights.migration_plan_correctness, f"Grader failed: {exc}")],
                violations=[viol],
                details={"error": str(exc)},
            )

        try:
            evid_res = self.evidence_grader.grade(contract, scen, ground_truth)
        except Exception as exc:
            semantic_errors.append(f"Internal evaluator failure in evidence_grader: {type(exc).__name__}: {str(exc)}")
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description=f"Evaluator internal failure in evidence_grader: {type(exc).__name__}: {str(exc)}",
                severity=ViolationSeverity.CRITICAL,
                evidence=str(exc),
            )
            internal_fault_violations.append(viol)
            evid_res = EvidenceGradingResult(
                dimension_name="evidence_and_uncertainty",
                raw_score=0.0,
                max_score=self.scoring_weights.evidence_and_uncertainty,
                normalized_score=0.0,
                passed=False,
                valid_citations=[],
                invalid_citations=[],
                unsupported_claims=[],
                uncertainties_calibrated=False,
                deductions=[(self.scoring_weights.evidence_and_uncertainty, f"Grader failed: {exc}")],
                violations=[viol],
                details={"error": str(exc)},
            )

        try:
            gate_res = self.verification_gate_grader.grade(contract, scen, ground_truth)
        except Exception as exc:
            semantic_errors.append(f"Internal evaluator failure in verification_gate_grader: {type(exc).__name__}: {str(exc)}")
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description=f"Evaluator internal failure in verification_gate_grader: {type(exc).__name__}: {str(exc)}",
                severity=ViolationSeverity.CRITICAL,
                evidence=str(exc),
            )
            internal_fault_violations.append(viol)
            gate_res = VerificationGateGradingResult(
                dimension_name="validation_and_safety_gates",
                raw_score=0.0,
                max_score=self.scoring_weights.validation_and_safety_gates,
                normalized_score=0.0,
                passed=False,
                readiness_blocked_by_gates=True,
                mandatory_tests_present=[],
                mandatory_tests_missing=[],
                failed_tests_detected=[],
                pending_tests_detected=[],
                skipped_tests_detected=[],
                deductions=[(self.scoring_weights.validation_and_safety_gates, f"Grader failed: {exc}")],
                violations=[viol],
                details={"error": str(exc)},
            )

        try:
            expl_res = self.explanation_grader.grade(contract, scen, ground_truth)
        except Exception as exc:
            semantic_errors.append(f"Internal evaluator failure in explanation_grader: {type(exc).__name__}: {str(exc)}")
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description=f"Evaluator internal failure in explanation_grader: {type(exc).__name__}: {str(exc)}",
                severity=ViolationSeverity.CRITICAL,
                evidence=str(exc),
            )
            internal_fault_violations.append(viol)
            expl_res = ExplanationGradingResult(
                dimension_name="explanation_and_traceability",
                raw_score=0.0,
                max_score=self.scoring_weights.explanation_and_traceability,
                normalized_score=0.0,
                passed=False,
                addresses_blockers=False,
                cites_telemetry=False,
                explains_wave_ordering=False,
                acknowledges_uncertainty=False,
                deductions=[(self.scoring_weights.explanation_and_traceability, f"Grader failed: {exc}")],
                violations=[viol],
                details={"error": str(exc)},
            )

        try:
            const_res = self.constraint_grader.grade(contract, scen, ground_truth)
        except Exception as exc:
            semantic_errors.append(f"Internal evaluator failure in constraint_grader: {type(exc).__name__}: {str(exc)}")
            viol = CriticalViolation(
                violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                rule_name="VIO_MALFORMED_RESPONSE",
                description=f"Evaluator internal failure in constraint_grader: {type(exc).__name__}: {str(exc)}",
                severity=ViolationSeverity.CRITICAL,
                evidence=str(exc),
            )
            internal_fault_violations.append(viol)
            const_res = ConstraintGradingResult(
                dimension_name="architectural_constraints",
                raw_score=0.0,
                max_score=10.0,
                normalized_score=0.0,
                passed=False,
                constraint_checks=[],
                precondition_findings=[],
                precondition_violations=[],
                deductions=[(10.0, f"Grader failed: {exc}")],
                violations=[viol],
                details={"error": str(exc)},
            )

        # 3. Consolidate violations across all dimensions
        all_violations: list[CriticalViolation] = [
            *dep_res.violations,
            *comp_res.violations,
            *plan_res.violations,
            *evid_res.violations,
            *gate_res.violations,
            *expl_res.violations,
            *const_res.violations,
        ]

        # Add malformed response violation if parsing failed
        if parsed.is_malformed:
            all_violations.append(
                CriticalViolation(
                    violation_id=generate_id("viol", "VIO_MALFORMED_RESPONSE"),
                    rule_name="VIO_MALFORMED_RESPONSE",
                    description="Response failed JSON syntax parsing or breached response contract schema.",
                    severity="CRITICAL",  # type: ignore[arg-type]
                    evidence="; ".join(parsed.errors)[:200],
                )
            )

        # 4. Evaluate Safety Gates
        safety_res = self.safety_gate_engine.evaluate(
            contract=contract,
            scenario=scen,
            collected_violations=all_violations,
            is_dag=plan_res.is_dag,
            readiness_blocked_by_gates=gate_res.readiness_blocked_by_gates,
        )

        # 5. Compute Weighted Scores
        dim_results = {
            "dependency_identification": dep_res,
            "compatibility_reasoning": comp_res,
            "migration_plan_correctness": plan_res,
            "evidence_and_uncertainty": evid_res,
            "validation_and_safety_gates": gate_res,
            "explanation_and_traceability": expl_res,
        }
        score_res = self.scoring_engine.calculate_score(
            dim_results,
            safety_res.safety_gate_passed,
            constraint_result=const_res,
        )

        # 6. Format Detailed Report
        eval_id = generate_id("eval", task.task_id)

        dim_scores_dict = {
            summary.dimension_name: {
                "raw_score": summary.raw_score,
                "max_score": summary.max_score,
                "normalized_score": summary.normalized_score,
                "weighted_contribution": summary.weighted_contribution,
                "deductions": [{"amount": d[0], "reason": d[1]} for d in summary.deductions],
            }
            for summary in score_res.dimension_summaries
        }

        report = DetailedEvaluationReport(
            evaluation_id=eval_id,
            task_id=task.task_id,
            scenario_id=scen.scenario_id,
            model_identifier=model_identifier,
            model_version=model_version,
            contract_version=contract.contract_version if contract else "unknown",
            evaluator_version=self.evaluator_version,
            is_valid_json=parsed.json_parsed,
            is_valid_contract=parsed.is_valid_contract,
            parsing_errors=parsed.errors,
            validation_errors=semantic_errors,
            raw_weighted_score=score_res.raw_weighted_score,
            effective_score=score_res.effective_score,
            safety_gate_passed=score_res.safety_gate_passed,
            overall_status=score_res.overall_status,
            dimension_scores=dim_scores_dict,
            critical_violations=[v.model_dump(mode="json") for v in safety_res.critical_violations],
            non_critical_violations=[
                v.model_dump(mode="json") for v in safety_res.non_critical_violations
            ],
            dependency_findings=dep_res.details,
            compatibility_findings=comp_res.details,
            migration_order_findings=plan_res.details,
            evidence_findings=evid_res.details,
            verification_gate_findings=gate_res.details,
            constraint_findings=const_res.details,
            cross_cutting_deductions=score_res.constraint_deductions,
            authoritative_readiness_decision=safety_res.readiness_decision,
            model_reported_decision=contract.decision.value if contract else None,
            evaluation_trace=safety_res.reasoning_trace,
            rubric_weights=self.scoring_weights.model_dump(),
        )

        return report

    def evaluate(
        self,
        task: BenchmarkTask,
        response: ModelResponse,
        ground_truth: dict[str, Any],
    ) -> EvaluationResult:
        """BaseEvaluator interface implementation returning standard EvaluationResult."""
        report = self.evaluate_detailed(
            task=task,
            raw_response_text=response.raw_response,
            ground_truth=ground_truth,
            model_identifier=response.model_identifier,
            model_version=response.model_version,
        )

        crit_scores = [
            CriterionScore(
                criterion_id=f"crit-{name}",
                score=data["normalized_score"],
                weight=self.scoring_weights.model_dump().get(name, 1.0),
                passed=data["raw_score"] >= (data["max_score"] * 0.70),
                reason=f"Scored {data['raw_score']}/{data['max_score']} (Deductions: {len(data['deductions'])}).",
            )
            for name, data in report.dimension_scores.items()
        ]

        critical_violations_objects = [
            CriticalViolation.model_validate(v) for v in report.critical_violations
        ]

        status_mapping = {
            "PASSED": "PASSED",
            "FAILED": "FAILED",
            "BLOCKED_BY_SAFETY_GATE": "BLOCKED_BY_SAFETY_GATE",
        }

        return EvaluationResult(
            evaluation_id=report.evaluation_id,
            task_id=task.task_id,
            response_id=response.response_id,
            criterion_scores=crit_scores,
            raw_score=report.effective_score,  # Phase 1 EvaluationResult raw_score is effective score
            safety_gate_status=SafetyGateStatus.PASSED
            if report.safety_gate_passed
            else SafetyGateStatus.FAILED,
            critical_violations=critical_violations_objects,
            false_positive_count=len(report.non_critical_violations),
            final_status=status_mapping.get(report.overall_status, "FAILED"),  # type: ignore[arg-type]
            evaluation_metadata={
                "evaluator_name": self.evaluator_name,
                "evaluator_version": self.evaluator_version,
                "raw_weighted_score": report.raw_weighted_score,
                "effective_score": report.effective_score,
                "authoritative_readiness_decision": report.authoritative_readiness_decision,
                "model_reported_decision": report.model_reported_decision,
                "detailed_report": report.model_dump(mode="json"),
            },
        )
