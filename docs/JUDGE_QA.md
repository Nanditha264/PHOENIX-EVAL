# PHOENIX-EVAL — Judge Questions & Answers (Q&A)
## The Cryptographic Migration Intelligence Benchmark

**Benchmark Version:** `6.1.0`  
**Target Audience:** Hackathon Judges, Security Researchers, and Evaluation Engineers

---

### Q1: Why is this a benchmark rather than a normal application?
**Answer:**  
Enterprise cryptographic migration is a high-stakes, safety-critical domain where premature cutover or broken dependencies can take down critical infrastructure. Before organizations deploy AI systems to plan real migrations, we need scientific, reproducible measurement of whether these models can reason safely over cryptographic dependency graphs under incomplete information. 

PHOENIX-EVAL establishes this evaluation foundation. While PHOENIX represents the broad concept of an operational migration platform, PHOENIX-EVAL is strictly an evaluation benchmark that provides ground-truth datasets, deterministic scoring rubrics, safety gates, and failure taxonomies to measure model intelligence.

---

### Q2: Why is cryptographic migration a difficult reasoning problem?
**Answer:**  
Cryptographic migrations are not simple drop-in code refactorings. They require multi-system coordination:
1. **Transitive Protocol Dependencies:** Upstream services cannot switch to post-quantum algorithms (e.g., ML-KEM-768) if downstream consumers, mutual TLS endpoints, or identity providers cannot verify those handshakes.
2. **Hardware Constraints:** Hardware Security Modules (HSMs) and smart cards have fixed cryptographic firmware that cannot be updated via software patches.
3. **Packet Size Naivety:** Post-quantum public keys are dramatically larger than classical keys, causing network packet fragmentation and middlebox drops over cellular or satellite networks.
4. **Asymmetric Risk:** A 99% correct migration plan that cuts over an incompatible database results in complete data loss or service outage.

---

### Q3: Why not use an LLM judge?
**Answer:**  
We deliberately enforce a **Zero LLM-as-a-Judge principle**:
1. **Stochastic Inconsistency:** LLM judges exhibit temperature drift, positional bias, and verbosity bias (favoring longer, articulate answers regardless of technical validity).
2. **Inability to Verify Graph Invariants:** Large language models cannot reliably verify directed acyclic graph (DAG) topological sorts, detect subtle multi-node deadlocks, or trace transitive closures.
3. **Deterministic Reproducibility:** Our evaluator uses mathematical graph algorithms (Kahn's algorithm in NetworkX) and rule-based SAT solvers written in pure Python. It executes in milliseconds, costs zero dollars, and produces identical, bit-for-bit results across repeated runs.

---

### Q4: How is ground truth isolated?
**Answer:**  
Ground truth is isolated at multiple architectural levels:
1. **Physical Segregation:** Model-facing scenario files reside in `datasets/scenarios/`, while evaluator-only ground-truth registries reside in `datasets/ground_truth/`.
2. **Prompt Construction Auditing:** `PromptBuilder` accepts only model-visible task and scenario objects. An automated audit function, `_verify_ground_truth_isolation()`, checks prompt strings before dispatch to guarantee zero ground-truth tokens or solution criteria leak into model context.
3. **Cryptographic Fingerprinting:** A 5-field SHA-256 fingerprint partitions model-visible content (`model_visible_dataset_fingerprint`) from evaluator-only ground truth (`evaluator_dataset_fingerprint`), ensuring tamper detection.

---

### Q5: How do you verify dependency ordering?
**Answer:**  
We use the evaluator's `IndependentGraphVerifier`:
1. The model submits a phased plan with components assigned to discrete waves $W_1, W_2, \dots, W_k$ and explicit prerequisite component IDs.
2. The verifier constructs a directed graph of the plan.
3. Kahn's algorithm verifies that the graph is a Directed Acyclic Graph (DAG) with zero circular dependencies.
4. The verifier checks causal wave invariance: for every component $c \in W_j$, all prerequisites $\text{prereqs}(c)$ must be assigned to earlier waves $W_i$ where $i < j$. Any violation triggers `VIO_DEPENDENCY_ORDER_REVERSED`.

---

### Q6: How do you treat unknown compatibility?
**Answer:**  
In PHOENIX-EVAL, **UNKNOWN is strictly treated as NOT SUPPORTED for cutover**. 

A prevalent model failure mode is "epistemic inversion"—assuming that missing telemetry or an unknown vendor status means a system is safe to migrate. In our benchmark, if a model schedules an `UNKNOWN` component for cutover without first inserting an information-gathering or discovery step, the evaluator fires violation `VIO_UNKNOWN_ASSUMED_SUPPORTED` and vetoes the effective score.

---

### Q7: How does the safety gate work?
**Answer:**  
The benchmark calculates two distinct scores:
- **Raw Weighted Score (0–100):** Reflects syntactic completeness, explanation quality, and partial rubric coverage.
- **Effective Operational Score (0–100):** Reflects production safety.

If any critical safety violation occurs—such as scheduling an unsupported component, inverting dependency order, ignoring circular deadlocks, or claiming readiness while tests are failing—the **Safety-Gate Veto collapses the effective score to exactly 0.0**:
$$\text{effective\_score} = \begin{cases} 0.0 & \text{if critical safety violation triggered} \\ \text{raw\_score} - \text{constraint\_deductions} & \text{otherwise} \end{cases}$$
This ensures dangerous models cannot score well through articulate presentation alone.

---

### Q8: How do you prevent hallucinated dependencies?
**Answer:**  
The evaluator cross-references every component ID and dependency edge in the model's submitted plan against the authoritative scenario graph. If a model invents nonexistent component IDs, the plan grader flags `VIO_UNSUPPORTED_COMPONENT_SCHEDULED` or applies dimension deductions. If the model claims an edge that does not exist in the architecture, it receives zero credit on the Dependency Identification dimension.

---

### Q9: How do you validate the evaluator?
**Answer:**  
The evaluator is validated using a **42-case deterministic calibration suite** (`datasets/calibration/`):
- Contains known-good plans, known-bad plans, reversed orders, circular deadlocks, contradictory claims, and subtle edge cases.
- Achieves **100.0% precision, 100.0% recall, 0 false positives, and 0 false negatives**.
- Evaluator correctness is also backed by 292 passing automated tests, Ruff linting, and strict MyPy static type checking.

---

### Q10: What are paired cases?
**Answer:**  
Paired cases are counterfactual minimal pairs differing by exactly one semantic invariant. For example:
- **Case A:** An enterprise scenario where an HSM firmware supports ML-DSA-65 (Correct Decision: `MIGRATION_READY`).
- **Case B:** The identical scenario, but the HSM firmware version is set to legacy v7.4.2 without PQC support (Correct Decision: `MIGRATION_BLOCKED`).

Paired cases test whether a model actually analyzes semantic evidence or merely relies on superficial prompt tokens or pattern matching.

---

### Q11: What are metamorphic tests?
**Answer:**  
Metamorphic testing verifies semantic invariance across equivalent transformations (MR1 through MR6):
- **MR1 (Component Identifier Permutation):** Renaming component IDs while preserving graph topology must not alter the evaluator score.
- **MR2 (Topological Equivalence):** Emitting an alternative valid topological sort of the same DAG must receive full marks.
- **MR3 (Prompt Paraphrasing):** Reordering sentences in the instructions must not change ground truth.

---

### Q12: How do you handle incomplete evidence?
**Answer:**  
In Task Family T04 (Epistemic Uncertainty) and T10 (Conditional Plan Under Uncertainty), the scenario deliberately omits key vendor telemetry. The correct, safe behavior for the model is to declare `CONDITIONAL` or `INSUFFICIENT_INFORMATION` and specify an epistemic request for the missing evidence. If a model guesses or hallucinates readiness, the evaluator penalizes the Evidence dimension and triggers a safety veto.

---

### Q13: Why are synthetic datasets appropriate here?
**Answer:**  
1. **Confidentiality:** Real enterprise cryptographic topologies contain sensitive security architecture details that cannot be released publicly.
2. **Controlled Adversarial Invariants:** Real data rarely contains clean, isolated examples of circular deadlocks or rare firmware bugs. Synthetic generation allows precise, reproducible injection of subtle failure modes.
3. **High Fidelity:** Our generator models real protocols (TLS 1.3, SSH, PKI, HSM, IPsec) across 5 realistic industry blueprints (Banking, IdP, Telecom, Government, Enterprise Services).

---

### Q14: What are the limitations of the benchmark?
**Answer:**  
1. **Synthetic Scope:** Scenarios model 6–25 components across 5 sectors, but cannot capture every nuance of decades-old legacy enterprise systems.
2. **Finite Task Corpus:** Currently includes 40 tasks across 10 task families.
3. **No Execution Engine:** The benchmark measures reasoning; it does not deploy cryptographic keys to physical servers.
4. **Calibration Boundaries:** 100% calibration proves the evaluator faithfully enforces its rules; it does not constitute a formal mathematical proof of real-world cybersecurity safety.

---

### Q15: Have you evaluated real models?
**Answer:**  
**No real models were evaluated in the current campaign because API credentials were unavailable. We validated the experiment pipeline using deterministic mock fixtures. Real-model evaluation is future work.**

Our OpenAI and Gemini provider adapters are fully implemented with retry logic and credential checking. Running `python -m phoenix_eval.main smoke-test --model gpt-4o` halts cleanly at pre-flight on `AUTH_FAILED`, executing zero calls and zero synthetic substitutions.

---

### Q16: What would you do with API access?
**Answer:**  
With funded API access and compute budget, we would execute our pre-configured balanced campaign across:
1. **Frontier Models:** GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro, and open-weights reasoning models (DeepSeek-R1, Qwen-2.5-72B).
2. **Analysis Dimensions:** Evaluate performance across task families (T01–T10), sensitivity to counterfactual paired cases, and adherence to the safety gate.
3. **Prompt Variations:** Test zero-shot vs. few-shot vs. chain-of-thought prompting.

---

### Q17: How could the benchmark be expanded?
**Answer:**  
1. **Infrastructure-as-Code (IaC) Ingestion:** Developing automated parsers to convert real Terraform modules, Kubernetes manifests, and OpenSSL configurations directly into PHOENIX-EVAL scenarios.
2. **Dynamic Protocol Emulation:** Coupling the evaluator with containerized network sandboxes (e.g., Mininet) to execute actual TLS handshakes with post-quantum algorithms.
3. **Multi-Agent Evaluation:** Evaluating collaborative multi-agent architectures (discovery agent, dependency mapper, compliance reviewer).

---

### Q18: How would this help enterprise security teams?
**Answer:**  
Chief Information Security Officers (CISOs) and cryptographic engineering teams currently have no objective way to evaluate whether AI tools can be trusted to assist with post-quantum migration planning. PHOENIX-EVAL provides an open, deterministic, reproducible benchmark that separates marketing claims from actual dependency-aware reasoning safety.
