"""Prompt builder constructing model-facing prompts from tasks and scenarios.

Architectural Rule:
This module accepts ONLY model-visible tasks and scenarios.
It has zero access to evaluator ground truth and strictly omits all evaluator metadata.
"""

from phoenix_eval.schemas.scenarios import ScenarioModel
from phoenix_eval.schemas.tasks import BenchmarkTask


class PromptBuilder:
    """Constructs standardized prompts for model providers from benchmark tasks and scenarios."""

    @staticmethod
    def build_model_prompt(task: BenchmarkTask, scenario: ScenarioModel) -> str:
        """Construct a model-visible prompt string.

        Args:
            task: BenchmarkTask definition (instructions, criteria objectives, expected schema).
            scenario: ScenarioModel containing observable architectural components and evidence.

        Returns:
            Formatted prompt text ready for model consumption.
        """
        lines: list[str] = []

        # 1. Header & Task Identity
        lines.append(f"# BENCHMARK CHALLENGE: {task.task_name}")
        lines.append(f"Category: {task.task_category.value} | Difficulty: {task.difficulty.value}")
        lines.append("")
        lines.append("## Challenge Overview")
        lines.append(task.description.strip())
        lines.append("")

        # 2. Explicit Instructions
        lines.append("## Task Instructions")
        lines.append(task.task_instructions.strip())
        lines.append("")

        # 3. Expected Output Format
        if task.expected_output_schema:
            lines.append("## Expected Output Format")
            lines.append(
                "Produce a response that complies with the following JSON schema requirements:"
            )
            lines.append("```json")
            import json

            lines.append(json.dumps(task.expected_output_schema, indent=2))
            lines.append("```")
            lines.append("")

        # 4. Evaluation Objectives (Public Rubric)
        if task.evaluation_criteria:
            lines.append("## Evaluation Rubric Objectives")
            for crit in task.evaluation_criteria:
                crit_note = " (Safety-Critical)" if crit.is_safety_critical else ""
                lines.append(f"- **{crit.name}**{crit_note}: {crit.description}")
            lines.append("")

        # 5. Architecture Context
        lines.append("---")
        lines.append(f"# ENTERPRISE SCENARIO: {scenario.scenario_name}")
        lines.append(f"Scenario ID: {scenario.scenario_id}")
        lines.append(scenario.description.strip())
        lines.append("")

        # 6. System Components Inventory
        lines.append("## System Components")
        for comp in scenario.system_components:
            algos = ", ".join(comp.current_algorithms) if comp.current_algorithms else "None"
            lines.append(
                f"- **{comp.component_id}** ({comp.component_name}):\n"
                f"  Type: {comp.component_type.value} | Role: {comp.cryptographic_role.value}\n"
                f"  Technology: {comp.technology}\n"
                f"  Current Algorithms: {algos}\n"
                f"  Description: {comp.description}"
            )
        lines.append("")

        # 7. Discovered Dependencies
        lines.append("## Discovered Dependency Graph")
        for dep in scenario.dependencies:
            lines.append(
                f"- `{dep.source_component_id}` --[{dep.relationship_type.value}]--> `{dep.target_component_id}` "
                f"(Criticality: {dep.criticality.value}, Confidence: {dep.confidence})\n"
                f"  Context: {dep.description}"
            )
        lines.append("")

        # 8. Observed Evidence Records
        lines.append("## Discovered Evidence & Telemetry")
        for evid in scenario.evidence_records:
            lines.append(
                f"- **[{evid.evidence_id}]** {evid.evidence_type.value} (Category: {evid.evidence_category.value}, Status: {evid.verification_status.value})\n"
                f"  Source: {evid.source} | Confidence: {evid.confidence}\n"
                f"  Observed Value: {evid.observed_value}\n"
                f"  Description: {evid.description}"
            )
        lines.append("")

        # 9. Assessed Target Compatibility
        lines.append("## Assessed Compatibility Telemetry")
        for cp in scenario.compatibility_records:
            lines.append(
                f"- Component: `{cp.component_id}` | Proposed Target: `{cp.proposed_target}` | Status: **{cp.status.value}**\n"
                f"  Reason: {cp.reason} (Source: {cp.assessment_source})"
            )
        lines.append("")

        # 10. Operational Constraints & Verification Gates
        if scenario.migration_constraints:
            lines.append("## Migration Constraints")
            for cnstr in scenario.migration_constraints:
                affected = ", ".join(cnstr.affected_components)
                lines.append(
                    f"- **{cnstr.constraint_id}** [{cnstr.constraint_type.value}]: {cnstr.description} (Affected: {affected})"
                )
            lines.append("")

        if scenario.required_tests:
            lines.append("## Required Verification Tests")
            for test in scenario.required_tests:
                targets = ", ".join(test.target_components)
                lines.append(
                    f"- **{test.test_id}** [{test.test_type.value}]: {test.description} (Targets: {targets})"
                )
            lines.append("")

        return "\n".join(lines)


def build_model_prompt(task: BenchmarkTask, scenario: ScenarioModel) -> str:
    """Convenience function to build standardized model prompt from task and scenario."""
    return PromptBuilder.build_model_prompt(task, scenario)
