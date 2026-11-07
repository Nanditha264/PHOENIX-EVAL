"""Central constants and definitions for PHOENIX-EVAL."""

from typing import Final

# Application Metadata
APP_NAME: Final[str] = "PHOENIX-EVAL"
APP_DESCRIPTION: Final[str] = "The Cryptographic Migration Intelligence Benchmark"
BENCHMARK_SPEC_VERSION: Final[str] = "1.0.0"

# Benchmark-wide system instruction for evaluated models
BENCHMARK_SYSTEM_PROMPT: Final[str] = (
    "You are a principal cryptographic migration architect. "
    "Analyze enterprise cryptographic architectures, evaluate readiness, "
    "and produce structured, deterministic migration plans according to specifications."
)

# Standard NIST Post-Quantum Cryptographic Standards (FIPS 203, 204, 205)
ALGORITHM_ML_KEM_512: Final[str] = "ML-KEM-512"
ALGORITHM_ML_KEM_768: Final[str] = "ML-KEM-768"
ALGORITHM_ML_KEM_1024: Final[str] = "ML-KEM-1024"
ALGORITHM_ML_DSA_44: Final[str] = "ML-DSA-44"
ALGORITHM_ML_DSA_65: Final[str] = "ML-DSA-65"
ALGORITHM_ML_DSA_87: Final[str] = "ML-DSA-87"
ALGORITHM_SLH_DSA_SHA2_128S: Final[str] = "SLH-DSA-SHA2-128s"
ALGORITHM_SLH_DSA_SHAKE_128S: Final[str] = "SLH-DSA-SHAKE-128s"

# Stateful Hash-Based Signature Standards (SP 800-208 / RFC 8554 / RFC 8391)
ALGORITHM_LMS: Final[str] = "LMS"
ALGORITHM_XMSS: Final[str] = "XMSS"

# Legacy / Deprecated Cryptographic Standards
ALGORITHM_RSA_1024: Final[str] = "RSA-1024"
ALGORITHM_RSA_2048: Final[str] = "RSA-2048"
ALGORITHM_RSA_3072: Final[str] = "RSA-3072"
ALGORITHM_RSA_4096: Final[str] = "RSA-4096"
ALGORITHM_ECDSA_P256: Final[str] = "ECDSA-P256"
ALGORITHM_ECDSA_P384: Final[str] = "ECDSA-P384"
ALGORITHM_ECDH_P256: Final[str] = "ECDH-P256"
ALGORITHM_ED25519: Final[str] = "ED25519"
ALGORITHM_X25519: Final[str] = "X25519"
ALGORITHM_3DES: Final[str] = "3DES"
ALGORITHM_AES_128_GCM: Final[str] = "AES-128-GCM"
ALGORITHM_AES_256_GCM: Final[str] = "AES-256-GCM"
ALGORITHM_SHA1: Final[str] = "SHA-1"
ALGORITHM_SHA256: Final[str] = "SHA-256"
ALGORITHM_SHA384: Final[str] = "SHA-384"
ALGORITHM_SHA512: Final[str] = "SHA-512"
ALGORITHM_MD5: Final[str] = "MD5"

# Hybrid Migration Combinations
ALGORITHM_HYBRID_ECDH_ML_KEM_768: Final[str] = "X25519+ML-KEM-768"
ALGORITHM_HYBRID_RSA_ML_DSA_65: Final[str] = "RSA-3072+ML-DSA-65"

SUPPORTED_PQC_ALGORITHMS: Final[frozenset[str]] = frozenset(
    {
        ALGORITHM_ML_KEM_512,
        ALGORITHM_ML_KEM_768,
        ALGORITHM_ML_KEM_1024,
        ALGORITHM_ML_DSA_44,
        ALGORITHM_ML_DSA_65,
        ALGORITHM_ML_DSA_87,
        ALGORITHM_SLH_DSA_SHA2_128S,
        ALGORITHM_SLH_DSA_SHAKE_128S,
        ALGORITHM_LMS,
        ALGORITHM_XMSS,
        ALGORITHM_HYBRID_ECDH_ML_KEM_768,
        ALGORITHM_HYBRID_RSA_ML_DSA_65,
    }
)

DEPRECATED_ALGORITHMS: Final[frozenset[str]] = frozenset(
    {
        ALGORITHM_RSA_1024,
        ALGORITHM_3DES,
        ALGORITHM_MD5,
        ALGORITHM_SHA1,
    }
)

SUPPORTED_ALGORITHMS: Final[frozenset[str]] = frozenset(
    SUPPORTED_PQC_ALGORITHMS
    | DEPRECATED_ALGORITHMS
    | {
        ALGORITHM_RSA_2048,
        ALGORITHM_RSA_3072,
        ALGORITHM_RSA_4096,
        ALGORITHM_ECDSA_P256,
        ALGORITHM_ECDSA_P384,
        ALGORITHM_ECDH_P256,
        ALGORITHM_ED25519,
        ALGORITHM_X25519,
        ALGORITHM_AES_128_GCM,
        ALGORITHM_AES_256_GCM,
        ALGORITHM_SHA256,
        ALGORITHM_SHA384,
        ALGORITHM_SHA512,
    }
)

# Supported File Formats
VALID_DATA_EXTENSIONS: Final[frozenset[str]] = frozenset({".json", ".jsonl", ".csv"})

# Confidence and Scoring Thresholds
MIN_EVIDENCE_CONFIDENCE: Final[float] = 0.0
MAX_EVIDENCE_CONFIDENCE: Final[float] = 1.0
HIGH_CONFIDENCE_THRESHOLD: Final[float] = 0.85
CRITICAL_VIOLATION_PENALTY: Final[float] = 100.0
SAFETY_GATE_PASS_THRESHOLD: Final[float] = 70.0

# Prefix Standards for Resource Identifiers
PREFIX_COMPONENT: Final[str] = "comp"
PREFIX_EDGE: Final[str] = "edge"
PREFIX_EVIDENCE: Final[str] = "evid"
PREFIX_COMPATIBILITY: Final[str] = "compati"
PREFIX_SCENARIO: Final[str] = "scen"
PREFIX_TASK: Final[str] = "task"
PREFIX_GROUND_TRUTH: Final[str] = "gt"
PREFIX_RESPONSE: Final[str] = "resp"
PREFIX_EVALUATION: Final[str] = "eval"
PREFIX_EXPERIMENT: Final[str] = "exp"
