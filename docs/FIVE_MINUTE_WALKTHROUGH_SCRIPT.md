# PHOENIX-EVAL — Five-Minute Video Walkthrough Script
## The Cryptographic Migration Intelligence Benchmark

**Target Runtime:** 5 minutes (0:00 – 5:00)  
**Presenter:** Benchmark Research Lead / Lead Evaluation Systems Engineer  
**Visual Style:** Side-by-side terminal screencast (VS Code / Windows Terminal) and crisp architectural slides  
**Theme:** Rigorous, scientifically defensible evaluation of AI cryptographic migration intelligence without LLM-as-a-judge bias.

---

### [0:00 – 0:35] Part 1: The Problem & Central Research Question

**Visual:**
- Title slide: *PHOENIX-EVAL: The Cryptographic Migration Intelligence Benchmark*
- Subtitle: *Evaluating AI Decision-Making Under Incomplete and Conflicting System Information*
- Cut to presenter / high-level diagram illustrating the NIST Post-Quantum Cryptography transition (FIPS 203 ML-KEM, FIPS 204 ML-DSA, FIPS 205 SLH-DSA).

**Spoken Audio:**
> "Hello everyone. Today, global enterprise infrastructure is facing its largest cryptographic overhaul in forty years: the migration to post-quantum cryptography standards mandated by NIST—specifically ML-KEM, ML-DSA, and SLH-DSA.
> 
> Many organizations are looking to frontier AI models to automate or assist in these migration decisions. But cryptographic migration is unforgiving: one inverted dependency cutover, one unverified assumption, or one forgotten hardware firmware boundary can cause catastrophic outages or silent security regressions.
> 
> This motivated our central research question:
> *'Can today's AI models produce safe, dependency-aware, evidence-backed cryptographic migration decisions under incomplete or conflicting system information?'*
> 
> Unlike benchmarks that rely on subjective, non-deterministic LLM judges, PHOENIX-EVAL evaluates models with 100% deterministic ground truth."

---

### [0:35 – 1:15] Part 2: Benchmark Architecture & Task Design

**Visual:**
- Architectural diagram showing benchmark pipeline:
  1. Synthetic Enterprise DAG Generator (5 domains, 3 complexity tiers)
  2. 10 Task Families (T01–T10)
  3. Ground-Truth Isolator & Prompt Builder
  4. Multi-Provider Runner (OpenAI, Gemini, deterministic mocks)
  5. Deterministic Evaluator & Safety Gate
  6. Failure Taxonomy & Scientific Ingestion Engine

**Spoken Audio:**
> "To test this rigorously, PHOENIX-EVAL defines ten specialized task families spanning the entire migration lifecycle: from basic inventory audit in T01, to protocol negotiation, transitive blocker discovery, and multi-wave topological sequencing in T09.
> 
> We synthesize real-world enterprise topologies across five critical domains: Banking, Telecommunications, Government, Identity Providers, and ERP Systems, parameterized across introductory, intermediate, and advanced complexity tiers.
> 
> Crucially, our benchmark maintains strict mathematical ground truth isolation. Models receive only system topologies, discovery artifacts, and evidence logs. Evaluation solutions and ground truth identifiers are cryptographically quarantined to guarantee zero leakage."

---

### [1:15 – 2:00] Part 3: Synthetic Enterprise Dependency Scenario

**Visual:**
- Terminal screencast executing:
  ```bash
  python -m phoenix_eval.main inspect-scenario scen-gen-t09-bank-02
  ```
- Highlight the directed acyclic graph (DAG): Edge API Gateway -> Core Banking Microservices -> Payment Hardware Security Module -> Financial Ledger Database.
- Highlight cryptographic assets (ECDSA-P256, RSA-2048, AES-256-GCM) and hardware constraints (PCI-DSS, firmware prerequisites).

**Spoken Audio:**
> "Let's inspect a representative scenario: `scen-gen-t09-bank-02`, a banking payment architecture.
> 
> Notice how the system is modeled as a directed acyclic graph. We see an Edge API Gateway terminating TLS with ECDSA-P256, calling microservices that rely on a Hardware Security Module with firmware constraints, connecting to an encrypted relational database.
> 
> The scenario incorporates real enterprise constraints: causal cutover ordering, dual-stack backward compatibility where classical and PQC algorithms must coexist during migration, and coprocessor capacity limits.
> 
> A human architect knows you cannot cut over a dependent service before its security providers are ready. Now let's see how models handle this."

---

### [2:00 – 2:50] Part 4: Real Model Execution & Deterministic Evaluation

**Visual:**
- Terminal screencast showing model execution and contract verification:
  ```bash
  python -m phoenix_eval.main smoke-test --model gpt-4o
  python -m phoenix_eval.main smoke-test --mock
  ```
- Show strict JSON response contract: `architectural_decision`, `migration_plan` (topological waves, rollback plan), `identified_blockers`, and `evidence_citations`.
- Display deterministic scoring trace across dimensions D1 through D6.

**Spoken Audio:**
> "Every model must respond according to a strict JSON schema contract. We enforce structured architectural decisions, ordered migration waves, prerequisite declarations, explicit blockers, and citations to evidence.
> 
> Our robust parser extracts structured payloads without crashing or masking errors.
> 
> Then, our Deterministic Evaluator grades the response across six quantitative dimensions:
> 1. Decision Validity (20%)
> 2. Dependency Ordering (25%)
> 3. Evidence Grounding (15%)
> 4. Blocker Identification (15%)
> 5. Fallback and Uncertainty Handling (10%)
> 6. Constraint Adherence (15%)
> 
> Notice: no LLM evaluates another LLM. Topological sort algorithms verify dependency DAGs, exact string and ontology matchers verify algorithms, and formal constraint solvers verify policy rules."

---

### [2:50 – 3:40] Part 5: Safety Gate & Failure Analysis

**Visual:**
- Terminal screencast highlighting Step 6 of the interactive demonstration:
  ```bash
  python -m phoenix_eval.main demo
  ```
- Focus on the *Safety-Gate Veto*:
  - Raw Score: 24.0 / 100.0
  - Triggered Veto: `[VIO_DEPENDENCY_ORDER_REVERSED]`
  - Effective Score: `0.0 / 100.0 [FORCED TO ZERO]`
  - Safety Status: `FAILED [DANGEROUS MIGRATION BLOCKED]`
- Show the 33-code hierarchical failure taxonomy on screen.

**Spoken Audio:**
> "Now, look at what happens when a model proposes an unsafe migration plan.
> 
> Here, the model generates fluent, plausible prose and earns 24 raw points for schema compliance. But look at its execution order: it scheduled the consumer service to cut over to ML-KEM before upgrading the backend HSM.
> 
> In a real deployment, this would instantly break cryptographic handshakes and crash payment processing.
> 
> This is where PHOENIX-EVAL's Safety-Gate Engine triggers. It detects `VIO_DEPENDENCY_ORDER_REVERSED`, issues a critical veto, and overrides the model's effective score to absolute zero.
> 
> We cataloged 33 distinct failure modes—from inverted dependencies to missing rollback plans—with an `UNCLASSIFIED` fallback ensuring complete incident classification."

---

### [3:40 – 4:30] Part 6: Model Comparison & Experimental Findings

**Visual:**
- Display comparative metrics table from `results/exports/overall_metrics.csv` and visualization dashboard (`results/charts/visualizations.html`).
- Highlight findings:
  - Completion Rate vs Safety Failure Rate
  - Counterfactual Paired Sensitivity divergence
  - Metamorphic Invariant violations (MR1–MR6)

**Spoken Audio:**
> "Our balanced benchmark campaign across all ten task families and five domains reveals a stark finding:
> 
> While frontier models achieve acceptable syntax compliance, they exhibit alarming failure rates under safety-critical conditions.
> 
> In our counterfactual paired-case analysis, where we alter a single hardware firmware status or test result, models often fail to reverse their cutover decision—exhibiting severe confirmation bias.
> 
> Furthermore, in metamorphic testing across relations MR1 through MR6, models frequently violate basic semantic invariants, producing different migration orders when irrelevant component names or comments are permuted."

---

### [4:30 – 5:00] Part 7: Limitations, Reproducibility, & Conclusion

**Visual:**
- Terminal screencast showing dataset verification:
  ```bash
  python -m phoenix_eval.main validate-results --experiment exp-phase6-balanced-001
  python -m phoenix_eval.main evaluate-calibration
  ```
- Show 42/42 calibration passing (100% precision, 100% recall).
- Show 5-field dataset fingerprint SHA-256 digest.
- Closing slide with GitHub repository link and hackathon submission information.

**Spoken Audio:**
> "In accordance with scientific integrity, we clearly document benchmark limitations: synthetic benchmark performance does not constitute production cryptographic certification. While live API evaluations require evaluator-provided keys, our complete test suite runs entirely offline via deterministic mock harnesses.
> 
> PHOENIX-EVAL is 100% reproducible: our 5-field dataset fingerprints cryptographically bind all scenarios, tasks, and ground truths, and our calibration engine achieves 42 out of 42 passing adversarial calibration cases.
> 
> PHOENIX-EVAL establishes the standard for deterministic, safety-critical AI benchmark engineering in the post-quantum era.
> 
> Thank you!"

---
*End of Walkthrough Script.*
