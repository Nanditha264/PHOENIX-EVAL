"""Schema validation and JSON Schema export verification script."""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from phoenix_eval.schemas import (
    BenchmarkTask,
    CompatibilityRecord,
    CryptographicComponent,
    DependencyRelationship,
    EvaluationResult,
    EvidenceRecord,
    ExperimentRecord,
    ModelResponse,
    ScenarioModel,
)


def validate_schemas() -> int:
    print("=" * 60)
    print(" PHOENIX-EVAL Schema Contract & JSON Schema Verification")
    print("=" * 60)

    models = [
        CryptographicComponent,
        DependencyRelationship,
        EvidenceRecord,
        CompatibilityRecord,
        ScenarioModel,
        BenchmarkTask,
        ModelResponse,
        EvaluationResult,
        ExperimentRecord,
    ]

    for model in models:
        try:
            schema = model.model_json_schema()
            title = schema.get("title", model.__name__)
            props = len(schema.get("properties", {}))
            print(f"  [OK] {title:<28} -> JSON Schema generated ({props} properties)")
        except Exception as err:
            print(f"  [FAIL] {model.__name__} failed JSON schema export: {err}")
            return 1

    print("\n All Pydantic v2 data contract schemas exported successfully.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(validate_schemas())
