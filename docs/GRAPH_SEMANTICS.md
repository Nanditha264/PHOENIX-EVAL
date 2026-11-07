# PHOENIX-EVAL Dependency Graph Semantics & Topological Ordering

## 1. Mathematical Formalism

In the PHOENIX-EVAL benchmark, enterprise software architectures and their cryptographic dependencies are modeled as a finite directed graph:

$$G = (V, E)$$

where:
- **$V$ (Vertices / Nodes)**: The set of system components $\{c_1, c_2, \dots, c_n\}$, representing microservices, database storage systems, cryptographic hardware modules (HSMs), API gateways, external third-party services, certificate authorities, and authentication platforms.
- **$E$ (Edges)**: The set of directed dependency relationships between components.

---

## 2. Explicit Edge Direction Convention

To eliminate ambiguity across all evaluation scenarios, tasks, solvers, and rubrics, PHOENIX-EVAL adheres strictly to the following foundational invariant:

> **Core Invariant**: A directed edge $(u, v) \in E$ denotes that component $u$ depends on component $v$.
> In this relationship, $u$ is the **caller / consumer / dependent**, and $v$ is the **callee / prerequisite / provider**.

```
[ Component u ]  ────────(depends on)────────>  [ Component v ]
(Caller / Consumer)                           (Prerequisite / Callee)
```

### 2.1 Degree Interpretations

Under this convention:
- **Out-degree of $u$ ($\text{deg}^+(u)$)**: The number of direct prerequisite components that $u$ requires in order to function or transition safely.
- **In-degree of $v$ ($\text{deg}^-(v)$)**: The number of upstream callers or consumers that depend directly upon $v$.

### 2.2 Sinks and Sources
- **Foundational Infrastructure (Sinks in $G$)**:
  Core hardware security modules (HSMs), database clusters, identity directories, and root certificate authorities typically do not call upward into business logic services. Therefore, in $G$, they have **$\text{deg}^+(v) = 0$** (out-degree 0). They are pure prerequisites.
- **Edge Clients / Entrypoints (Sources in $G$)**:
  Mobile applications, web single-page apps, and public API gateways call internal microservices but are not depended upon by core backend databases. In $G$, they have **$\text{deg}^-(u) = 0$** (in-degree 0).

---

## 3. Cryptographic Migration Prerequisites

During a cryptographic migration (e.g., transitioning from classical RSA/ECDSA to post-quantum ML-KEM or ML-DSA), a caller cannot successfully communicate using new cryptographic primitives until the callee supports them.

Specifically:
- If service $A$ calls database $B$ with encrypted payloads, database $B$ must support the new algorithm and decryption schemes **before or simultaneously with** service $A$.
- If an authentication service relies on an HSM for signing tokens, the HSM firmware must support the target algorithm before the authentication service can issue quantum-safe signatures.

Therefore:
$$\text{Migration Order: } v \text{ must be upgraded before } u \quad (\forall (u, v) \in E)$$

---

## 4. Reversed Graph ($G^R$) and Migration Wave Computation

Because edge $(u, v)$ points from caller to prerequisite, the prerequisite relationship is directed backwards relative to execution/migration order. To compute the topological wave sequence:

### 4.1 Reversed Graph Definition
We define the reversed graph $G^R = (V, E^R)$ where:
$$E^R = \{(v, u) \mid (u, v) \in E\}$$

In $G^R$, an edge $(v, u)$ points from **prerequisite $v$** to **dependent $u$**.

```
In G:    u ────(depends on)────> v
In G^R:  v ────(enables)───────> u
```

### 4.2 Topological Generation (Wave Decomposition)
Assuming $G$ is a Directed Acyclic Graph (DAG):
1. **Wave 1 ($W_1$)**: Components in $G^R$ with in-degree 0 ($\text{deg}^-_{G^R}(v) = 0$), which correspond to components in $G$ with out-degree 0 ($\text{deg}^+_G(v) = 0$). These are foundational sinks (HSMs, standalone databases, leaf providers) with no remaining unmigrated prerequisites.
2. **Wave $k$ ($W_k$)**: Once all components in waves $W_1, \dots, W_{k-1}$ are migrated, the components whose prerequisites are entirely contained in $\bigcup_{i=1}^{k-1} W_i$ are eligible for Wave $k$.
3. Mathematically, for NetworkX:
   $$\text{waves} = \text{list}(\text{nx.topological\_generations}(G.\text{reverse}()))$$

### 4.3 Concrete Example

Consider the following system:
- `API-GW` depends on `AUTH-SVC`
- `AUTH-SVC` depends on `HSM-CORE`
- `AUTH-SVC` depends on `USER-DB`

In graph $G$:
```
API-GW ──> AUTH-SVC ──> HSM-CORE
                     ──> USER-DB
```

Edges in $G$:
- `(API-GW, AUTH-SVC)`
- `(AUTH-SVC, HSM-CORE)`
- `(AUTH-SVC, USER-DB)`

In reversed graph $G^R$:
```
HSM-CORE ──> AUTH-SVC ──> API-GW
USER-DB  ──>
```

Wave Calculation on $G^R$:
- **Wave 1**: `["HSM-CORE", "USER-DB"]` (prerequisites with out-degree 0 in $G$)
- **Wave 2**: `["AUTH-SVC"]` (prerequisites migrated in Wave 1)
- **Wave 3**: `["API-GW"]` (prerequisites migrated in Wave 2)

---

## 5. Dependency Cycles and Deadlock Detection

If $G$ contains a directed cycle:
$$c_1 \to c_2 \to \dots \to c_k \to c_1$$

Then:
1. $G$ is not a DAG ($\text{nx.is\_directed\_acyclic\_graph}(G) = \text{False}$).
2. Component $c_1$ requires $c_2$ to be migrated first, but $c_2$ transitively requires $c_1$ to be migrated first.
3. Without introducing an intermediate backward-compatibility dual-stack proxy, decoupling interface, or cyclic migration protocol, **no linear topological migration sequence exists**.
4. The system is in a **migration deadlock**.

In PHOENIX-EVAL, when a cycle is present:
- Evaluator ground truth flags `cycle_detected = True`.
- `valid_migration_waves = []` (null/empty).
- The model must recognize the cycle, identify the participating nodes, refuse to output an unverified linear ordering, and recommend architectural decoupling or a dual-stack migration strategy.

---

## 6. Migration Blocker Invariant

A component $c \in V$ is an **unconditional migration blocker** if:
1. Its compatibility status is `UNSUPPORTED`, or
2. Its compatibility status is `UNKNOWN` (under strict pre-migration validation policy).

### 6.1 Transitive Impact
Any component $u$ that transitively depends on an unsupported component $v$ ($u \rightsquigarrow v$) cannot complete its cryptographic migration, because its communication channel to $v$ cannot be secured with the target algorithm.

Furthermore, even if an unsupported component is a top-level edge client (in-degree 0, e.g., legacy mobile client fleet), the system as a whole **cannot claim complete end-to-end migration verification** until the client compatibility is resolved or deprecated.

---

## 7. Automated Invariant Verification (`verify_migration_wave_ordering`)

The benchmark engine enforces wave correctness through the mathematical verifier:
`phoenix_eval.generator.constraints.verify_migration_wave_ordering(graph, proposed_waves)`

The algorithm validates:
1. **Partition Property**: Every component appears exactly once across all waves ($\bigcup W_i = V$ and $W_i \cap W_j = \emptyset$ for $i \ne j$).
2. **Causal Ordering Property**: For every directed edge $(u, v) \in E$, the wave index of prerequisite $v$ must be strictly less than the wave index of dependent $u$:
   $$\text{wave\_index}(v) < \text{wave\_index}(u)$$
If any proposed wave violates this condition, the verifier rejects the plan and outputs the exact violating edge $(u, v)$ and wave indices.
