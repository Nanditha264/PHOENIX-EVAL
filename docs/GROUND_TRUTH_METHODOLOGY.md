# PHOENIX-EVAL Ground Truth Methodology & Architectural Isolation

## 1. Principles of Independent Benchmark Ground Truth

A core failure mode of contemporary LLM benchmarks is **circular evaluation**: using an LLM to generate ground-truth answers for evaluating other LLMs. This introduces subtle hallucinations, logical inconsistencies, and unverified assumptions into the evaluation baseline.

PHOENIX-EVAL enforces a strict methodological principle:

> **Fundamental Principle**: Ground truth in PHOENIX-EVAL is synthesized deterministically from formal graph-theoretic invariants and explicit architectural compatibility facts. Zero LLM calls are involved in the generation or verification of ground-truth artifacts.

Every ground-truth answer is provably sound under the mathematical semantics of directed dependency graphs and formal epistemic logic.

---

## 2. Deterministic Ground Truth Derivation

The ground-truth synthesizer (`GroundTruthGenerator`) derives expected decisions directly from the generated scenario artifacts:

```
┌────────────────────────────────┐       ┌────────────────────────────────┐
│   Cryptographic Architecture   │       │   Compatibility & Telemetry    │
│    Directed Graph G = (V, E)   │       │   Records (Facts & Evidence)   │
└───────────────┬────────────────┘       └───────────────┬────────────────┘
                │                                        │
                ▼                                        ▼
    Graph-Theoretic Analysis                Epistemic State Evaluation
    * Cycle Detection (Tarjan's)            * Unsupported Components
    * Sink/Source Classification            * Unknown Status Records
    * Transitive Reachability               * Contradictory Evidence
                │                                        │
                └────────────────┬───────────────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ GroundTruthGenerator  │
                     └───────────┬───────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ Evaluator GroundTruth │
                     │   (Deterministic)     │
                     └───────────────────────┘
```

### 2.1 Formal Derivation Rules

1. **Cycle Detection**:
   $$\text{cycle\_detected} = \neg \text{nx.is\_directed\_acyclic\_graph}(G)$$
   $$\text{cycle\_components} = \bigcup_{C \in \text{cycles}} C$$
   If $\text{cycle\_detected} = \text{True}$, then:
   - $\text{valid\_migration\_waves} = [\ ]$
   - $\text{expected\_decision} = \text{"REJECT\_CYCLE\_DETECTED"}$
   - $\text{safety\_gate\_required} = \text{True}$

2. **Blocker Identification**:
   A component $c \in V$ is an unconditional migration blocker if:
   $$\text{status}(c) \in \{\text{UNSUPPORTED}, \text{UNKNOWN}\}$$
   $$\text{expected\_blockers} = \{c \in V \mid \text{status}(c) \in \{\text{UNSUPPORTED}, \text{UNKNOWN}\}\}$$
   If $\text{expected\_blockers} \ne \emptyset$, then:
   - $\text{valid\_migration\_waves} = [\ ]$
   - $\text{expected\_decision} \in \{\text{"REJECT\_MIGRATION\_BLOCKED"}, \text{"REJECT\_INSUFFICIENT\_EVIDENCE"}\}$
   - $\text{safety\_gate\_required} = \text{True}$

3. **Valid Migration Wave Synthesis**:
   If and only if $G$ is a DAG and $\text{expected\_blockers} = \emptyset$:
   $$\text{valid\_migration\_waves} = \text{list}(\text{nx.topological\_generations}(G.\text{reverse}()))$$
   $$\text{expected\_decision} = \text{"APPROVE\_PLAN"}$$
   $$\text{safety\_gate\_required} = \text{False}$$

---

## 3. Strict Ground-Truth Isolation Architecture

To guarantee the scientific integrity of the benchmark, model-facing execution and evaluator scoring are separated by a strict architectural boundary.

```
┌────────────────────────────────────────────────────────┐
│                   TASK EXECUTION FLOW                  │
│                                                        │
│   Scenario Model ──┐                                   │
│   (Allowed Facts)  │                                   │
│                    ├──> PromptBuilder ──> Model Input  │
│   Benchmark Task ──┘                     (API / CLI)   │
│   (Instructions)                              │        │
│                                               ▼        │
│                                         Model Output   │
│                                               │        │
└───────────────────────────────────────────────┼────────┘
                                                │
════════════════════════════════════════════════╪═════════
      ARCHITECTURAL GROUND-TRUTH BOUNDARY       │
════════════════════════════════════════════════╪═════════
                                                │
┌───────────────────────────────────────────────┼────────┐
│                   EVALUATION FLOW             ▼        │
│                                         Evaluator      │
│                                         Scoring Engine │
│                                               ▲        │
│                                               │        │
│   GroundTruthRepository                       │        │
│   (datasets/generated/ground_truth/) ─────────┘        │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### 3.1 Architectural Enforcement Guarantees

1. **No Ground Truth in PromptBuilder**:
   The `PromptBuilder` takes only `BenchmarkTask` and `ScenarioModel`. Its signature accepts no repository, no ground-truth object, and no evaluator context.
2. **No Ground Truth in Model Serialization**:
   `BenchmarkTask` contains no ground-truth fields. The evaluator ground truth is stored in a completely separate directory hierarchy (`datasets/generated/ground_truth/`).
3. **Registry Isolation**:
   `BenchmarkRegistry` exposes discovery and registration exclusively for `BenchmarkTask` and `ScenarioModel`. It contains no methods or references to ground truth.
4. **Independent Evaluator Retrieval**:
   The `Evaluator` loads ground truth directly from `GroundTruthRepository` by `task_id` during post-hoc scoring. The model's context window never contains ground-truth answers.
5. **Automated Test Enforcement**:
   Unit and integration tests (`tests/integration/test_ground_truth_isolation.py`) systematically verify that prompt text, serialized model inputs, and task objects never leak ground-truth properties.
