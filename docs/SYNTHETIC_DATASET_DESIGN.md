# PHOENIX-EVAL Synthetic Enterprise Architecture Design

## 1. Overview & Architectural Philosophy

The **PHOENIX-EVAL Synthetic Generation Engine** synthesizes enterprise cryptographic architectures to rigorously evaluate AI models on complex cryptographic migration decisions.

Real-world enterprise systems contain heterogenous technologies, multi-tier dependency chains, legacy cryptographic algorithms, partial discovery telemetry, and third-party contractual constraints. Hand-crafted benchmark datasets are inherently limited in scale and variety, while random graphs lack architectural realism.

The synthetic engine bridges this gap by combining **realistic domain blueprints** with **graph-theoretic constraint modeling** and **deterministic procedural generation**.

---

## 2. Enterprise Architecture Domains

The engine synthesizes architectures across 5 distinct enterprise industry verticals, each exhibiting realistic component roles, technologies, cryptographic algorithms, and operational constraints:

| Domain | Key Focus & Topology | Representative Components | Target Migration Scope |
| :--- | :--- | :--- | :--- |
| **Banking / Payments** | High-security core banking, transaction signing, PCI-DSS compliance, hardware isolation. | Payment Switch, Core Ledger, HSM Core, Fraud Detection, Tokenization Engine, Mobile Banking App. | RSA-2048 / 3DES / ECDSA $\to$ **ML-KEM-1024**, **ML-DSA-87** |
| **Telecom / Network** | Core carrier infrastructure, low-latency session management, 5G authentication, lawful intercept. | 5G Core AMF, HLR/HSS Subscriber DB, Session Border Controller, Diameter Gateway, IMS Signaling. | RSA-3072 / ECDH-P256 $\to$ **ML-KEM-768**, **SLH-DSA-128** |
| **Cloud / Identity** | Scalable multi-tenant cloud control planes, identity federation, API gateways, secret management. | Cloud IAM, Key Vault, API Gateway, OAuth/OIDC Token Service, Tenant Registry, Ingress Proxy. | RSA-2048 / ECDSA-P384 $\to$ **ML-KEM-768**, **ML-DSA-65** |
| **Government / Critical** | Sovereign identity, classified enclave communications, national PKI, defense-in-depth isolation. | Root CA, Secure Document Vault, Sovereign Identity Broker, Air-gapped HSM, Enclave Gateways. | RSA-4096 / DH-3072 $\to$ **ML-KEM-1024**, **ML-DSA-87**, **SLH-DSA-256** |
| **Enterprise Services** | Corporate ERP, customer relationship management, internal payroll, supply chain coordination. | Enterprise ERP, Billing Engine, CRM Backend, Payroll Processor, Supply Chain Gateway, SSO Proxy. | RSA-2048 / AES-128 $\to$ **ML-KEM-768**, **ML-DSA-65** |

---

## 3. Tier Hierarchy & Blueprint Modeling

To mirror genuine enterprise topologies, each component blueprint is assigned an architectural tier:

```
[ Tier 0: External / Sinks ]        HSM Appliances, External SaaS/Banks, Cloud Key Vaults
             ▲
             │
[ Tier 3: Core Backend ]            Ledger DBs, Document Vaults, User Data Repositories
             ▲
             │
[ Tier 2: Microservices / Logic ]   Payment Switch, Fraud Analyzer, AMF, ERP Business Logic
             ▲
             │
[ Tier 1: Ingress / Edge ]          API Gateways, Ingress Proxies, Mobile / Web Clients
```

### 3.1 Edge Direction & Constraint Rules
Dependencies are primarily directed downwards from callers to foundational providers:
- Tier 1 (Gateways) depend on Tier 2 (Services).
- Tier 2 (Services) depend on Tier 3 (Databases) and Tier 0 (HSMs / Key Vaults).
- Foundational sinks (Tier 0 & Tier 3) have out-degree 0 in normal operation.
- Cross-tier dependencies and internal tier collaborations are injected according to graph complexity settings.

---

## 4. Graph Complexity Tiers

The generator supports four distinct structural complexity levels:

1. **SPARSE**:
   - Component Count: 4–6 components.
   - Cross-tier edge probability: 10%.
   - Intended for focused algorithmic isolation tasks (e.g., single blocker, isolated dependency).
2. **MODERATE** (Default):
   - Component Count: 7–12 components.
   - Cross-tier edge probability: 25%.
   - Realistic multi-tier microservice trees with multiple database dependencies and external endpoints.
3. **DENSE**:
   - Component Count: 13–20 components.
   - Cross-tier edge probability: 45%.
   - Highly interconnected enterprise graph with shared microservice hubs and multiple cryptographic authorities.
4. **ENTERPRISE_SCALE**:
   - Component Count: 25–40 components.
   - Complex meshes with multi-hop transitive paths, legacy enclaves, and distributed dependencies.

---

## 5. Epistemic Evidence Synthesis

Every generated scenario includes an evidence catalog that reflects real-world discovery telemetry:
- **Evidence Types**: Static code analysis (`STATIC_CODE_ANALYSIS`), network telemetry (`NETWORK_TELEMETRY`), configuration audits (`CONFIGURATION_AUDIT`), third-party vendor statements (`VENDOR_DOCUMENTATION`), runtime TLS handshakes (`RUNTIME_HANDSHAKE`), and integration test results (`PENETRATION_TEST_REPORT`).
- **Epistemic Categories**:
  - `OBSERVED`: Direct factual telemetry (e.g., active TLS cipher suite observed in production).
  - `INFERRED`: Derived facts requiring contextual deduction.
  - `ASSUMPTION`: Unverified human assumptions or documentation claims.
- **Verification Status**:
  - `VERIFIED`: Confirmed by repeatable automated scans.
  - `UNVERIFIED`: Anecdotal, outdated, or lacking signature/audit provenance.
  - `DISPUTED`: In conflict with runtime network telemetry.

---

## 6. Target Post-Quantum Cryptographic Algorithms

The engine tests migrations from legacy classical schemes to NIST-standardized Post-Quantum Cryptography (PQC):

| Target Algorithm | Standard | Category | Security Strength |
| :--- | :--- | :--- | :--- |
| **ML-KEM-768** | FIPS 203 | Key Encapsulation Mechanism | Category 3 (AES-192 equivalent) |
| **ML-KEM-1024** | FIPS 203 | Key Encapsulation Mechanism | Category 5 (AES-256 equivalent) |
| **ML-DSA-65** | FIPS 204 | Digital Signature Algorithm | Category 3 |
| **ML-DSA-87** | FIPS 204 | Digital Signature Algorithm | Category 5 |
| **SLH-DSA-128** | FIPS 205 | Stateless Hash-Based Signatures | Category 1 |
| **SLH-DSA-256** | FIPS 205 | Stateless Hash-Based Signatures | Category 5 |

---

## 7. Determinism & Generation Pipeline

1. **Seed Management**:
   The entire generation sequence is governed by `SeedManager`, deriving deterministic PRNG sub-seeds for component selection, dependency generation, evidence assignment, and task construction.
2. **Deterministic Artifact Hashing**:
   All timestamps on generated artifacts use fixed epochs (`2026-01-01T00:00:00Z`), ensuring that running the generator with the same seed reproduces bit-for-bit identical JSON artifacts and SHA-256 manifest digests.
3. **Strict Validation**:
   Generated datasets must pass schema cross-referential integrity checks:
   - All component IDs referenced in dependencies, compatibility, and evidence exist.
   - No self-referential or dangling edges exist.
   - Generated topological waves are mathematically validated using `verify_migration_wave_ordering`.
