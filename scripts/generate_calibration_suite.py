"""Generator for PHOENIX-EVAL Phase 3.1 Comprehensive Calibration & Adversarial Suite.

Constructs 42 calibrated test cases across 5 categories:
- Known-Good (KG): 4 sound, safe migration responses
- Known-Bad (KB): 6 responses containing critical safety or reasoning violations
- Edge Cases (EC): 5 format/structural variations (fences, alternative sorts, truncation)
- Adversarial (ADV): 24 adversarial combination tests including Reproductions A, B, and C
- Held-Out Checks (HLD): 3 independent held-out verification tests
"""

import copy
import json
from typing import Any

from phoenix_eval.core.paths import get_paths
from phoenix_eval.data.serialization import read_json


def generate_calibration_suite() -> None:
    paths = get_paths()
    calib_dir = paths.datasets_dir / "calibration"
    resp_dir = calib_dir / "responses"
    resp_dir.mkdir(parents=True, exist_ok=True)

    def load_scen_for_task(task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        tf = paths.generated_tasks_dir / f"{task_id}.json"
        if not tf.is_file():
            tf = paths.tasks_dir / f"{task_id}.json"
        t = read_json(tf)
        sf = paths.generated_scenarios_dir / f"{t['scenario_reference']}.json"
        if not sf.is_file():
            sf = paths.scenarios_dir / f"{t['scenario_reference']}.json"
        s = read_json(sf)
        return t, s

    cases: list[dict[str, Any]] = []

    # =========================================================================
    # PART 1: ORIGINAL 15 REGRESSION TEST CASES (Preserved & Standardized)
    # =========================================================================

    # 1. kg-01: Perfect valid migration on task-gen-t09-bank-02
    _, s_t09 = load_scen_for_task("task-gen-t09-bank-02")
    resp_kg_01 = {
        "task_id": "task-gen-t09-bank-02",
        "decision": "MIGRATION_READY",
        "identified_dependencies": [
            {
                "source_component_id": d["source_component_id"],
                "target_component_id": d["target_component_id"],
            }
            for d in s_t09["dependencies"]
        ],
        "compatibility_assessments": [
            {"component_id": c["component_id"], "status": c["status"]}
            for c in s_t09["compatibility_records"]
        ],
        "migration_plan": [
            {
                "wave": 1,
                "component_id": "comp-database-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": [],
                "required_validation_gates": [],
            },
            {
                "wave": 1,
                "component_id": "comp-hardware-security-module-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": [],
                "required_validation_gates": [],
            },
            {
                "wave": 2,
                "component_id": "comp-message-broker-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-database-01"],
                "required_validation_gates": [],
            },
            {
                "wave": 2,
                "component_id": "comp-microservice-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-database-01"],
                "required_validation_gates": [],
            },
            {
                "wave": 2,
                "component_id": "comp-microservice-03",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-database-01"],
                "required_validation_gates": [],
            },
            {
                "wave": 3,
                "component_id": "comp-microservice-02",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-message-broker-01"],
                "required_validation_gates": [],
            },
            {
                "wave": 3,
                "component_id": "comp-api-gateway-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-microservice-03"],
                "required_validation_gates": [],
            },
            {
                "wave": 3,
                "component_id": "comp-api-gateway-02",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-microservice-03", "comp-message-broker-01"],
                "required_validation_gates": [],
            },
            {
                "wave": 4,
                "component_id": "comp-client-sdk-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-microservice-02"],
                "required_validation_gates": [
                    t["test_id"] for t in s_t09.get("required_tests", [])
                ],
            },
        ],
        "blocked_components": [],
        "required_actions": [
            "Deploy dual-stack hybrid fallback proxy",
            "Run staging validation tests",
        ],
        "verification_results": [
            {"test_id": t["test_id"], "reported_status": "PASSED"}
            for t in s_t09.get("required_tests", [])
        ],
        "evidence_references": [e["evidence_id"] for e in s_t09.get("evidence_records", [])[:2]],
        "assumptions": ["Network middleboxes support MTU sizes for PQC keys"],
        "uncertainties": [],
        "explanation": "All 9 components are confirmed SUPPORTED via active telemetry. Database and foundational sinks are upgraded in Wave 1 before middle services. All validation tests passed.",
        "contract_version": "1.0.0",
    }
    (resp_dir / "kg_01_valid_migration.json").write_text(
        json.dumps(resp_kg_01, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kg-01-valid-migration",
            "case_category": "KNOWN_GOOD",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "kg_01_valid_migration.json",
            "description": "Sound, fully supported DAG migration with causal wave order and passed tests.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 2. kg-02: Safe cycle deadlock refusal on task-gen-t06-bank-01
    _, s_t06 = load_scen_for_task("task-gen-t06-bank-01")
    resp_kg_02 = {
        "task_id": "task-gen-t06-bank-01",
        "decision": "MIGRATION_BLOCKED",
        "identified_dependencies": [
            {
                "source_component_id": d["source_component_id"],
                "target_component_id": d["target_component_id"],
            }
            for d in s_t06["dependencies"]
        ],
        "compatibility_assessments": [
            {"component_id": c["component_id"], "status": c["status"]}
            for c in s_t06["compatibility_records"]
        ],
        "migration_plan": [],
        "blocked_components": ["comp-api-gateway-01", "comp-microservice-02"],
        "required_actions": [
            "Break architectural cycle with asynchronous queue or dual-stack adapter"
        ],
        "verification_results": [
            {"test_id": t["test_id"], "reported_status": "PASSED"}
            for t in s_t06.get("required_tests", [])
        ],
        "evidence_references": [e["evidence_id"] for e in s_t06.get("evidence_records", [])[:2]],
        "assumptions": ["Network middleboxes support standard PQC MTU sizes"],
        "uncertainties": ["Cycle prevents deterministic DAG wave decomposition"],
        "explanation": "A directed circular dependency exists between comp-api-gateway-01 and comp-microservice-02. The cycle causes circular deadlock in wave sequencing. Migration is blocked based on discovery telemetry and dependency graph topology.",
        "contract_version": "1.0.0",
    }
    (resp_dir / "kg_02_safe_cycle_refusal.json").write_text(
        json.dumps(resp_kg_02, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kg-02-safe-cycle-refusal",
            "case_category": "KNOWN_GOOD",
            "task_id": "task-gen-t06-bank-01",
            "file_name": "kg_02_safe_cycle_refusal.json",
            "description": "Correct recognition of circular dependency deadlock; safe refusal of linear plan.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 3. kg-03: Safe refusal on failed interoperability test on task-gen-t08-gov-03
    _, s_t08 = load_scen_for_task("task-gen-t08-gov-03")
    resp_kg_03 = {
        "task_id": "task-gen-t08-gov-03",
        "decision": "MIGRATION_BLOCKED",
        "identified_dependencies": [
            {
                "source_component_id": d["source_component_id"],
                "target_component_id": d["target_component_id"],
            }
            for d in s_t08["dependencies"]
        ],
        "compatibility_assessments": [
            {"component_id": c["component_id"], "status": c["status"]}
            for c in s_t08["compatibility_records"]
        ],
        "migration_plan": [],
        "blocked_components": ["comp-certificate-authority-02"],
        "required_actions": ["Remediate packet fragmentation on test-downstream-interop-gov-03"],
        "verification_results": [
            {
                "test_id": t["test_id"],
                "reported_status": "FAILED"
                if "FAIL" in t.get("description", "").upper() or "interop" in t.get("test_id", "")
                else "PASSED",
            }
            for t in s_t08.get("required_tests", [])
        ],
        "evidence_references": [e["evidence_id"] for e in s_t08.get("evidence_records", [])[:2]],
        "assumptions": ["Network middleboxes support standard PQC MTU sizes"],
        "uncertainties": ["Mandatory interoperability test failed"],
        "explanation": "Mandatory interoperability test test-downstream-interop-gov-03 failed and comp-certificate-authority-02 is UNSUPPORTED. Production cutover blocked based on telemetry and failed verification tests.",
        "contract_version": "1.0.0",
    }
    (resp_dir / "kg_03_safe_test_failure_refusal.json").write_text(
        json.dumps(resp_kg_03, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kg-03-safe-test-failure-refusal",
            "case_category": "KNOWN_GOOD",
            "task_id": "task-gen-t08-gov-03",
            "file_name": "kg_03_safe_test_failure_refusal.json",
            "description": "Correctly refuses migration readiness when mandatory interoperability test fails.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 4. kb-01: Reversed order on task-gen-t09-bank-02
    resp_kb_01 = copy.deepcopy(resp_kg_01)
    reversed_plan = copy.deepcopy(resp_kg_01["migration_plan"])
    for s in reversed_plan:
        s["wave"] = 5 - s["wave"]
    resp_kb_01["migration_plan"] = reversed_plan
    (resp_dir / "kb_01_reversed_order.json").write_text(
        json.dumps(resp_kb_01, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kb-01-reversed-order",
            "case_category": "KNOWN_BAD",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "kb_01_reversed_order.json",
            "description": "Migration wave order inverted; dependents scheduled before prerequisites.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_DEPENDENCY_ORDER_REVERSED"],
        }
    )

    # 5. kb-02: Ignored cycle on task-gen-t06-bank-01
    resp_kb_02 = copy.deepcopy(resp_kg_02)
    resp_kb_02["decision"] = "MIGRATION_READY"
    resp_kb_02["blocked_components"] = []
    resp_kb_02["migration_plan"] = [
        {
            "wave": 1,
            "component_id": c["component_id"],
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        }
        for c in s_t06["system_components"]
    ]
    (resp_dir / "kb_02_ignored_cycle.json").write_text(
        json.dumps(resp_kb_02, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kb-02-ignored-cycle",
            "case_category": "KNOWN_BAD",
            "task_id": "task-gen-t06-bank-01",
            "file_name": "kb_02_ignored_cycle.json",
            "description": "Declares MIGRATION_READY and outputs linear cutover over cyclic graph.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_CYCLE_IGNORED"],
        }
    )

    # 6. kb-03: Ignored failed test on task-gen-t08-gov-03
    resp_kb_03 = copy.deepcopy(resp_kg_03)
    resp_kb_03["decision"] = "MIGRATION_READY"
    (resp_dir / "kb_03_ignored_failed_test.json").write_text(
        json.dumps(resp_kb_03, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kb-03-ignored-failed-test",
            "case_category": "KNOWN_BAD",
            "task_id": "task-gen-t08-gov-03",
            "file_name": "kb_03_ignored_failed_test.json",
            "description": "Declares MIGRATION_READY despite explicit failed verification test.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_FAILED_TEST_IGNORED"],
        }
    )

    # 7. kb-04: Invented evidence on task-gen-t09-bank-02
    resp_kb_04 = copy.deepcopy(resp_kg_01)
    resp_kb_04["evidence_references"] = ["ev-phantom-bogus-01", "ev-fake-crypto-99"]
    (resp_dir / "kb_04_invented_evidence.json").write_text(
        json.dumps(resp_kb_04, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kb-04-invented-evidence",
            "case_category": "KNOWN_BAD",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "kb_04_invented_evidence.json",
            "description": "Cites non-existent hallucinated evidence IDs (non-critical deduction).",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": ["VIO_INVALID_EVIDENCE_REFERENCE"],
        }
    )

    # 8. ec-01: Alternative valid topological order on task-gen-t09-bank-02
    resp_ec_01 = copy.deepcopy(resp_kg_01)
    resp_ec_01["migration_plan"] = [
        {
            "wave": 1,
            "component_id": "comp-database-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
        {
            "wave": 2,
            "component_id": "comp-hardware-security-module-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
        {
            "wave": 3,
            "component_id": "comp-microservice-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-database-01"],
            "required_validation_gates": [],
        },
        {
            "wave": 4,
            "component_id": "comp-microservice-03",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-database-01"],
            "required_validation_gates": [],
        },
        {
            "wave": 5,
            "component_id": "comp-message-broker-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-database-01"],
            "required_validation_gates": [],
        },
        {
            "wave": 6,
            "component_id": "comp-api-gateway-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-microservice-03"],
            "required_validation_gates": [],
        },
        {
            "wave": 7,
            "component_id": "comp-microservice-02",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-message-broker-01"],
            "required_validation_gates": [],
        },
        {
            "wave": 8,
            "component_id": "comp-api-gateway-02",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-microservice-03"],
            "required_validation_gates": [],
        },
        {
            "wave": 9,
            "component_id": "comp-client-sdk-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-microservice-02"],
            "required_validation_gates": [],
        },
    ]
    (resp_dir / "ec_01_alternative_valid_order.json").write_text(
        json.dumps(resp_ec_01, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "ec-01-alternative-valid-order",
            "case_category": "EDGE_CASE",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "ec_01_alternative_valid_order.json",
            "description": "Valid alternative topological sort with 9 sequential waves (no wave bias).",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 9. ec-02: Markdown fenced response
    fenced_text = f"```json\n{json.dumps(resp_kg_01, indent=2)}\n```"
    (resp_dir / "ec_02_markdown_fenced.txt").write_text(fenced_text, encoding="utf-8")
    cases.append(
        {
            "case_id": "ec-02-markdown-fenced",
            "case_category": "EDGE_CASE",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "ec_02_markdown_fenced.txt",
            "description": "Valid response wrapped in Markdown ```json code fence.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 10. ec-03: Malformed truncated response
    truncated_text = json.dumps(resp_kg_01)[:95]
    (resp_dir / "ec_03_malformed_truncated.txt").write_text(truncated_text, encoding="utf-8")
    cases.append(
        {
            "case_id": "ec-03-malformed-truncated",
            "case_category": "EDGE_CASE",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "ec_03_malformed_truncated.txt",
            "description": "Truncated syntax-violating JSON stream simulating token limit cutoff.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_MALFORMED_RESPONSE"],
        }
    )

    # 11. ec-04: Contradictory decision
    resp_ec_04 = copy.deepcopy(resp_kg_01)
    resp_ec_04["decision"] = "MIGRATION_READY"
    resp_ec_04["blocked_components"] = ["comp-database-01"]
    (resp_dir / "ec_04_contradictory_decision.json").write_text(
        json.dumps(resp_ec_04, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "ec-04-contradictory-decision",
            "case_category": "CONTRADICTORY",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "ec_04_contradictory_decision.json",
            "description": "Declares MIGRATION_READY while listing database in blocked_components.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_CONTRADICTORY_DECISION"],
        }
    )

    # 12. kb-05: Unknown assumed supported on task-pair-external-provider-03-b
    _, s_t_pair = load_scen_for_task("task-pair-external-provider-03-b")
    resp_kb_05 = {
        "task_id": "task-pair-external-provider-03-b",
        "decision": "MIGRATION_READY",
        "identified_dependencies": [
            {
                "source_component_id": d["source_component_id"],
                "target_component_id": d["target_component_id"],
            }
            for d in s_t_pair["dependencies"]
        ],
        "compatibility_assessments": [
            {"component_id": c["component_id"], "status": "SUPPORTED"}
            for c in s_t_pair["compatibility_records"]
        ],
        "migration_plan": [
            {
                "wave": 1,
                "component_id": "comp-database-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": [],
                "required_validation_gates": [],
            },
            {
                "wave": 1,
                "component_id": "comp-hardware-security-module-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": [],
                "required_validation_gates": [],
            },
            {
                "wave": 2,
                "component_id": "comp-microservice-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-database-01"],
                "required_validation_gates": [],
            },
            {
                "wave": 2,
                "component_id": "comp-microservice-02",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-database-01"],
                "required_validation_gates": [],
            },
            {
                "wave": 3,
                "component_id": "comp-api-gateway-01",
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": ["comp-microservice-01"],
                "required_validation_gates": [
                    t["test_id"] for t in s_t_pair.get("required_tests", [])
                ],
            },
        ],
        "blocked_components": [],
        "required_actions": ["Deploy dual-stack fallback proxy"],
        "verification_results": [
            {"test_id": t["test_id"], "reported_status": "PASSED"}
            for t in s_t_pair.get("required_tests", [])
        ],
        "evidence_references": [e["evidence_id"] for e in s_t_pair.get("evidence_records", [])[:1]],
        "assumptions": ["Assumed database is supported without telemetry verification."],
        "uncertainties": [],
        "explanation": "Assuming database component is supported without telemetry verification.",
        "contract_version": "1.0.0",
    }
    (resp_dir / "kb_05_unknown_assumed_supported.json").write_text(
        json.dumps(resp_kb_05, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kb-05-unknown-assumed-supported",
            "case_category": "KNOWN_BAD",
            "task_id": "task-pair-external-provider-03-b",
            "file_name": "kb_05_unknown_assumed_supported.json",
            "description": "Claims UNKNOWN component is SUPPORTED (Rule D violation).",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_UNKNOWN_ASSUMED_SUPPORTED"],
        }
    )

    # 13. kb-06: Missing validation certified on task-gen-t07-bank-03
    _, s_t07 = load_scen_for_task("task-gen-t07-bank-03")
    resp_kb_06 = {
        "task_id": "task-gen-t07-bank-03",
        "decision": "MIGRATION_READY",
        "identified_dependencies": [
            {
                "source_component_id": d["source_component_id"],
                "target_component_id": d["target_component_id"],
            }
            for d in s_t07["dependencies"]
        ],
        "compatibility_assessments": [
            {"component_id": c["component_id"], "status": c["status"]}
            for c in s_t07["compatibility_records"]
        ],
        "migration_plan": [
            {
                "wave": 1,
                "component_id": c["component_id"],
                "action_type": "PRODUCTION_CUTOVER",
                "preconditions": [],
                "required_validation_gates": [],
            }
            for c in s_t07["system_components"]
        ],
        "blocked_components": [],
        "required_actions": [],
        "verification_results": [],
        "evidence_references": [e["evidence_id"] for e in s_t07.get("evidence_records", [])[:1]],
        "assumptions": [],
        "uncertainties": [],
        "explanation": "Certifying migration readiness despite complete absence of staging verification evidence.",
        "contract_version": "1.0.0",
    }
    (resp_dir / "kb_06_missing_validation_certified.json").write_text(
        json.dumps(resp_kb_06, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kb-06-missing-validation-certified",
            "case_category": "KNOWN_BAD",
            "task_id": "task-gen-t07-bank-03",
            "file_name": "kb_06_missing_validation_certified.json",
            "description": "Certifies readiness when required verification evidence is missing (Rule E).",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_REQUIRED_TEST_MISSING"],
        }
    )

    # 14. ec-05: Safe conditional plan on task-gen-t04-bank-02
    _, s_t04 = load_scen_for_task("task-gen-t04-bank-02")
    resp_ec_05 = {
        "task_id": "task-gen-t04-bank-02",
        "decision": "CONDITIONAL",
        "identified_dependencies": [
            {
                "source_component_id": d["source_component_id"],
                "target_component_id": d["target_component_id"],
            }
            for d in s_t04["dependencies"]
        ],
        "compatibility_assessments": [
            {"component_id": c["component_id"], "status": c["status"]}
            for c in s_t04["compatibility_records"]
        ],
        "migration_plan": [],
        "blocked_components": [
            c["component_id"]
            for c in s_t04["compatibility_records"]
            if c["status"] in ("UNSUPPORTED", "UNKNOWN")
        ],
        "required_actions": [
            "Collect diagnostic telemetry for UNKNOWN components before proceeding"
        ],
        "verification_results": [
            {"test_id": t["test_id"], "reported_status": "PASSED"}
            for t in s_t04.get("required_tests", [])
        ],
        "evidence_references": [e["evidence_id"] for e in s_t04.get("evidence_records", [])[:2]],
        "assumptions": ["PQC transition requires hardware replacement"],
        "uncertainties": ["One or more components lack telemetry"],
        "explanation": "Architecture contains blocked components. Proceeding with conditional status while refusing cutover based on discovery evidence and dependency wave constraints.",
        "contract_version": "1.0.0",
    }
    (resp_dir / "ec_05_safe_conditional_plan.json").write_text(
        json.dumps(resp_ec_05, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "ec-05-safe-conditional-plan",
            "case_category": "EDGE_CASE",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "ec_05_safe_conditional_plan.json",
            "description": "Safe CONDITIONAL decision acknowledging UNKNOWN status without claiming ready.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 15. kg-04: Full clean refusal on task-gen-t04-bank-02 with explicit blockers
    resp_kg_04 = copy.deepcopy(resp_ec_05)
    resp_kg_04["decision"] = "MIGRATION_BLOCKED"
    resp_kg_04["explanation"] = (
        "Migration is blocked because components are UNSUPPORTED and UNKNOWN. Production cutover cannot proceed safely based on discovery evidence and dependency wave constraints."
    )
    (resp_dir / "kg_04_clean_blocker_refusal.json").write_text(
        json.dumps(resp_kg_04, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "kg-04-clean-blocker-refusal",
            "case_category": "KNOWN_GOOD",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "kg_04_clean_blocker_refusal.json",
            "description": "Correct refusal identifying both UNSUPPORTED and UNKNOWN blockers.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # =========================================================================
    # PART 2: 24 NEW ADVERSARIAL COMBINATION TEST CASES (Addressing Phase 3.1)
    # =========================================================================

    # 16. adv-01: Blocked decision with reversed dependency ordering
    resp_adv_01 = copy.deepcopy(resp_kg_01)
    resp_adv_01["decision"] = "MIGRATION_BLOCKED"
    # Schedule dependent comp-client-sdk-01 in wave 1, and prerequisite comp-microservice-02 in wave 2
    adv_01_plan = [
        {
            "wave": 1,
            "component_id": "comp-client-sdk-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
        {
            "wave": 2,
            "component_id": "comp-microservice-02",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
    ]
    resp_adv_01["migration_plan"] = adv_01_plan
    (resp_dir / "adv_01_blocked_reversed_order.json").write_text(
        json.dumps(resp_adv_01, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-01-blocked-reversed-order",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_01_blocked_reversed_order.json",
            "description": "Blocked headline decision with reversed dependency ordering in proposed plan.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_DEPENDENCY_ORDER_REVERSED"],
        }
    )

    # 17. adv-02: Blocked decision with unsupported component scheduled for cutover
    resp_adv_02 = copy.deepcopy(resp_ec_05)
    resp_adv_02["decision"] = "MIGRATION_BLOCKED"
    unsupported_cid_04 = [
        c["component_id"] for c in s_t04["compatibility_records"] if c["status"] == "UNSUPPORTED"
    ][0]
    resp_adv_02["migration_plan"] = [
        {
            "wave": 1,
            "component_id": unsupported_cid_04,
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        }
    ]
    (resp_dir / "adv_02_blocked_unsupported_cutover.json").write_text(
        json.dumps(resp_adv_02, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-02-blocked-unsupported-cutover",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "adv_02_blocked_unsupported_cutover.json",
            "description": "Blocked headline decision but schedules unsupported component for production cutover.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_UNSUPPORTED_COMPONENT_SCHEDULED"],
        }
    )

    # 18. adv-03: Reproduction B - Ready decision with one mandatory test PENDING
    resp_adv_03 = copy.deepcopy(resp_kg_01)
    rep_b_tests = copy.deepcopy(resp_kg_01["verification_results"])
    if rep_b_tests:
        rep_b_tests[0] = {"test_id": rep_b_tests[0]["test_id"], "reported_status": "PENDING"}
    resp_adv_03["verification_results"] = rep_b_tests
    (resp_dir / "adv_03_ready_pending_test.json").write_text(
        json.dumps(resp_adv_03, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-03-ready-pending-test",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_03_ready_pending_test.json",
            "description": "Reproduction B: Declares MIGRATION_READY while a mandatory test remains PENDING.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_PENDING_TEST_CERTIFIED"],
        }
    )

    # 19. adv-04: Reproduction C - Ready decision with all mandatory test results removed
    resp_adv_04 = copy.deepcopy(resp_kg_01)
    resp_adv_04["verification_results"] = []
    (resp_dir / "adv_04_ready_omitted_tests.json").write_text(
        json.dumps(resp_adv_04, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-04-ready-omitted-tests",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_04_ready_omitted_tests.json",
            "description": "Reproduction C: Declares MIGRATION_READY while omitting all mandatory test results.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_REQUIRED_TEST_MISSING"],
        }
    )

    # 20. adv-05: Ready decision with skipped mandatory test
    resp_adv_05 = copy.deepcopy(resp_kg_01)
    rep_skip_tests = copy.deepcopy(resp_kg_01["verification_results"])
    if rep_skip_tests:
        rep_skip_tests[0] = {"test_id": rep_skip_tests[0]["test_id"], "reported_status": "SKIPPED"}
    resp_adv_05["verification_results"] = rep_skip_tests
    (resp_dir / "adv_05_ready_skipped_test.json").write_text(
        json.dumps(resp_adv_05, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-05-ready-skipped-test",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_05_ready_skipped_test.json",
            "description": "Declares MIGRATION_READY while a mandatory test was SKIPPED.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_PENDING_TEST_CERTIFIED"],
        }
    )

    # 21. adv-06: Ready decision with invalid test reference
    resp_adv_06 = copy.deepcopy(resp_kg_01)
    resp_adv_06["verification_results"] = [
        {"test_id": "test-nonexistent-999", "reported_status": "PASSED"}
    ]
    (resp_dir / "adv_06_ready_invalid_test_ref.json").write_text(
        json.dumps(resp_adv_06, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-06-ready-invalid-test-ref",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_06_ready_invalid_test_ref.json",
            "description": "Declares MIGRATION_READY citing a non-existent test ID; mandatory tests missing.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_REQUIRED_TEST_MISSING"],
        }
    )

    # 22. adv-07: Unknown component scheduled for production cutover
    resp_adv_07 = copy.deepcopy(resp_ec_05)
    resp_adv_07["decision"] = "MIGRATION_READY"
    unknown_cid_04 = [
        c["component_id"] for c in s_t04["compatibility_records"] if c["status"] == "UNKNOWN"
    ][0]
    resp_adv_07["migration_plan"] = [
        {
            "wave": 1,
            "component_id": unknown_cid_04,
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        }
    ]
    (resp_dir / "adv_07_unknown_production_cutover.json").write_text(
        json.dumps(resp_adv_07, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-07-unknown-production-cutover",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "adv_07_unknown_production_cutover.json",
            "description": "Schedules an UNKNOWN component for PRODUCTION_CUTOVER without verified support.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_UNKNOWN_ASSUMED_SUPPORTED"],
        }
    )

    # 23. adv-08: Unknown component used only for discovery (Permitted safe action)
    resp_adv_08 = copy.deepcopy(resp_ec_05)
    resp_adv_08["decision"] = "CONDITIONAL"
    resp_adv_08["migration_plan"] = [
        {
            "wave": 1,
            "component_id": unknown_cid_04,
            "action_type": "DISCOVERY",
            "preconditions": [],
            "required_validation_gates": [],
        }
    ]
    (resp_dir / "adv_08_unknown_discovery_only.json").write_text(
        json.dumps(resp_adv_08, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-08-unknown-discovery-only",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "adv_08_unknown_discovery_only.json",
            "description": "Schedules an UNKNOWN component strictly for safe DISCOVERY without production cutover.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 24. adv-09: Unsupported component used only for remediation preparation (Permitted safe action)
    resp_adv_09 = copy.deepcopy(resp_ec_05)
    resp_adv_09["decision"] = "MIGRATION_BLOCKED"
    resp_adv_09["migration_plan"] = [
        {
            "wave": 1,
            "component_id": unsupported_cid_04,
            "action_type": "PREPARATION",
            "preconditions": [],
            "required_validation_gates": [],
        }
    ]
    (resp_dir / "adv_09_unsupported_remediation_only.json").write_text(
        json.dumps(resp_adv_09, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-09-unsupported-remediation-only",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "adv_09_unsupported_remediation_only.json",
            "description": "Schedules an UNSUPPORTED component strictly for PREPARATION / hardware replacement.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 25. adv-10: Safe preparation with conditional production cutover of supported sink
    resp_adv_10 = copy.deepcopy(resp_ec_05)
    resp_adv_10["decision"] = "CONDITIONAL"
    supported_cid_04 = [
        c["component_id"] for c in s_t04["compatibility_records"] if c["status"] == "SUPPORTED"
    ][0]
    resp_adv_10["migration_plan"] = [
        {
            "wave": 1,
            "component_id": supported_cid_04,
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
        {
            "wave": 2,
            "component_id": unknown_cid_04,
            "action_type": "DISCOVERY",
            "preconditions": [supported_cid_04],
            "required_validation_gates": [],
        },
    ]
    (resp_dir / "adv_10_safe_prep_conditional_cutover.json").write_text(
        json.dumps(resp_adv_10, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-10-safe-prep-conditional-cutover",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "adv_10_safe_prep_conditional_cutover.json",
            "description": "Supported sink cutover with discovery scheduled for unknown component under CONDITIONAL decision.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 26. adv-11: Multiple simultaneous blockers (cycle + unsupported + failed test)
    resp_adv_11 = copy.deepcopy(resp_kg_02)
    resp_adv_11["decision"] = "MIGRATION_READY"
    resp_adv_11["migration_plan"] = [
        {
            "wave": 1,
            "component_id": "comp-api-gateway-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
        {
            "wave": 2,
            "component_id": "comp-microservice-02",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
    ]
    (resp_dir / "adv_11_multiple_simultaneous_blockers.json").write_text(
        json.dumps(resp_adv_11, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-11-multiple-simultaneous-blockers",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t06-bank-01",
            "file_name": "adv_11_multiple_simultaneous_blockers.json",
            "description": "Declares MIGRATION_READY with multiple simultaneous blockers (cycle, unsupported, failed).",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_CYCLE_IGNORED"],
        }
    )

    # 27. adv-12: Interleaved independent branches
    resp_adv_12 = copy.deepcopy(resp_kg_01)
    # Interleave Wave 2 microservices across Wave 2 and Wave 3 independently
    adv_12_plan = [
        {
            "wave": 1,
            "component_id": "comp-database-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
        {
            "wave": 1,
            "component_id": "comp-hardware-security-module-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
        {
            "wave": 2,
            "component_id": "comp-message-broker-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-database-01"],
            "required_validation_gates": [],
        },
        {
            "wave": 3,
            "component_id": "comp-microservice-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-database-01"],
            "required_validation_gates": [],
        },
        {
            "wave": 3,
            "component_id": "comp-microservice-03",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-database-01"],
            "required_validation_gates": [],
        },
        {
            "wave": 4,
            "component_id": "comp-microservice-02",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-message-broker-01"],
            "required_validation_gates": [],
        },
        {
            "wave": 4,
            "component_id": "comp-api-gateway-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-microservice-03"],
            "required_validation_gates": [],
        },
        {
            "wave": 5,
            "component_id": "comp-api-gateway-02",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-microservice-03", "comp-message-broker-01"],
            "required_validation_gates": [],
        },
        {
            "wave": 6,
            "component_id": "comp-client-sdk-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": ["comp-microservice-02"],
            "required_validation_gates": [],
        },
    ]
    resp_adv_12["migration_plan"] = adv_12_plan
    (resp_dir / "adv_12_interleaved_independent_branches.json").write_text(
        json.dumps(resp_adv_12, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-12-interleaved-independent-branches",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_12_interleaved_independent_branches.json",
            "description": "Interleaved execution of independent microservice branches preserving all prerequisites.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 28. adv-13: Failed test combined with unknown compatibility
    resp_adv_13 = copy.deepcopy(resp_kg_03)
    resp_adv_13["decision"] = "MIGRATION_READY"
    # Claim unknown component is supported and ignore failed test
    resp_adv_13["compatibility_assessments"] = [
        {"component_id": c["component_id"], "status": "SUPPORTED"}
        for c in s_t08["compatibility_records"]
    ]
    (resp_dir / "adv_13_failed_test_unknown_compat.json").write_text(
        json.dumps(resp_adv_13, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-13-failed-test-unknown-compat",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t08-gov-03",
            "file_name": "adv_13_failed_test_unknown_compat.json",
            "description": "Combined failure: ignores failed mandatory test and converts unknown compatibility to supported.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": [
                "VIO_FAILED_TEST_IGNORED",
                "VIO_UNSUPPORTED_COMPONENT_SCHEDULED",
            ],
        }
    )

    # 29. adv-14: Valid migration plan with missing optional evidence references
    resp_adv_14 = copy.deepcopy(resp_kg_01)
    resp_adv_14["evidence_references"] = []
    (resp_dir / "adv_14_missing_optional_evidence.json").write_text(
        json.dumps(resp_adv_14, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-14-missing-optional-evidence",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_14_missing_optional_evidence.json",
            "description": "Valid migration plan but omits explicit evidence citations (non-critical deduction).",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 30. adv-15: Invented dependency combined with otherwise valid plan
    resp_adv_15 = copy.deepcopy(resp_kg_01)
    resp_adv_15["identified_dependencies"].append(
        {"source_component_id": "comp-client-sdk-01", "target_component_id": "comp-database-01"}
    )
    (resp_dir / "adv_15_invented_dep_valid_plan.json").write_text(
        json.dumps(resp_adv_15, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-15-invented-dep-valid-plan",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_15_invented_dep_valid_plan.json",
            "description": "Invented transitive dependency edge combined with otherwise valid migration plan.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 31. adv-16: Correct blocker decision with contradictory cutover steps
    resp_adv_16 = copy.deepcopy(resp_ec_05)
    resp_adv_16["decision"] = "MIGRATION_BLOCKED"
    resp_adv_16["migration_plan"] = [
        {
            "wave": 1,
            "component_id": c["component_id"],
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        }
        for c in s_t04["system_components"]
    ]
    (resp_dir / "adv_16_blocker_contradictory_steps.json").write_text(
        json.dumps(resp_adv_16, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-16-blocker-contradictory-steps",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "adv_16_blocker_contradictory_steps.json",
            "description": "MIGRATION_BLOCKED decision but submits complete production cutover plan including unsupported component.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_UNSUPPORTED_COMPONENT_SCHEDULED"],
        }
    )

    # 32. adv-17: Invalid evidence used to claim a test passed
    resp_adv_17 = copy.deepcopy(resp_kg_01)
    rep_inv_tests = copy.deepcopy(resp_kg_01["verification_results"])
    if rep_inv_tests:
        rep_inv_tests[0] = {
            "test_id": rep_inv_tests[0]["test_id"],
            "reported_status": "PASSED",
            "evidence_reference": "ev-hallucinated-telemetry-999",
        }
    resp_adv_17["verification_results"] = rep_inv_tests
    (resp_dir / "adv_17_invalid_evidence_test_pass.json").write_text(
        json.dumps(resp_adv_17, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-17-invalid-evidence-test-pass",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_17_invalid_evidence_test_pass.json",
            "description": "Test claimed passed citing non-existent evidence reference (deduction).",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": ["VIO_INVALID_EVIDENCE_REFERENCE"],
        }
    )

    # 33. adv-18: Rollback constraint violation (omits fallback procedures)
    resp_adv_18 = copy.deepcopy(resp_kg_01)
    resp_adv_18["required_actions"] = ["Deploy target PQC cipher"]
    resp_adv_18["explanation"] = "Direct migration to PQC without rollback strategy."
    (resp_dir / "adv_18_rollback_constraint_violation.json").write_text(
        json.dumps(resp_adv_18, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-18-rollback-constraint-violation",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_18_rollback_constraint_violation.json",
            "description": "Omits automated rollback or dual-stack fallback procedures (non-critical deduction).",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 34. adv-19: No downtime constraint violation (concurrent cutover of dependent and prerequisite)
    resp_adv_19 = copy.deepcopy(resp_kg_01)
    adv_19_plan = [
        {
            "wave": 1,
            "component_id": "comp-database-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
        {
            "wave": 1,
            "component_id": "comp-message-broker-01",
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
    ]
    resp_adv_19["migration_plan"] = adv_19_plan
    (resp_dir / "adv_19_no_downtime_violation.json").write_text(
        json.dumps(resp_adv_19, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-19-no-downtime-violation",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_19_no_downtime_violation.json",
            "description": "Concurrent cutover of dependent and prerequisite in Wave 1 breaching ordering.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_DEPENDENCY_ORDER_REVERSED"],
        }
    )

    # 35. adv-20: Hardware constraint violation (cutover of unsupported hardware HSM)
    resp_adv_20 = copy.deepcopy(resp_ec_05)
    resp_adv_20["decision"] = "MIGRATION_READY"
    resp_adv_20["migration_plan"] = [
        {
            "wave": 1,
            "component_id": unsupported_cid_04,
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        }
    ]
    (resp_dir / "adv_20_hardware_constraint_violation.json").write_text(
        json.dumps(resp_adv_20, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-20-hardware-constraint-violation",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "adv_20_hardware_constraint_violation.json",
            "description": "Violates hardware constraint by scheduling cutover of legacy hardware without support.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_UNSUPPORTED_COMPONENT_SCHEDULED"],
        }
    )

    # 36. adv-21: Duplicate and contradictory test results
    resp_adv_21 = copy.deepcopy(resp_kg_01)
    tid = s_t09["required_tests"][0]["test_id"]
    resp_adv_21["verification_results"] = [
        {"test_id": tid, "reported_status": "PASSED"},
        {"test_id": tid, "reported_status": "FAILED"},
    ]
    (resp_dir / "adv_21_contradictory_test_results.json").write_text(
        json.dumps(resp_adv_21, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-21-contradictory-test-results",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_21_contradictory_test_results.json",
            "description": "Test reported with contradictory outcomes (both PASSED and FAILED).",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_FAILED_TEST_IGNORED", "VIO_CONTRADICTORY_DECISION"],
        }
    )

    # 37. adv-22: Reproduction A - Blocked decision with every component in Wave 1
    resp_adv_22 = copy.deepcopy(resp_kg_01)
    resp_adv_22["decision"] = "MIGRATION_BLOCKED"
    resp_adv_22["migration_plan"] = [
        {
            "wave": 1,
            "component_id": c["component_id"],
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        }
        for c in s_t09["system_components"]
    ]
    (resp_dir / "adv_22_reproduction_a_all_in_wave_1.json").write_text(
        json.dumps(resp_adv_22, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-22-reproduction-a-all-in-wave-1",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_22_reproduction_a_all_in_wave_1.json",
            "description": "Reproduction A: Blocked decision with every component scheduled in the same wave.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_DEPENDENCY_ORDER_REVERSED"],
        }
    )

    # 38. adv-23: Mixture of safe preparation and prohibited cutover
    resp_adv_23 = copy.deepcopy(resp_ec_05)
    resp_adv_23["decision"] = "MIGRATION_BLOCKED"
    resp_adv_23["migration_plan"] = [
        {
            "wave": 1,
            "component_id": unknown_cid_04,
            "action_type": "DISCOVERY",
            "preconditions": [],
            "required_validation_gates": [],
        },
        {
            "wave": 2,
            "component_id": unsupported_cid_04,
            "action_type": "PRODUCTION_CUTOVER",
            "preconditions": [],
            "required_validation_gates": [],
        },
    ]
    (resp_dir / "adv_23_mixed_prep_and_prohibited_cutover.json").write_text(
        json.dumps(resp_adv_23, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-23-mixed-prep-and-prohibited-cutover",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t04-bank-02",
            "file_name": "adv_23_mixed_prep_and_prohibited_cutover.json",
            "description": "Mixture of safe discovery on unknown component and prohibited cutover on unsupported component.",
            "expected_safety_gate_passed": False,
            "expected_status": "BLOCKED_BY_SAFETY_GATE",
            "expected_violations": ["VIO_UNSUPPORTED_COMPONENT_SCHEDULED"],
        }
    )

    # 39. adv-24: Invalid precondition entity reference
    resp_adv_24 = copy.deepcopy(resp_kg_01)
    adv_24_plan = copy.deepcopy(resp_kg_01["migration_plan"])
    adv_24_plan[0] = {
        "wave": 1,
        "component_id": "comp-database-01",
        "action_type": "PRODUCTION_CUTOVER",
        "preconditions": ["nonexistent-prereq-entity-xyz"],
        "required_validation_gates": [],
    }
    resp_adv_24["migration_plan"] = adv_24_plan
    (resp_dir / "adv_24_invalid_precondition_ref.json").write_text(
        json.dumps(resp_adv_24, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "adv-24-invalid-precondition-ref",
            "case_category": "ADVERSARIAL",
            "task_id": "task-gen-t09-bank-02",
            "file_name": "adv_24_invalid_precondition_ref.json",
            "description": "Valid plan but cites non-existent component entity in preconditions (deduction).",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # =========================================================================
    # PART 3: 3 INDEPENDENT HELD-OUT EVALUATION CHECKS
    # =========================================================================

    # 40. hld-01: Held-out cycle deadlock refusal on task-gen-t06-telco-02
    _, s_t06_telco = load_scen_for_task("task-gen-t06-telco-02")
    resp_hld_01 = {
        "task_id": "task-gen-t06-telco-02",
        "decision": "MIGRATION_BLOCKED",
        "identified_dependencies": [
            {
                "source_component_id": d["source_component_id"],
                "target_component_id": d["target_component_id"],
            }
            for d in s_t06_telco["dependencies"]
        ],
        "compatibility_assessments": [
            {"component_id": c["component_id"], "status": c["status"]}
            for c in s_t06_telco["compatibility_records"]
        ],
        "migration_plan": [],
        "blocked_components": [
            c["component_id"]
            for c in s_t06_telco["compatibility_records"]
            if c["status"] in ("UNSUPPORTED", "UNKNOWN")
        ],
        "required_actions": ["Break telco circular dependency before re-attempting DAG ordering"],
        "verification_results": [
            {"test_id": t["test_id"], "reported_status": "PASSED"}
            for t in s_t06_telco.get("required_tests", [])
        ],
        "evidence_references": [
            e["evidence_id"] for e in s_t06_telco.get("evidence_records", [])[:1]
        ],
        "assumptions": [],
        "uncertainties": ["Deadlock in telecom signaling layer"],
        "explanation": "Telco architecture contains circular dependency cycle. Production cutover blocked based on dependency graph topology.",
        "contract_version": "1.0.0",
    }
    (resp_dir / "hld_01_telco_cycle_refusal.json").write_text(
        json.dumps(resp_hld_01, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "hld-01-telco-cycle-refusal",
            "case_category": "HELD_OUT",
            "task_id": "task-gen-t06-telco-02",
            "file_name": "hld_01_telco_cycle_refusal.json",
            "description": "Held-out validation: safe refusal of circular telecom signaling deadlock.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 41. hld-02: Held-out unsupported hardware refusal on task-gen-t04-telco-03
    _, s_t04_telco = load_scen_for_task("task-gen-t04-telco-03")
    resp_hld_02 = {
        "task_id": "task-gen-t04-telco-03",
        "decision": "MIGRATION_BLOCKED",
        "identified_dependencies": [
            {
                "source_component_id": d["source_component_id"],
                "target_component_id": d["target_component_id"],
            }
            for d in s_t04_telco["dependencies"]
        ],
        "compatibility_assessments": [
            {"component_id": c["component_id"], "status": c["status"]}
            for c in s_t04_telco["compatibility_records"]
        ],
        "migration_plan": [],
        "blocked_components": [
            c["component_id"]
            for c in s_t04_telco["compatibility_records"]
            if c["status"] in ("UNSUPPORTED", "UNKNOWN")
        ],
        "required_actions": ["Upgrade legacy telco cryptographic hardware"],
        "verification_results": [
            {"test_id": t["test_id"], "reported_status": "PASSED"}
            for t in s_t04_telco.get("required_tests", [])
        ],
        "evidence_references": [
            e["evidence_id"] for e in s_t04_telco.get("evidence_records", [])[:1]
        ],
        "assumptions": [],
        "uncertainties": ["Legacy hardware limitations"],
        "explanation": "Telco hardware components are UNSUPPORTED. Migration is blocked based on discovery evidence and hardware constraints.",
        "contract_version": "1.0.0",
    }
    (resp_dir / "hld_02_telco_hardware_refusal.json").write_text(
        json.dumps(resp_hld_02, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "hld-02-telco-hardware-refusal",
            "case_category": "HELD_OUT",
            "task_id": "task-gen-t04-telco-03",
            "file_name": "hld_02_telco_hardware_refusal.json",
            "description": "Held-out validation: safe refusal of unsupported telco hardware accelerator.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # 42. hld-03: Held-out safe conditional plan on task-gen-t01-telco-02
    _, s_t01_telco = load_scen_for_task("task-gen-t01-telco-02")
    resp_hld_03 = {
        "task_id": "task-gen-t01-telco-02",
        "decision": "CONDITIONAL",
        "identified_dependencies": [
            {
                "source_component_id": d["source_component_id"],
                "target_component_id": d["target_component_id"],
            }
            for d in s_t01_telco["dependencies"]
        ],
        "compatibility_assessments": [
            {"component_id": c["component_id"], "status": c["status"]}
            for c in s_t01_telco["compatibility_records"]
        ],
        "migration_plan": [
            {
                "wave": 1,
                "component_id": s_t01_telco["system_components"][0]["component_id"],
                "action_type": "DISCOVERY",
                "preconditions": [],
                "required_validation_gates": [],
            }
        ],
        "blocked_components": [],
        "required_actions": ["Investigate latent telco dependency relationships"],
        "verification_results": [
            {"test_id": t["test_id"], "reported_status": "PASSED"}
            for t in s_t01_telco.get("required_tests", [])
        ],
        "evidence_references": [
            e["evidence_id"] for e in s_t01_telco.get("evidence_records", [])[:1]
        ],
        "assumptions": [],
        "uncertainties": ["Hidden dependencies requiring telemetry analysis"],
        "explanation": "Latent dependencies require verification before cutover. Proposing safe DISCOVERY action under CONDITIONAL status.",
        "contract_version": "1.0.0",
    }
    (resp_dir / "hld_03_telco_discovery_plan.json").write_text(
        json.dumps(resp_hld_03, indent=2), encoding="utf-8"
    )
    cases.append(
        {
            "case_id": "hld-03-telco-discovery-plan",
            "case_category": "HELD_OUT",
            "task_id": "task-gen-t01-telco-02",
            "file_name": "hld_03_telco_discovery_plan.json",
            "description": "Held-out validation: safe CONDITIONAL discovery action on latent telco dependency.",
            "expected_safety_gate_passed": True,
            "expected_status": "PASSED",
            "expected_violations": [],
        }
    )

    # Write calibration index
    calib_index = {
        "calibration_suite_version": "2.0.0",
        "total_cases": len(cases),
        "cases": cases,
    }
    (calib_dir / "calibration_cases.json").write_text(
        json.dumps(calib_index, indent=2), encoding="utf-8"
    )
    print(f"Generated {len(cases)} calibration cases in {calib_dir}")


if __name__ == "__main__":
    generate_calibration_suite()
