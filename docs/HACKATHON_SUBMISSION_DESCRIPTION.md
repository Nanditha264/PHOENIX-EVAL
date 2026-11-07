# PHOENIX-EVAL — Hackathon Submission Description
## The Cryptographic Migration Intelligence Benchmark

**Project Title:** PHOENIX-EVAL — The Cryptographic Migration Intelligence Benchmark  
**Short Tagline:** A deterministic, constraint-based benchmark evaluating AI reasoning safety during enterprise post-quantum cryptographic transitions.

---

### 1. Problem Statement
With the finalization of NIST Post-Quantum Cryptography standards (FIPS 203 ML-KEM, FIPS 204 ML-DSA, FIPS 205 SLH-DSA), global enterprises must migrate thousands of interconnected cryptographic dependencies across edge gateways, identity providers, databases, and Hardware Security Modules (HSMs).

Security architects are exploring Large Language Models (LLMs) to analyze system telemetry and plan phased cutovers. However, cryptographic transitions carry asymmetric risk: an AI model that inverts a cutover wave, overlooks an incompatible downstream consumer, or assumes missing telemetry is supported will cause catastrophic enterprise blackouts, database corruption, or compliance penalties. 

Existing benchmarks measure coding or conversational security Q&A; none evaluate whether AI models can safely reason over directed dependency graphs and cryptographic invariants under incomplete or conflicting information.

---

### 2. Proposed Solution: PHOENIX-EVAL
**PHOENIX-EVAL** is a research-grade evaluation benchmark designed to measure the safety, dependency-awareness, and evidence-grounding of AI models during complex cryptographic migrations.

> **Important Identity Distinction:**
> - **PHOENIX:** An architectural concept for a future autonomous enterprise cryptographic migration platform.
> - **PHOENIX-EVAL:** The evaluation benchmark (and our hackathon deliverable) that tests AI models on cryptographic migration reasoning. It is strictly an evaluation benchmark, not a production execution tool.

---

### 3. Main Technical Features
1. **Zero LLM-as-a-Judge Evaluation:** Uses pure mathematical graph theory (NetworkX) and rule-based constraint solvers to eliminate stochastic judge drift, hallucination, and prompt bias.
2. **Topological Invariant Verification:** Kahn's algorithm verifies directed acyclic graph (DAG) properties, ensuring proposed cutover waves $W_1, W_2, \dots, W_k$ respect all causal prerequisites ($\text{prereqs}(c) \in W_i$ where $i < j$) with zero cycle deadlocks.
3. **Safety-Gate Veto Engine:** Separates raw syntax score (0–100) from operational effective score (0–100). Any critical safety violation (e.g., cutting over unsupported algorithms, ignoring dependency blockers, or certifying pending tests) forces the effective score to exactly 0.0.
4. **10 Specialized Task Families (T01–T10):** Evaluates hidden dependencies, false discovery, downstream blockers, epistemic uncertainty, wave sequencing, circular deadlocks, missing validation, failed interoperability, epistemic calibration, and conditional planning.
5. **Standardized 33-Code Failure Taxonomy:** Maps model reasoning defects into four categories (Dependency, Cryptographic, Evidence, Architectural) with safe `UNCLASSIFIED` fallback.
6. **Architectural Ground-Truth Isolation:** Evaluator criteria and expected solutions are strictly segregated from model prompts, verified via automated leakage audits and a 5-field SHA-256 dataset fingerprint.

---

### 4. Technical Architecture
```
+-------------------------------------------------------------------------------+
|                           PHOENIX-EVAL ARCHITECTURE                           |
+-------------------------------------------------------------------------------+
                                                                                 
  [Procedural Enterprise Generator]               [Evaluator Ground Truth]       
     - 5 Enterprise Sectors                          - Expected Cutover Waves    
     - 40 Synthetic Topologies                       - Known Blockers            
     - 10 Task Families (T01-T10)                    - Policy Constraints        
                 |                                               |               
                 v                                               | (Strictly     
     [Model-Visible Scenario]                                    |  Isolated)    
                 |                                               |               
                 v                                               |               
      [ModelResponseContract]                                    |               
       - Phased Cutover Waves                                    v               
       - Explicit Prerequisites        ======>       [Deterministic Evaluator]   
       - Readiness Certifications                    - Kahn's DAG Algorithm      
       - Evidence Citations                          - 6-Dimension Rubric        
                                                     - Safety-Gate Veto Engine   
                                                                 |               
                                                                 v               
                                                     [Telemetry & Failure Intel] 
                                                     - Dual Scoring (Raw vs Eff) 
                                                     - 33-Code Failure Taxonomy  
                                                     - Wilson Score Intervals    
```

---

### 5. What Has Actually Been Demonstrated
- **Deterministic Calibration:** 42/42 calibration cases passing with 100% precision, 100% recall, 0 false positives, and 0 false negatives.
- **Offline Evaluation Campaign:** 84 runs executed across 14 representative tasks covering all 10 task families (T01–T10) and all 5 enterprise domains using deterministic mock fixtures (`mock-valid-migration`, `mock-unsafe-migration`, `mock-malformed-response`).
- **Evaluator Rigor & Veto Fidelity:** Proved that `mock-unsafe-migration` receives a raw score of 19.4 but an effective score of 0.0 due to safety vetoes.
- **Automated Failure Intelligence:** Extracted 124 failure incidents into recurring patterns (e.g., `FATAL_PREMATURE_CUTOVER`).
- **Production Provider Readiness:** OpenAI and Gemini provider adapters are implemented with retries and credential pre-flights. When executed without API keys, they halt cleanly on `AUTH_FAILED` with zero fake substitutions.
- **Quality Engineering:** 292 passing automated tests, 0 MyPy typing errors across 96 source files, 0 Ruff lint errors across 157 files.

---

### 6. What Is Novel
1. **First Benchmark for Cryptographic Migration Reasoning:** Fills a critical gap between high-level security Q&A and general code refactoring benchmarks.
2. **Deterministic DAG Causal Wave Verification:** Solves the challenge of evaluating multi-phase, multi-tier migration schedules without stochastic LLM judges.
3. **Safety-Gate Veto Scoring:** Rejects syntactic score inflation; an articulate model that breaks a production dependency receives an operational score of zero.
4. **Epistemic Calibration Testing:** Explicitly penalizes models that treat missing telemetry as supported compatibility (epistemic inversion).

---

### 7. Limitations & Future Work
- **Documented Limitation:** Due to the absence of API keys in the execution environment, no commercial frontier AI models (GPT-4o, Claude 3.5, Gemini 1.5) were evaluated in the current campaign. All reported experimental figures reflect deterministic mock fixtures.
- **Future Work:** Running live evaluation campaigns against frontier models once API budgets are allocated, scaling topologies to 100+ components, and expanding dynamic Infrastructure-as-Code ingestion from Terraform and Kubernetes.
