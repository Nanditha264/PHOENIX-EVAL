"""Component generator synthesizing enterprise cryptographic components across five operational domains."""

from dataclasses import dataclass
from typing import Optional

from phoenix_eval.generator.config import ArchitectureDomain
from phoenix_eval.generator.seed_manager import SeedManager
from phoenix_eval.schemas.components import (
    ComponentType,
    CryptographicComponent,
    CryptographicRole,
)


@dataclass(frozen=True)
class ComponentBlueprint:
    """Template for generating domain-specific components with realistic cryptographic roles."""

    name_template: str
    component_type: ComponentType
    cryptographic_role: CryptographicRole
    description_template: str
    technologies: list[str]
    classical_algorithms: list[list[str]]
    target_pqc_algorithm: str
    metadata_tier: int  # 0: edge/client, 1: app/svc, 2: middleware, 3: core/hsm/db


DOMAIN_BLUEPRINTS: dict[ArchitectureDomain, list[ComponentBlueprint]] = {
    ArchitectureDomain.BANKING_PAYMENTS: [
        ComponentBlueprint(
            name_template="{org} Edge API Gateway",
            component_type=ComponentType.API_GATEWAY,
            cryptographic_role=CryptographicRole.TLS_TERMINATION,
            description_template="Edge ingress proxy handling customer TLS termination and routing.",
            technologies=[
                "Nginx 1.24 / OpenSSL 3.0.9",
                "HAProxy 2.8 / BoringSSL",
                "Envoy 1.28 / OpenSSL 3.1.2",
            ],
            classical_algorithms=[["RSA-2048", "AES-256-GCM"], ["ECDSA-P256", "AES-128-GCM"]],
            target_pqc_algorithm="ML-KEM-768",
            metadata_tier=0,
        ),
        ComponentBlueprint(
            name_template="{org} Core Banking Service",
            component_type=ComponentType.MICROSERVICE,
            cryptographic_role=CryptographicRole.AUTHENTICATION_TOKEN,
            description_template="High-throughput transactional ledger microservice issuing JWT session credentials.",
            technologies=[
                "Java 17 / Spring Boot 3.2 / BouncyCastle 1.77",
                "Go 1.21 / crypto/tls",
                "Java 21 / Quarkus 3.4",
            ],
            classical_algorithms=[["RSA-2048", "SHA-256"], ["ECDSA-P256", "SHA-384"]],
            target_pqc_algorithm="ML-DSA-65",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} Payment Settlement Processor",
            component_type=ComponentType.MICROSERVICE,
            cryptographic_role=CryptographicRole.DIGITAL_SIGNATURE,
            description_template="Interbank payment rail processor signing ISO 20022 wire transfers.",
            technologies=["Java 17 / BouncyCastle 1.76", "C++20 / OpenSSL 3.0"],
            classical_algorithms=[["RSA-3072", "SHA-384"], ["ECDSA-P256", "SHA-256"]],
            target_pqc_algorithm="ML-DSA-65",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} Payment Hardware Security Module",
            component_type=ComponentType.HARDWARE_SECURITY_MODULE,
            cryptographic_role=CryptographicRole.KEY_STORAGE,
            description_template="FIPS 140-2 Level 3 certified hardware security module for master key protection.",
            technologies=[
                "Firmware v7.4.2 Classical",
                "Firmware v8.1.0 PQC-Ready Beta",
                "Firmware v6.9.1 Legacy",
            ],
            classical_algorithms=[
                ["RSA-2048", "RSA-3072", "AES-256-GCM"],
                ["ECDSA-P256", "AES-256-GCM"],
            ],
            target_pqc_algorithm="ML-DSA-65",
            metadata_tier=3,
        ),
        ComponentBlueprint(
            name_template="{org} Financial Ledger Database",
            component_type=ComponentType.DATABASE,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
            description_template="ACID transaction store utilizing transparent cryptographic disk encryption.",
            technologies=[
                "PostgreSQL 16 / TDE pgcrypto",
                "Oracle 19c / Advanced Security",
                "CockroachDB 23.2",
            ],
            classical_algorithms=[["AES-256-GCM", "SHA-256"], ["AES-128-GCM"]],
            target_pqc_algorithm="AES-256-GCM",
            metadata_tier=3,
        ),
        ComponentBlueprint(
            name_template="{org} Mobile Banking Client App",
            component_type=ComponentType.CLIENT_SDK,
            cryptographic_role=CryptographicRole.TLS_TERMINATION,
            description_template="Consumer iOS and Android mobile banking native client applications.",
            technologies=["Swift 5.10 / Kotlin 1.9 / BoringSSL", "React Native 0.73 / OpenSSL"],
            classical_algorithms=[
                ["ECDSA-P256", "X25519", "AES-128-GCM"],
                ["RSA-2048", "AES-256-GCM"],
            ],
            target_pqc_algorithm="X25519+ML-KEM-768",
            metadata_tier=0,
        ),
        ComponentBlueprint(
            name_template="{org} Fraud Detection Engine",
            component_type=ComponentType.MICROSERVICE,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_IN_TRANSIT,
            description_template="Real-time ML fraud analysis scoring incoming debit and wire requests.",
            technologies=[
                "Python 3.11 / FastAPI / cryptography 42.0",
                "Rust 1.76 / tokio / rustls",
            ],
            classical_algorithms=[["AES-256-GCM", "ECDSA-P256"]],
            target_pqc_algorithm="ML-KEM-768",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} Financial Event Message Broker",
            component_type=ComponentType.MESSAGE_BROKER,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_IN_TRANSIT,
            description_template="Kafka messaging cluster streaming encrypted payment events between services.",
            technologies=["Apache Kafka 3.6 / mTLS", "RabbitMQ 3.12 / TLS 1.3"],
            classical_algorithms=[["RSA-2048", "AES-256-GCM"]],
            target_pqc_algorithm="ML-KEM-768",
            metadata_tier=2,
        ),
    ],
    ArchitectureDomain.TELECOM_NETWORK: [
        ComponentBlueprint(
            name_template="{org} 5G gNodeB Cell Controller",
            component_type=ComponentType.IOT_GATEWAY,
            cryptographic_role=CryptographicRole.TLS_TERMINATION,
            description_template="Radio access network edge controller terminating 5G user-plane encryption.",
            technologies=["Embedded Linux / OpenSSL 1.1.1u", "Yocto Linux / WolfSSL 5.6"],
            classical_algorithms=[["ECDSA-P256", "AES-256-GCM"], ["RSA-2048"]],
            target_pqc_algorithm="ML-KEM-768",
            metadata_tier=0,
        ),
        ComponentBlueprint(
            name_template="{org} 5G Core Access Management (AMF)",
            component_type=ComponentType.MICROSERVICE,
            cryptographic_role=CryptographicRole.AUTHENTICATION_TOKEN,
            description_template="5G Core network function executing 5G-AKA subscriber authentication.",
            technologies=["Go 1.21 / 5G Core Stack", "C++20 / DPDK 23.11"],
            classical_algorithms=[["ECDSA-P256", "SHA-256"], ["AES-256-GCM"]],
            target_pqc_algorithm="ML-DSA-44",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} SIM/eSIM OTA Key Vault",
            component_type=ComponentType.HARDWARE_SECURITY_MODULE,
            cryptographic_role=CryptographicRole.KEY_STORAGE,
            description_template="Carrier-grade HSM holding root symmetric and asymmetric Ki subscriber secrets.",
            technologies=["Telecommunications HSM v5.2", "FIPS 140-2 Level 4 Telecom Vault"],
            classical_algorithms=[["AES-128-GCM", "RSA-2048", "ECDSA-P256"]],
            target_pqc_algorithm="ML-DSA-65",
            metadata_tier=3,
        ),
        ComponentBlueprint(
            name_template="{org} IMS SIP Roaming Gateway",
            component_type=ComponentType.REVERSE_PROXY,
            cryptographic_role=CryptographicRole.TLS_TERMINATION,
            description_template="Border control proxy for voice-over-LTE/5G and cross-carrier roaming.",
            technologies=["Kamailio 5.7 / OpenSSL 3.0", "OpenSIPS 3.4 / LibreSSL"],
            classical_algorithms=[["RSA-2048", "AES-128-GCM"], ["ECDSA-P256"]],
            target_pqc_algorithm="ML-KEM-768",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} Subscriber Profile Registry",
            component_type=ComponentType.DATABASE,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
            description_template="High-availability database storing subscriber identity credentials and tariffs.",
            technologies=["Cassandra 4.1 / Encrypted Storage", "PostgreSQL 15 / TDE"],
            classical_algorithms=[["AES-256-GCM"]],
            target_pqc_algorithm="AES-256-GCM",
            metadata_tier=3,
        ),
    ],
    ArchitectureDomain.CLOUD_IDENTITY: [
        ComponentBlueprint(
            name_template="{org} Cloud Identity Provider (IdP)",
            component_type=ComponentType.SERVICE,
            cryptographic_role=CryptographicRole.AUTHENTICATION_TOKEN,
            description_template="Enterprise central identity provider issuing OpenID Connect and SAML tokens.",
            technologies=["Java 17 / Keycloak 23.0 / BouncyCastle 1.77", "Node.js 20 / jose 5.1"],
            classical_algorithms=[["RSA-2048", "SHA-256"], ["ECDSA-P256", "SHA-384"]],
            target_pqc_algorithm="ML-DSA-65",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} SSO Reverse Proxy",
            component_type=ComponentType.REVERSE_PROXY,
            cryptographic_role=CryptographicRole.TLS_TERMINATION,
            description_template="Edge security gateway intercepting enterprise web traffic for SSO authentication.",
            technologies=["Envoy 1.28 / BoringSSL", "Nginx 1.24 / OpenSSL 3.1"],
            classical_algorithms=[["ECDSA-P256", "AES-256-GCM"], ["RSA-2048"]],
            target_pqc_algorithm="ML-KEM-768",
            metadata_tier=0,
        ),
        ComponentBlueprint(
            name_template="{org} Cloud Key Management Service (KMS)",
            component_type=ComponentType.KEY_MANAGEMENT_SERVICE,
            cryptographic_role=CryptographicRole.KEY_STORAGE,
            description_template="Multi-tenant cryptographic key lifecycle and envelope encryption service.",
            technologies=["Go 1.22 / KMS Backend", "C++ / PKCS#11 HSM Interop"],
            classical_algorithms=[["RSA-3072", "AES-256-GCM"], ["ECDSA-P256"]],
            target_pqc_algorithm="ML-KEM-1024",
            metadata_tier=3,
        ),
        ComponentBlueprint(
            name_template="{org} Privileged Access Manager (PAM)",
            component_type=ComponentType.APPLICATION,
            cryptographic_role=CryptographicRole.DIGITAL_SIGNATURE,
            description_template="Zero-trust access gateway generating ephemeral SSH certificates for engineers.",
            technologies=["Go 1.21 / HashiCorp Vault 1.15", "Python 3.11 / cryptography 42.0"],
            classical_algorithms=[["Ed25519", "RSA-3072"]],
            target_pqc_algorithm="ML-DSA-65",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} Corporate Directory Database",
            component_type=ComponentType.DATABASE,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
            description_template="LDAP / OpenLDAP user directory database with hashed and encrypted attributes.",
            technologies=["OpenLDAP 2.6 / TLS 1.3", "Active Directory / Kerberos"],
            classical_algorithms=[["AES-256-GCM", "SHA-384"]],
            target_pqc_algorithm="AES-256-GCM",
            metadata_tier=3,
        ),
    ],
    ArchitectureDomain.GOVERNMENT_CRITICAL: [
        ComponentBlueprint(
            name_template="{org} National Root Certificate Authority",
            component_type=ComponentType.CERTIFICATE_AUTHORITY,
            cryptographic_role=CryptographicRole.CERTIFICATE_ISSUANCE,
            description_template="Offline root CA issuing top-level trust anchors for government digital services.",
            technologies=["EJBCA 8.1 / SafeNet Luna HSM", "OpenSSL 3.0 Custom Root Appliance"],
            classical_algorithms=[["RSA-3072", "SHA-384"], ["RSA-4096", "SHA-512"]],
            target_pqc_algorithm="ML-DSA-87",
            metadata_tier=3,
        ),
        ComponentBlueprint(
            name_template="{org} Citizen Digital ID Portal",
            component_type=ComponentType.APPLICATION,
            cryptographic_role=CryptographicRole.TLS_TERMINATION,
            description_template="Public-facing web portal for citizen taxes, healthcare, and passport renewal.",
            technologies=["Next.js / Node.js 20 / TLS 1.3", "Java 21 / Spring Boot 3"],
            classical_algorithms=[["ECDSA-P256", "AES-256-GCM"], ["RSA-2048"]],
            target_pqc_algorithm="ML-KEM-768",
            metadata_tier=0,
        ),
        ComponentBlueprint(
            name_template="{org} Official Document Signing Service",
            component_type=ComponentType.SERVICE,
            cryptographic_role=CryptographicRole.DIGITAL_SIGNATURE,
            description_template="High-assurance legal document timestamping and digital signature service.",
            technologies=["Java 17 / Apache PDFBox / BouncyCastle 1.76", "C# .NET 8 / PKCS#7"],
            classical_algorithms=[["RSA-2048", "SHA-256"], ["ECDSA-P256"]],
            target_pqc_algorithm="ML-DSA-65",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} Border Control Biometric e-Gate",
            component_type=ComponentType.IOT_GATEWAY,
            cryptographic_role=CryptographicRole.CERTIFICATE_ISSUANCE,
            description_template="Airport electronic passport inspection gate verifying ICAO PKD certificates.",
            technologies=["C++17 / Embedded Linux / OpenSSL 1.1.1", "Rust / WolfSSL"],
            classical_algorithms=[["ECDSA-P256", "RSA-2048"]],
            target_pqc_algorithm="ML-DSA-44",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} National Civil Registry Database",
            component_type=ComponentType.DATABASE,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
            description_template="Encrypted repository holding citizen vital statistics and biometric credentials.",
            technologies=["Oracle 19c Enterprise / TDE", "PostgreSQL 15 / pgcrypto"],
            classical_algorithms=[["AES-256-GCM"]],
            target_pqc_algorithm="AES-256-GCM",
            metadata_tier=3,
        ),
    ],
    ArchitectureDomain.ENTERPRISE_SERVICES: [
        ComponentBlueprint(
            name_template="{org} Central ERP Accounting Core",
            component_type=ComponentType.APPLICATION,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_IN_TRANSIT,
            description_template="Core ERP accounting and human capital system coordinating enterprise orders.",
            technologies=["SAP NetWeaver / CommonCryptoLib", "Java 17 / Spring Boot"],
            classical_algorithms=[["RSA-2048", "AES-256-GCM"]],
            target_pqc_algorithm="ML-KEM-768",
            metadata_tier=1,
        ),
        ComponentBlueprint(
            name_template="{org} B2B EDI Partner Gateway",
            component_type=ComponentType.API_GATEWAY,
            cryptographic_role=CryptographicRole.DIGITAL_SIGNATURE,
            description_template="AS2 / AS4 electronic data interchange gateway trading signed invoices with vendors.",
            technologies=[
                "Java 17 / Mendelson AS2 / BouncyCastle 1.74",
                "Python 3.10 / AS4 Engine",
            ],
            classical_algorithms=[["RSA-2048", "SHA-256"], ["ECDSA-P256"]],
            target_pqc_algorithm="ML-DSA-65",
            metadata_tier=0,
        ),
        ComponentBlueprint(
            name_template="{org} Enterprise Kafka Event Stream",
            component_type=ComponentType.MESSAGE_BROKER,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_IN_TRANSIT,
            description_template="Distributed event bus propagating supply chain telemetry between warehouse apps.",
            technologies=["Apache Kafka 3.6 / mTLS / SASL_SSL", "Confluent Enterprise Kafka"],
            classical_algorithms=[["RSA-2048", "AES-256-GCM"]],
            target_pqc_algorithm="ML-KEM-768",
            metadata_tier=2,
        ),
        ComponentBlueprint(
            name_template="{org} Enterprise Customer Database",
            component_type=ComponentType.DATABASE,
            cryptographic_role=CryptographicRole.DATA_ENCRYPTION_AT_REST,
            description_template="Multi-region SQL cluster with encrypted data tables and customer records.",
            technologies=["PostgreSQL 16 / AWS Aurora TDE", "MySQL 8.0 Enterprise"],
            classical_algorithms=[["AES-256-GCM"]],
            target_pqc_algorithm="AES-256-GCM",
            metadata_tier=3,
        ),
        ComponentBlueprint(
            name_template="{org} Legacy Mainframe Connector",
            component_type=ComponentType.LEGACY_SYSTEM,
            cryptographic_role=CryptographicRole.KEY_STORAGE,
            description_template="IBM z/OS Mainframe middleware connector handling legacy batch settlement.",
            technologies=["IBM z/OS v2.4 / ICSF Crypto", "Java 8 / IBM JCE 1.8"],
            classical_algorithms=[["RSA-1024", "DES3", "AES-128-GCM"]],
            target_pqc_algorithm="ML-DSA-65",
            metadata_tier=3,
        ),
    ],
}

ORGANIZATION_NAMES: dict[ArchitectureDomain, list[str]] = {
    ArchitectureDomain.BANKING_PAYMENTS: [
        "Apex Meridian Financial",
        "Boreal Trust Corp",
        "Cobalt Horizon Bank",
        "Solaria Payment Systems",
    ],
    ArchitectureDomain.TELECOM_NETWORK: [
        "StrataCom Global Telecom",
        "NexusWave Networks",
        "Veloce Cellular Infra",
        "AeroLink Mobile Core",
    ],
    ArchitectureDomain.CLOUD_IDENTITY: [
        "AetherIdentity Enterprise Systems",
        "OmniAuth Cloud Services",
        "Veritas Access Security",
        "Zenith Directory Services",
    ],
    ArchitectureDomain.GOVERNMENT_CRITICAL: [
        "Helios Public Digital Authority",
        "Crown Digital Infrastructure",
        "National Secure Gateway Agency",
        "Aegis Civic Identity",
    ],
    ArchitectureDomain.ENTERPRISE_SERVICES: [
        "Vanguard Logistics Platform",
        "Titan Enterprise Commerce",
        "Equinox Supply Chain Network",
        "Kestrel Cloud ERP",
    ],
}


def generate_components_for_domain(
    domain: ArchitectureDomain,
    seed_mgr: SeedManager,
    count: int = 5,
    custom_org: Optional[str] = None,
) -> list[CryptographicComponent]:
    """Generate realistic cryptographic components for a given architecture domain."""
    org_list = ORGANIZATION_NAMES[domain]
    org_name = custom_org or seed_mgr.choice(org_list)
    blueprints = DOMAIN_BLUEPRINTS[domain]

    # Select blueprints to instantiate (repeat with suffixes if count > len(blueprints))
    selected_blueprints: list[ComponentBlueprint] = []
    while len(selected_blueprints) < count:
        for bp in blueprints:
            selected_blueprints.append(bp)
            if len(selected_blueprints) >= count:
                break

    components: list[CryptographicComponent] = []
    type_counts: dict[str, int] = {}

    for _idx, bp in enumerate(selected_blueprints):
        base_name = bp.name_template.format(org=org_name)
        type_key = bp.component_type.value.lower().replace("_", "-")
        type_counts[type_key] = type_counts.get(type_key, 0) + 1
        comp_id = f"comp-{type_key}-{type_counts[type_key]:02d}"

        tech = seed_mgr.choice(bp.technologies)
        algs = seed_mgr.choice(bp.classical_algorithms)

        comp = CryptographicComponent(
            component_id=comp_id,
            component_name=base_name
            if type_counts[type_key] == 1
            else f"{base_name} #{type_counts[type_key]}",
            component_type=bp.component_type,
            cryptographic_role=bp.cryptographic_role,
            description=bp.description_template,
            technology=tech,
            current_algorithms=algs,
            evidence_references=[],  # Populated during evidence generation
            metadata={
                "domain": domain.value,
                "tier": bp.metadata_tier,
                "target_pqc_algorithm": bp.target_pqc_algorithm,
            },
        )
        components.append(comp)

    return components
