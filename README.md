# PHOENIX-EVAL

> **The Cryptographic Migration Intelligence Benchmark**  
> Measuring whether AI models can make reliable, safe, and evidence-backed decisions regarding cryptographic transitions across interconnected enterprise systems.

---

## 1. What is PHOENIX-EVAL?

Modern enterprise systems run on hundreds of intertwined cryptographic dependencies: TLS certificates, JWT signing keys, hardware security modules (HSMs), database transparent data encryption (TDE), and legacy cipher suites. Migrating these architectures to **Post-Quantum Cryptography (PQC)**—such as NIST FIPS 203 (ML-KEM), FIPS 204 (ML-DSA), and FIPS 205 (SLH-DSA)—is one of the most complex architectural challenges of the coming decade.

**PHOENIX-EVAL** is a research-grade evaluation benchmark designed to assess whether Large Language Models (LLMs) and AI reasoning systems can safely interpret discovery evidence, map cryptographic dependency graphs, detect migration blockers, and produce dependency-aware migration plans without making dangerous assumptions or hallucinating compatibility.

---

## 2. The Research Problem

When AI models are prompted with cryptographic transition scenarios, they exhibit several catastrophic failure modes:
1. **Unwarranted Optimism (The Assumption Trap):** Assuming that because a component is modern or runs Java/Go, it automatically supports PQC, ignoring legacy upstream dependencies such as hardware HSM firmware.
2. **Epistemic Inversion (Unknown Treated as Supported):** Silently treating unverified or missing telemetry as confirmation of compatibility.
3. **Dependency Blindness:** Ordering migration waves without respecting topological prerequisites, resulting in cascading outages.
4. **Packet Size Naivety:** Overlooking network-level middlebox failures caused by larger PQC public keys (e.g., MTU fragmentation on cellular connections).
5. **Premature Verification Claims:** Declaring a system "migrated" or "verified" without requiring dual-stack fallback and staging validation gates.

PHOENIX-EVAL provides rigorous, evidence-based evaluation rubrics and safety gates to quantify these capabilities.

---

## 3. What the Benchmark Does and Does Not Do

### What PHOENIX-EVAL Does
- ✅ Evaluates AI model outputs against realistic synthetic enterprise architectures.
- ✅ Models complex cryptographic dependency graphs using directed graph theory (NetworkX).
- ✅ Tests epistemic calibration (e.g., distinguishing observed facts from inferences and unverified assumptions).
- ✅ Enforces strict safety gates (e.g., zero-tolerance for breaking dependencies or unauthorized cipher downgrades).
- ✅ Enforces architectural isolation between model-visible scenario prompts and evaluator-only ground truth.

### What PHOENIX-EVAL Does NOT Do
- ❌ **Does NOT modify real enterprise infrastructure:** This is an evaluation benchmark, not a migration execution engine.
- ❌ **Does NOT deploy security keys or reconfigure servers.**
- ❌ **Is NOT an autonomous agent framework:** No LangChain, LangGraph, vector databases, or autonomous agents are embedded in the benchmark.
- ❌ **Does NOT provide OS-level process sandboxing:** Ground-truth isolation is an architectural boundary within the Python application preventing accidental prompt contamination; it is not a cryptographic enclave against hostile code executing in the same Python process.
- ❌ **Does NOT execute production grading in Phase 1:** Phase 1 provides abstract evaluator contracts and a deterministic `MockEvaluator` to verify pipeline data flow. Real semantic grading and rubric scoring belong to Phase 3.

---

## 4. Technology Stack

- **Runtime:** Python 3.11+
- **Data Contracts & Validation:** Pydantic v2, Pydantic-Settings
- **Graph Theory & Topology:** NetworkX
- **Data Processing:** Pandas, NumPy
- **Deterministic Serialization:** JSON, JSONL, CSV
- **Testing & Coverage:** Pytest, Pytest-cov, Coverage.py
- **Code Quality & Typing:** Ruff, MyPy (strict typing)
- **Configuration & Logging:** PyYAML, python-dotenv, RotatingFileHandler with sensitive credential redaction

---

## 5. Project Structure

```
PHOENIX-EVAL/
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore patterns
├── LICENSE                   # Apache 2.0 License
├── pyproject.toml            # Project packaging, Ruff, MyPy, and Pytest configs
├── requirements.txt          # Python dependency specifications
│
├── config/
│   ├── logging.yaml          # Structured logging configuration
│   └── settings.yaml         # Centralized application settings
│
├── docs/
│   ├── ARCHITECTURE.md       # Architectural blueprints & design decisions
│   ├── BENCHMARK_TASK_CATALOG.md # 10 task families, rubrics & schemas
│   ├── DATA_CONTRACTS.md     # Pydantic v2 schema specification
│   ├── DEVELOPMENT_GUIDE.md  # Engineering workflows and coding standards
│   ├── EVALUATION_ENGINE.md  # Phase 3 Deterministic evaluation architecture
│   ├── EVALUATOR_CALIBRATION.md # Evaluator calibration suite (42 cases, 0 FP/FN)
│   ├── EXPERIMENT_EXECUTION.md # Phase 4 Multi-model experiment execution & resumption
│   ├── GRAPH_SEMANTICS.md    # Formal dependency graph semantics & waves
│   ├── GROUND_TRUTH_METHODOLOGY.md # Independent ground-truth derivation
│   ├── MODEL_PROVIDERS.md    # Phase 4 Provider adapters, retries & credential security
│   ├── PHASE_3_VALIDATION_REPORT.md # Phase 3 engineering validation report
│   ├── PROJECT_OVERVIEW.md   # Executive benchmark overview
│   ├── RESEARCH_METHODOLOGY.md # Evaluation methodology & research design
│   ├── RESPONSE_CONTRACT.md  # ModelResponseContract specification & schemas
│   ├── SAFETY_GATE_POLICY.md # 14 machine-readable violations (VIO_*) & veto policy
│   ├── SCORING_RUBRIC.md     # 6 grading dimensions (100 pts) & formulas
│   └── SYNTHETIC_DATASET_DESIGN.md # Enterprise domains & blueprints
│
├── src/
│   └── phoenix_eval/
│       ├── __init__.py
│       ├── main.py           # CLI entry point (phoenix-eval)
│       ├── core/             # Configuration, logging, paths, constants, exceptions
│       ├── schemas/          # Pydantic v2 data contracts (Components, Scenarios, ResponseContract)
│       ├── benchmark/        # Registry and loaders for scenarios, tasks, and ground truths
│       ├── data/             # Repositories, validators, deterministic serialization
│       ├── generator/        # Phase 2 Synthetic Generation Engine (blueprints, constraints, paired)
│       ├── evaluation/       # Phase 3 Deterministic Evaluation Engine (parser, verifier, 6 graders, gates)
│       ├── providers/        # Model provider interfaces and MockModelProvider
│       ├── evaluator/        # Base evaluator contracts and result builders
│       └── utils/            # Hashing (SHA-256), IDs, UTC time utilities
│
├── datasets/
│   ├── scenarios/            # Seed enterprise architecture scenarios
│   ├── tasks/                # Seed benchmark evaluation tasks
│   ├── ground_truth/         # Seed evaluator-only hidden ground truth criteria
│   ├── fixtures/             # Test fixtures
│   ├── calibration/          # Phase 3.1 Evaluator calibration suite (42 test cases)
│   └── generated/            # Phase 2 procedurally synthesized benchmark datasets
│       ├── scenarios/        # Generated scenario models
│       ├── tasks/            # Generated benchmark tasks (T01-T10)
│       ├── ground_truth/     # Deterministically synthesized ground truths
│       ├── manifests/        # Run manifests with complete SHA-256 digests
│       ├── paired_cases/     # Adversarial minimal-pair cases
│       └── metamorphic_cases/# Metamorphic relation verification results
│
├── results/
│   ├── raw_runs/             # Raw model responses
│   ├── processed/            # Graded evaluation results & experiment manifests
│   ├── evaluations/          # Phase 3 detailed evaluation reports (JSON)
│   └── reports/              # Summary metrics and logs
│
├── scripts/
│   ├── validate_project.py   # Standalone pre-flight project verification
│   └── validate_schemas.py   # Schema integrity and JSON Schema export verification
│
└── tests/
    ├── conftest.py           # Global Pytest fixtures
    ├── unit/                 # Unit tests (config, schemas, registry, repo, graph, cli, providers)
    └── integration/          # Integration tests (pipeline, ground truth isolation)
```

---

## 6. Installation & Environment Setup

### Prerequisites
- Python 3.11 or later
- Git

### Quickstart

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd "MICRO EVAL"
   ```

2. **Create and activate a virtual environment (optional but recommended):**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e . --no-deps
   ```

4. **Initialize environment configuration:**
   ```bash
   cp .env.example .env
   ```
   *Note:* PHOENIX-EVAL Phase 1 initializes cleanly **without any API keys**. The default provider is set to `mock`.

---

## 7. CLI Usage

The `phoenix-eval` command-line tool provides benchmark inspection, procedural dataset synthesis, and validation commands:

```bash
# Display help and available commands
python -m phoenix_eval.main --help

# Show version
python -m phoenix_eval.main --version

# --- Phase 1: Baseline Inspection & Validation ---
python -m phoenix_eval.main validate-config
python -m phoenix_eval.main validate-project
python -m phoenix_eval.main list-tasks
python -m phoenix_eval.main list-scenarios
python -m phoenix_eval.main inspect-task task-seq-pqc-001
python -m phoenix_eval.main inspect-scenario scen-pqc-tls-banking-001

# --- Phase 2: Procedural Benchmark Generation & Intelligence Engine ---
# Generate a new reproducible synthetic benchmark dataset (default seed 42)
python -m phoenix_eval.main generate-dataset --seed 42 --variants-per-family 3

# Validate an entire generated dataset against SHA-256 manifest integrity
python -m phoenix_eval.main validate-dataset

# List all dataset generation runs and summary statistics
python -m phoenix_eval.main list-dataset-runs

# Inspect a generated dataset manifest
python -m phoenix_eval.main inspect-dataset gen-pqc-a7254a6a

# Inspect a specific benchmark task family (T01 through T10)
python -m phoenix_eval.main inspect-task-family --family T01

# Validate adversarial paired cases (minimal pairs differing by 1 fact)
python -m phoenix_eval.main validate-paired-cases

# Run metamorphic relation test suite (MR1 through MR6)
python -m phoenix_eval.main run-metamorphic-tests

# --- Phase 3: Deterministic Evaluation, Constraint-Based Grading & Safety Gates ---
# Validate a model response against the Pydantic v2 ModelResponseContract
python -m phoenix_eval.main validate-response --task task-gen-t09-bank-02 --input datasets/calibration/responses/kg_01_valid_migration.json

# Evaluate a response against authoritative ground truth and safety gates
python -m phoenix_eval.main evaluate-response --task task-gen-t09-bank-02 --input datasets/calibration/responses/kg_01_valid_migration.json

# Run the 42-case deterministic evaluator calibration suite
python -m phoenix_eval.main evaluate-calibration

# Inspect a persisted evaluation report by evaluation ID
python -m phoenix_eval.main inspect-evaluation eval-task-gen-t09-bank-02-56e114a4

# List all persisted evaluation reports
python -m phoenix_eval.main list-evaluations

# Export all evaluations to a CSV summary table
python -m phoenix_eval.main export-evaluations --format csv

# --- Phase 4: Multi-Model Evaluation & Reproducible Experiment Execution ---
# Validate an experiment configuration file (pre-flight checks, credentials, task expansion)
python -m phoenix_eval.main validate-experiment --config config/experiments/sample_mock_experiment.yaml

# Execute an automated multi-model benchmark campaign (mock mode, zero API keys required)
python -m phoenix_eval.main run-experiment --config config/experiments/sample_mock_experiment.yaml

# Resume an interrupted benchmark experiment (skips already completed runs without duplication)
python -m phoenix_eval.main resume-experiment exp-mock-comparison-001

# Inspect an experiment campaign's model comparison metrics and completion status
python -m phoenix_eval.main inspect-experiment exp-mock-comparison-001

# List all persisted benchmark experiment campaigns
python -m phoenix_eval.main list-experiments

# Export experiment model comparison table (CSV, JSON, or Markdown report)
python -m phoenix_eval.main export-experiment exp-mock-comparison-001 --format csv
python -m phoenix_eval.main export-experiment exp-mock-comparison-001 --format md

# --- Phase 5 & 5.1: Scientific Ingestion, Failure Intelligence & Research Report ---
# Audit experiment artifacts, integrity hashes, and 5-field dataset fingerprints
python -m phoenix_eval.main validate-results --experiment exp-phase6-balanced-001

# Execute comprehensive Phase 5/5.1 multidimensional analysis and report generation
python -m phoenix_eval.main analyze-experiment --experiment exp-phase6-balanced-001

# Extract failure incidents (33-code taxonomy) and detect recurring failure patterns
python -m phoenix_eval.main failure-analysis --experiment exp-phase6-balanced-001

# Run counterfactual paired-case sensitivity analysis
python -m phoenix_eval.main paired-analysis --experiment exp-phase6-balanced-001

# Verify metamorphic relations (MR1-MR6) on experiment outputs
python -m phoenix_eval.main metamorphic-analysis --experiment exp-phase6-balanced-001

# Generate the authoritative 26-section research report
python -m phoenix_eval.main generate-research-report --experiment exp-phase6-balanced-001

# Inspect analysis manifest and cryptographic input hashes
python -m phoenix_eval.main inspect-analysis anal-178df363

# --- Phase 6: Real-Model Quality Control, Visualizations & Judge Demo ---
# Run pre-flight quality control smoke test on mock provider (3 canonical archetypes)
python -m phoenix_eval.main smoke-test --mock

# Run smoke test on commercial frontier model provider (verifies API key credentials)
python -m phoenix_eval.main smoke-test --model gpt-4o
python -m phoenix_eval.main smoke-test --model gemini-1.5-flash

# Execute official 9-step interactive terminal demonstration for hackathon judges
python -m phoenix_eval.main demo

# Generate static Markdown and HTML visualization dashboards from exported metrics
python scripts/generate_charts.py
```

---

## 8. Running Tests & Quality Checks

### Run Automated Test Suite
```bash
python -m pytest -v
```

### Run Test Coverage
```bash
python -m coverage run -m pytest
python -m coverage report --include="src/*"
```

### Run Static Analysis & Linting
```bash
# Ruff linter
python -m ruff check src tests scripts

# MyPy strict type checker
python -m mypy src
```

### Run Pre-Flight Validation Scripts
```bash
python scripts/validate_project.py
python scripts/validate_schemas.py
python scripts/package_archive.py
```

---

## 9. Current Implementation Status & Roadmap

### Phase 1 Through 6 Implementation Classification
- **Phase 1 Production Foundation (Completed):** All 9 Pydantic v2 data contracts, graph topology & cycle analysis (NetworkX), centralized configuration (Pydantic Settings), logging with credential scrubbing, isolated repositories (`ScenarioRepository`, `TaskRepository`, `GroundTruthRepository`, `ResultsRepository`), `PromptBuilder`, and CLI application.
- **Phase 2 Synthetic Generation Engine (Completed):** 5 enterprise domains, realistic component blueprints, topological constraint engine, 10 distinct task families (T01–T10) across 3 difficulty tiers, deterministic ground truth derivation, adversarial paired cases with divergence validators, metamorphic invariance test suite (MR1–MR6), deterministic SHA-256 artifact hashing, and 7 CLI commands.
- **Phase 3, 3.1 & 3.2 Deterministic Evaluation Engine & Constraint Integrity (Completed):** Zero LLM-as-a-judge primary evaluator, strict Pydantic v2 `ModelResponseContract` with tolerant markdown/JSON parsing and operational `MigrationActionType` differentiation, evaluator-side `IndependentGraphVerifier` (Rule B & C: Kahn's cycle detection, causal ordering `prereqs[c]`, zero canonical wave bias), 6 dimension graders (Dependency 20%, Compatibility 20%, Plan 20%, Evidence 15%, Gates 15%, Explanation 10%), zero refusal bypass in `MigrationPlanGrader` (always inspects steps), deterministic `ConstraintGrader` with zero blind pass (`NOT_EVALUABLE`), deep step precondition validation, cross-cutting constraint deductions without rubric distortion, centralized `SafetyGateEngine` with 16 machine-readable violations (`VIO_*`), dual-score preservation (Raw capability vs Effective operational score), 42-case calibration suite achieving 100% precision, recall & specificity (0 FP, 0 FN), 155 automated tests (100% passing), and 6 evaluation CLI commands.
- **Phase 4, 4.1 & 4.2 Multi-Model Evaluation & Reproducible Experiment Engine (Completed):** Automated multi-model experiment execution service (`ExperimentRunner`), validated configuration schema (`ExperimentConfig`), model registry with zero hardcoded credentials (`ModelRegistry`), multi-provider adapters (deterministic `MockModelProvider`, `OpenAICompatibleProvider`, and `GoogleGeminiProvider` via `httpx`), pre-flight credential verification with fast-failure, bounded exponential backoff retries, prompt equality and ground-truth isolation guarantees, idempotent experiment resumption with filesystem locking, metrics aggregation (`ExperimentAggregator` excluding failed calls from score averages), publication-grade Markdown and CSV comparisons, 188 automated tests (100% passing), and 6 experiment CLI commands.
- **Phase 5 & 5.1 Results Analysis, Failure Intelligence & Scientific Reporting (Completed):** Experiment ingestion engine (`ExperimentIngestionValidator`) enforcing 5-field dataset fingerprints, comparability assessment, multidimensional performance analytics across dimensions, families, domains, and difficulty tiers, failure intelligence engine with 33-code failure taxonomy and safe `UNCLASSIFIED` fallback, automated recurring failure pattern detection (e.g. `FATAL_PREMATURE_CUTOVER`), counterfactual paired-case sensitivity analysis, metamorphic relation verification (MR1–MR6), trial-level consistency analysis with confidence intervals, publication-grade CSV export suite (8 CSV tables), 26-section research report generator, and 284 passing automated tests.
- **Phase 6 Real-Model Experiments, Research Validation & Final Hackathon Submission (Completed):** Provider credential verification and pre-flight smoke testing (`smoke-test`), balanced evaluation subset covering all 10 task families (T01–T10), 5 enterprise domains, and 3 difficulty tiers (`exp-phase6-balanced-001`), static visualization generation engine (`generate_charts.py`), 9-step interactive terminal demonstration for hackathon judges (`demo`), 5-minute video walkthrough script (`docs/FIVE_MINUTE_WALKTHROUGH_SCRIPT.md`), transparent documentation of real-provider credentials with zero fabricated fake results, strict archive packaging (`phoenix_eval_submission.zip`), and automated clean extraction verification.

| Phase | Description | Status |
| :--- | :--- | :---: |
| **Phase 1** | **Engineering Foundation & Architecture**<br>Data contracts, registry, configuration, logging, ground-truth isolation, CLI, test suite. | **COMPLETED** |
| **Phase 2** | **Synthetic Enterprise Engine & Benchmark Intelligence**<br>Procedural enterprise generator (5 domains, 10 task families), deterministic ground truth, paired cases, metamorphic test suite, CLI commands. | **COMPLETED** |
| **Phase 3, 3.1 & 3.2** | **Evaluator Engine, Safety Gates & Constraint Integrity**<br>Deterministic Python evaluator, strict response contract with action types, 6 dimension graders, independent graph verifier, constraint grader with zero blind pass, precondition verification, cross-cutting deductions, safety gate veto engine, 42-case calibration suite, CLI integration. | **COMPLETED** |
| **Phase 4, 4.1 & 4.2** | **Multi-Model Evaluation & Reproducible Experiment Engine**<br>Experiment configuration, runner orchestration, mock & real provider adapters (OpenAI, Gemini), pre-flight credential verification, idempotent resumption, metric aggregation, comparison tables & reports, 6 CLI commands. | **COMPLETED** |
| **Phase 5 & 5.1** | **Results Analysis, Failure Intelligence & Scientific Reporting**<br>Ingestion validation, comparability matrix, 33-code failure taxonomy, recurring pattern detector, paired sensitivity, metamorphic invariants, 8 CSV tables, 26-section research report. | **COMPLETED** |
| **Phase 6** | **Real-Model Experiments, Research Validation & Final Hackathon Submission**<br>Smoke testing, balanced evaluation campaign (T01-T10, 5 domains, 3 difficulties), static visualization generator, 9-step judge demo, 5-minute walkthrough script, verified clean packaging. | **READY WITH DOCUMENTED LIMITATIONS** |
