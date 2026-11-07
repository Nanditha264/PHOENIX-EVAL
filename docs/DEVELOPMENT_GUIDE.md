# PHOENIX-EVAL: Developer Guide

This guide establishes the engineering conventions, workflows, and standards for contributing to PHOENIX-EVAL across all development phases.

---

## 1. Setting Up the Development Environment

### Step 1: Python Environment
PHOENIX-EVAL requires **Python 3.11** or later. Verify your local installation:
```bash
python --version
```

### Step 2: Install Development Dependencies
```bash
pip install -r requirements.txt
pip install -e . --no-deps
```

### Step 3: Local Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
PHOENIX-EVAL initializes cleanly **with zero API keys required**. Phase 1 uses deterministic mock providers by default.

---

## 2. Coding Standards & Engineering Invariants

### A. Type Safety & Type Hints
- **Strict Typing:** All public and internal functions must carry explicit type hints for parameters and return types.
- **MyPy Compliance:** The codebase enforces strict MyPy settings:
  - `disallow_untyped_defs = true`
  - `check_untyped_defs = true`
  - `no_implicit_optional = true`
  - `strict_optional = true`

### B. Clean Architecture & Separation of Concerns
- Never import evaluator-only repositories or ground-truth loading functions inside model-facing prompt generation routines.
- Maintain unidirectional module dependencies:
  - `schemas` imports from `core` and `utils`.
  - `data` imports from `schemas`, `core`, and `utils`.
  - `benchmark` imports from `data`, `schemas`, and `core`.
  - `providers` and `evaluator` import from `schemas` and `core`.
  - `main` coordinates all layers via the public interfaces.
- **No circular imports.**

### C. Immutability & Validation
- Pydantic models must use `model_config = ConfigDict(frozen=True, extra="forbid")` unless explicitly documented why mutability or dynamic fields are required.
- Enforce domain invariants via `@field_validator` and `@model_validator(mode="after")`.

### D. Security & Redaction
- **Never commit API keys or credentials.**
- All logging pipelines must use `RedactingFilter` in `src/phoenix_eval/core/logging.py` to scrub potential tokens.

---

## 3. Adding New Scenarios and Benchmark Tasks

### Adding a Scenario
1. Create a JSON file in `datasets/scenarios/` following the naming convention:
   `scen-<domain>-<topic>-<number>.json` (e.g., `scen-pqc-tls-banking-001.json`).
2. Verify all `component_id` values match `^[a-zA-Z0-9][a-zA-Z0-9_\-\.]{1,127}$`.
3. Ensure every dependency edge references existing `source_component_id` and `target_component_id`.
4. Validate that `compatibility_records` use explicit `SUPPORTED`, `UNSUPPORTED`, or `UNKNOWN` statuses.
5. Run schema validation:
   ```bash
   python scripts/validate_schemas.py
   python -m phoenix_eval.main inspect-scenario <SCENARIO_ID>
   ```

### Adding a Benchmark Task
1. Create a JSON file in `datasets/tasks/`:
   `task-<category>-<topic>-<number>.json` (e.g., `task-seq-pqc-001.json`).
2. Point `scenario_reference` to a registered scenario ID.
3. Point `ground_truth_reference` to an existing ground-truth file.
4. Define rubric criteria with weights summing to 100.0.
   **Crucial Invariant:** Do NOT leak the ground-truth answers or target component IDs in `task.description`, `task.task_instructions`, or `task.evaluation_criteria[].description`. The task description must formulate the problem and rubric objectives, while the ground-truth answers belong exclusively in `datasets/ground_truth/`.
5. Create the corresponding ground truth in `datasets/ground_truth/<GT_ID>.json`.
6. Run integrity check:
   ```bash
   python -m phoenix_eval.main validate-project
   ```

---

## 4. Running Tests & Quality Verification

Always run all three quality gates before committing:

### 1. Pytest Test Suite
```bash
python -m pytest
```

### 2. Ruff Linter & Formatter
```bash
python -m ruff check src tests scripts
```

### 3. MyPy Static Type Check
```bash
python -m mypy src
```

### 4. Standalone Project Validation
```bash
python scripts/validate_project.py
```

---

## 5. Phase 2 Synthetic Generation & Metamorphic Testing

### Generating a Benchmark Dataset
To synthesize a full reproducible dataset with seed control:
```bash
python -m phoenix_eval.main generate-dataset --seed 42 --variants-per-family 3
```

### Adding New Blueprints or Task Families
1. **Blueprints**: Add new domain blueprints to `src/phoenix_eval/generator/component_generator.py` under the appropriate `ArchitectureDomain`. Ensure `component_type`, `cryptographic_role`, and realistic algorithms are specified.
2. **Task Families**: Register new families in `src/phoenix_eval/generator/config.py` (`TaskFamily` enum and `TASK_FAMILY_DESCRIPTIONS`). Add tailored rubric criteria in `src/phoenix_eval/generator/task_generator.py` and output schemas.
3. **Paired Cases**: When adding an adversarial pair type in `src/phoenix_eval/generator/paired_cases.py`, ensure the pair differs by exactly one fact and triggers explicit ground truth divergence.
4. **Metamorphic Invariants**: Define relations in `src/phoenix_eval/generator/metamorphic.py` ensuring transformed inputs satisfy expected invariant outputs.
5. **Verify**: Run `python -m phoenix_eval.main validate-paired-cases` and `python -m phoenix_eval.main run-metamorphic-tests`.

