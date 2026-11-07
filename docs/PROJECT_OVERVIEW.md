# PHOENIX-EVAL: Project Overview

## 1. Executive Summary

**PHOENIX-EVAL** (*The Cryptographic Migration Intelligence Benchmark*) is an evaluation platform engineered to test the capability of artificial intelligence models to reason about large-scale, high-stakes cryptographic migrations in interconnected enterprise architectures.

With the ratification of NIST Post-Quantum Cryptography standards (FIPS 203 ML-KEM, FIPS 204 ML-DSA, and FIPS 205 SLH-DSA) and the impending obsolescence of classical asymmetric cryptography (RSA, ECDSA, ECDH), enterprise organizations face an unprecedented multi-year migration challenge.

Because enterprise cryptographic systems are deeply entangled across multi-tier networks, hardware security modules (HSMs), database transparent encryption layers, and third-party APIs, a single sequencing error can cause catastrophic outages or silent security degradation. 

PHOENIX-EVAL evaluates whether AI assistants can reliably analyze discovery telemetry, recognize hidden dependency traps, refuse unsupported claims, and formulate verifiable transition plans.

---

## 2. Core Benchmark Objectives

PHOENIX-EVAL establishes eight core evaluation objectives:

1. **Interpret Cryptographic Discovery Evidence:** Parse and reconcile heterogeneous discovery telemetry (SBOMs, static code analysis, network packet captures, cipher scans, and vendor hardware certifications).
2. **Identify Direct & Transitive System Dependencies:** Traverse directed dependency networks to map upstream callers and downstream service dependencies.
3. **Distinguish SUPPORTED, UNSUPPORTED, and UNKNOWN Compatibility:** Never convert `UNKNOWN` status into `SUPPORTED` without verified evidence.
4. **Produce Dependency-Aware Migration Plans:** Formulate topological wave orders that upgrade foundational prerequisites before dependent consumers.
5. **Recognize Circular Dependencies & Blockers:** Identify non-DAG topological structures, hardware-level deadlocks, and legacy firmware limitations that block progress.
6. **Respect Validation & Fallback Requirements:** Mandate hybrid dual-stack modes (e.g., X25519 + ML-KEM-768) and staging regression tests before production cutover.
7. **Avoid Unsupported Assumptions:** Resist hallucinating library or protocol support when evidence is absent or ambiguous.
8. **Calibrate Epistemic Confidence:** Refuse to certify migration completion when evidence is insufficient or contradictory.

---

## 3. The Enterprise Cryptographic Landscape

The benchmark reflects genuine real-world enterprise constraints:

- **Hardware Security Modules (HSMs):** Often governed by long-lifecycle firmware certifications (FIPS 140-2 / 140-3) that cannot be updated via simple software patches.
- **Packet Size MTU Fragmentation:** Post-quantum public keys and ciphertexts are significantly larger than classical keys (e.g., ML-KEM-768 public keys are 1,184 bytes vs. 32 bytes for X25519). Many cellular networks and carrier middleboxes fragment or drop multi-kilobyte TLS ClientHello handshakes.
- **Certificate Authority (CA) Chains:** Deep hierarchical trust chains where issuing CAs, intermediate CAs, and end-entity certificates must migrate in coordinated phases.
- **Zero-Downtime High Availability:** Core banking databases, payment gateways, and trading platforms cannot be taken offline for migration; they require dual-stack hybrid operation.

---

## 4. Benchmark Taxonomy & Challenge Categories

PHOENIX-EVAL organizes benchmark tasks across six primary reasoning categories:

| Category | Description | Primary Metric |
| :--- | :--- | :--- |
| **DEPENDENCY_DISCOVERY** | Mapping complex calling, encryption, and key-sharing links from discovery artifacts. | Recall & Precision of Edge Graph |
| **COMPATIBILITY_ASSESSMENT** | Accurately evaluating compatibility while maintaining strict `UNKNOWN` discipline. | False Positive Rate on Unverified Targets |
| **MIGRATION_SEQUENCING** | Generating wave sequences that satisfy topological and operational constraints. | Topological Order Validity & Downtime Risk |
| **BLOCKER_IDENTIFICATION** | Pinpointing hardware, regulatory, or circular barriers preventing upgrade. | Blocker Detection Recall |
| **EVIDENCE_VERIFICATION** | Testing epistemic humility: distinguishing verified observations from unverified assumptions. | Epistemic Calibration Score |
| **RISK_ASSESSMENT** | Holistic evaluation of blast radius, fallback strategies, and regulatory compliance. | Composite Safety Gate Pass Rate |

---

## 5. Non-Goals & System Boundaries

- **Not an Execution Platform:** PHOENIX-EVAL evaluates AI responses; it does not deploy cryptographic keys or execute production migrations.
- **Not an Autonomous Agent Framework:** The platform contains zero agent loops, vector databases, or dynamic tool calling chains. It is a strictly controlled, reproducible benchmark test harness.
- **Zero API Key Requirement in Phase 1:** Phase 1 focuses on core architecture, data contracts, and deterministic mocks, enabling complete offline testing without financial cost or external API dependencies.
