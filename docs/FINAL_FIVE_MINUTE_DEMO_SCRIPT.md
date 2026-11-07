# PHOENIX-EVAL — Final Five-Minute Demonstration Script
## The Cryptographic Migration Intelligence Benchmark

**Target Duration:** Exactly 5:00 minutes (300 seconds)  
**Execution Mode:** 100% Offline (Zero external API dependencies, zero cost, 100% reproducible)  
**Audience:** Hackathon Judges, Security Researchers, and Evaluation Engineers

---

## Demonstration Overview & Schedule

| Segment | Timestamp | Topic | Terminal Command / Artifact |
| :---: | :---: | :--- | :--- |
| **Part 1** | 0:00–0:35 | Problem & Research Question | Show `README.md` & NIST PQC Context |
| **Part 2** | 0:35–1:10 | Benchmark Architecture & Synthetic Topology | `python -m phoenix_eval.main inspect-scenario scen-gen-t09-bank-02` |
| **Part 3** | 1:10–1:55 | Task Families & Scenario Evidence | `python -m phoenix_eval.main inspect-task task-gen-t09-bank-02` |
| **Part 4** | 1:55–2:45 | Response Contract & Ground-Truth Isolation | Show `PromptBuilder` & response contract JSON |
| **Part 5** | 2:45–3:35 | Deterministic Scoring & Safety-Gate Veto | `python -m phoenix_eval.main evaluate-calibration` |
| **Part 6** | 3:35–4:20 | Failure Intelligence & Experiment Results | `python -m phoenix_eval.main failure-analysis --experiment exp-phase6-balanced-001` |
| **Part 7** | 4:20–5:00 | Reproducibility, Honest Limitations & Conclusion | `python -m phoenix_eval.main demo` |

---

## Detailed Minute-by-Minute Script

### Part 1: Problem & Research Question (0:00 – 0:35 | 35s)

#### Visual
Open project `README.md` or display the title slide:
> **PHOENIX-EVAL: The Cryptographic Migration Intelligence Benchmark**  
> *"Can today's AI models produce safe, dependency-aware, evidence-backed cryptographic migration decisions under incomplete or conflicting system information?"*

#### Spoken Narration
> *"Hello judges. We are presenting PHOENIX-EVAL. With NIST post-quantum standards now finalized—including ML-KEM and ML-DSA—enterprises must migrate thousands of interdependent cryptographic systems.
>
> Many teams want AI to plan these transitions. But cryptographic migrations have asymmetric risk: cutting over an API gateway before its identity provider is ready causes catastrophic outages, hardware locks, and compliance violations.
>
> To be clear on terminology: PHOENIX represents the broad concept of an autonomous cryptographic migration platform. PHOENIX-EVAL is our hackathon deliverable: a rigorous, 100% deterministic evaluation benchmark engineered to measure whether AI models can make safe, dependency-aware migration decisions."*

---

### Part 2: Benchmark Architecture & Synthetic Topology (0:35 – 1:10 | 35s)

#### Terminal Command
```bash
python -m phoenix_eval.main inspect-scenario scen-gen-t09-bank-02
```

#### Expected Screen Content
Displays a 9-component multi-tier Banking Payments enterprise topology:
- Component inventory: Edge API Gateway, Core Banking Microservice, Payment Settlement Processor, HSM accelerator, Ledger Database.
- Cryptographic details: Classical RSA-2048, ECDSA-P256, AES-128-GCM.
- Architectural constraints: Causal ordering, dual-stack backward compatibility, HSM capacity limits.

#### Spoken Narration
> *"To evaluate models rigorously without exposing confidential customer infrastructure, PHOENIX-EVAL features a deterministic procedural generation engine across five enterprise domains: Banking, Cloud Identity, Telecom, Government, and Enterprise Services.
>
> Here we inspect scenario `scen-gen-t09-bank-02`. Notice that components form a strict directed dependency graph. Hardware Security Modules and core databases are foundational; microservices depend on them, and the edge gateway depends on the microservices. Models cannot treat these as disconnected lists—they must reason over the entire topology."*

#### Recovery Instruction
If the terminal command encounters display clipping on Windows, pipe to more or run: `python -m phoenix_eval.main list-scenarios` to demonstrate scenario discovery.

---

### Part 3: Task Families & Scenario Evidence (1:10 – 1:55 | 45s)

#### Terminal Command
```bash
python -m phoenix_eval.main inspect-task task-gen-t09-bank-02
```

#### Expected Screen Content
Displays Task Family T09 (Valid Migration Control) task specification:
- Scenario reference: `scen-gen-t09-bank-02`
- Objective: Formulate phased migration sequence for PQC transition.
- Cryptographic telemetry: Staging integration test results, firmware versions, dual-stack requirements.

#### Spoken Narration
> *"PHOENIX-EVAL tests reasoning across 10 specialized task families, T01 through T10. These include detecting circular deadlocks in T06, halting when downstream consumers lack PQC support in T03, and handling missing vendor documentation under epistemic uncertainty in T04.
>
> This task, T09, is an epistemic calibration control: all tests have passed, hardware firmware is verified, and dual-stack fallback is configured. Here, a model should safely authorize migration in phased waves. But in adversarial counterfactual tasks, a single subtle flaw—like a failed handshake test or unverified HSM—requires the model to halt cutover."*

---

### Part 4: Model-Facing Response Contract & Ground-Truth Isolation (1:55 – 2:45 | 50s)

#### Visual / Screen Display
Display `src/phoenix_eval/schemas/model_outputs.py` or highlight the strict JSON output schema:
```json
{
  "architectural_decision": "MIGRATION_READY | MIGRATION_BLOCKED | CONDITIONAL",
  "migration_plan": [
    { "component_id": "comp-hsm-01", "target_algorithm": "ML-KEM-768", "prerequisite_component_ids": [] },
    { "component_id": "comp-api-01", "target_algorithm": "ML-KEM-768", "prerequisite_component_ids": ["comp-hsm-01"] }
  ],
  "identified_blockers": [],
  "evidence_citations": []
}
```

#### Spoken Narration
> *"How do models interface with the benchmark? We reject conversational free-text scoring in favor of a strict Pydantic v2 `ModelResponseContract`. Models must declare an explicit architectural decision, specify phased waves with explicit prerequisite component IDs, and cite concrete telemetry evidence.
>
> Crucially, our benchmark enforces complete ground-truth isolation. Evaluator ground truths—such as expected cutover orders, known blockers, and compliance rules—are stored strictly outside the model prompt directory. Our prompt builder is cryptographically audited to ensure zero solution tokens ever leak into the prompt body."*

---

### Part 5: Deterministic Scoring & Safety-Gate Demonstration (2:45 – 3:35 | 50s)

#### Terminal Command
```bash
python -m phoenix_eval.main evaluate-calibration
```

#### Expected Screen Content
```
================================================================================
 PHOENIX-EVAL Evaluator Calibration Suite Results
================================================================================
 Calibration Dir:       datasets/calibration
 Evaluator Version:     3.0.0
 Total Test Cases:      42
 Cases Passed:          42/42 (100.0%)
 Confusion Matrix (Positive Class = Unsafe Detected):
   - True Positives (TP) : 22   (Unsafe correctly blocked)
   - False Positives (FP): 0    (Safe incorrectly blocked)
   - True Negatives (TN) : 20   (Safe correctly accepted)
   - False Negatives (FN): 0    (Unsafe incorrectly accepted)
 Calibration Precision: 100.0%
 Calibration Recall:    100.0%
 CALIBRATION SUITE RESULT: PASSED [100% Deterministic Conformance]
```

#### Spoken Narration
> *"Now we reach the technical core: the evaluator. We use zero LLM judges. LLMs cannot reliably verify directed acyclic graphs or detect subtle deadlocks. Instead, our deterministic evaluator builds an independent NetworkX graph and runs Kahn's algorithm to mathematically prove causal ordering.
>
> Watch our 42-case calibration suite execute in real-time. It covers known-good plans, reversed orders, ignored cycles, and contradictory claims. It achieves 100% precision and 100% recall with zero false positives.
>
> We also demonstrate our Safety-Gate Veto. When a test fixture submits a plan with an inverted cutover, it might earn a raw score of 24 points for syntax. But our safety gate detects violation `VIO_DEPENDENCY_ORDER_REVERSED` and vetoes the effective score to exactly 0.0. In safety-critical infrastructure, a dangerous plan receives zero credit."*

---

### Part 6: Failure Intelligence & Experiment Results (3:35 – 4:20 | 45s)

#### Terminal Command
```bash
python -m phoenix_eval.main failure-analysis --experiment exp-phase6-balanced-001
```

#### Expected Screen Content
Displays summary of 124 extracted failure incidents across the balanced 84-run evaluation campaign:
- 33-code standardized failure taxonomy.
- Dominant recurring pattern detected: `FATAL_PREMATURE_CUTOVER`.
- Second pattern: `UNVERIFIED_DEPENDENCY_ASSUMPTION`.

#### Spoken Narration
> *"Beyond scoring, PHOENIX-EVAL provides failure intelligence. We map model errors into a standardized 33-code failure taxonomy.
>
> Running failure analysis on our 84-run balanced campaign extracts 124 failure incidents. Notice the dominant failure pattern detected: `FATAL_PREMATURE_CUTOVER`. This identifies when a model authorizes cutover despite unresolved downstream blockers.
>
> To be completely honest and transparent: all 84 runs in this campaign were generated using deterministic mock fixtures (`mock-valid-migration`, `mock-unsafe-migration`, `mock-malformed-response`). These runs validate our ingestion, failure clustering, and statistical machinery. They demonstrate evaluator behavior, not real commercial AI capabilities."*

---

### Part 7: Reproducibility, Limitations & Conclusion (4:20 – 5:00 | 40s)

#### Terminal Command
```bash
python -m phoenix_eval.main demo
```

#### Expected Screen Content
Executes the interactive 9-step demonstration trace concluding with:
`DEMONSTRATION COMPLETE — BENCHMARK READY`

#### Spoken Narration
> *"Finally, we conclude with full transparency on our project status.
>
> Our provider adapters for OpenAI and Gemini are fully implemented with retries and credential pre-flights. When run without API keys, they halt safely with `AUTH_FAILED` rather than fabricating fake results. Evaluating real frontier models remains future work once API budgets are allocated.
>
> Everything you have seen today—the 291 automated tests, the 42 calibration cases, the task generator, and the failure intelligence engine—is 100% offline, reproducible, and verifiable right now from our submission archive.
>
> PHOENIX-EVAL establishes the first rigorous foundation for evaluating AI reasoning in cryptographic migrations. Thank you."*

---

## Technical Recovery Procedures for Live Demos

| Issue | Symptom | Immediate Recovery Action |
| :--- | :--- | :--- |
| **Terminal encoding glitch** | Windows PowerShell prints `?` for Unicode boxes | Run `chcp 65001` or run the command directly with standard python output. |
| **Output scrolling too fast** | Judge cannot read table details | Show the pre-generated static report: `results/charts/visualizations.md` or `PHOENIX_EVAL_RESEARCH_REPORT.md`. |
| **Subprocess timeout** | Heavy background task running | Run direct test: `python -m pytest tests/unit/test_smoke_test.py` for immediate confirmation. |
