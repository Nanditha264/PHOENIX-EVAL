"""Cryptographic component schema representing system nodes in an enterprise architecture."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from phoenix_eval.schemas.common import StrEnum
from phoenix_eval.utils.identifiers import ensure_valid_identifier


class ComponentType(StrEnum):
    """Architectural classification of a system component."""

    APPLICATION = "APPLICATION"
    MICROSERVICE = "MICROSERVICE"
    SERVICE = "SERVICE"
    DATABASE = "DATABASE"
    API_GATEWAY = "API_GATEWAY"
    REVERSE_PROXY = "REVERSE_PROXY"
    LOAD_BALANCER = "LOAD_BALANCER"
    HARDWARE_SECURITY_MODULE = "HARDWARE_SECURITY_MODULE"
    CERTIFICATE_AUTHORITY = "CERTIFICATE_AUTHORITY"
    KEY_MANAGEMENT_SERVICE = "KEY_MANAGEMENT_SERVICE"
    CLIENT_SDK = "CLIENT_SDK"
    MESSAGE_BROKER = "MESSAGE_BROKER"
    THIRD_PARTY_SERVICE = "THIRD_PARTY_SERVICE"
    LEGACY_SYSTEM = "LEGACY_SYSTEM"
    IOT_GATEWAY = "IOT_GATEWAY"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"
    CRYPTOGRAPHIC_LIBRARY = "CRYPTOGRAPHIC_LIBRARY"
    DESKTOP_CLIENT = "DESKTOP_CLIENT"
    MONITORING_SERVICE = "MONITORING_SERVICE"


class CryptographicRole(StrEnum):
    """Primary cryptographic function performed by the component."""

    TLS_TERMINATION = "TLS_TERMINATION"
    DATA_ENCRYPTION_AT_REST = "DATA_ENCRYPTION_AT_REST"
    DATA_ENCRYPTION_IN_TRANSIT = "DATA_ENCRYPTION_IN_TRANSIT"
    DIGITAL_SIGNATURE = "DIGITAL_SIGNATURE"
    KEY_EXCHANGE = "KEY_EXCHANGE"
    KEY_GENERATION = "KEY_GENERATION"
    KEY_STORAGE = "KEY_STORAGE"
    AUTHENTICATION_TOKEN = "AUTHENTICATION_TOKEN"
    CERTIFICATE_ISSUANCE = "CERTIFICATE_ISSUANCE"
    HASHING_INTEGRITY = "HASHING_INTEGRITY"
    PASSWORD_HASHING = "PASSWORD_HASHING"


class CryptographicComponent(BaseModel):
    """An enterprise system component with cryptographic responsibilities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: str = Field(
        ...,
        description="Unique identifier for the component (e.g. 'comp-auth-svc-01').",
    )
    component_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable name of the system component.",
    )
    component_type: ComponentType = Field(
        ...,
        description="Architectural type of the component.",
    )
    cryptographic_role: CryptographicRole = Field(
        ...,
        description="Primary cryptographic role executed by this component.",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Functional description of the component and its cryptographic context.",
    )
    technology: str = Field(
        ...,
        min_length=1,
        description="Technology stack (e.g. 'Java 17 / BouncyCastle 1.76', 'Go 1.22 / crypto/tls').",
    )
    current_algorithms: list[str] = Field(
        default_factory=list,
        description="List of current cryptographic algorithms in active use (e.g. ['RSA-2048', 'AES-256-GCM']).",
    )
    evidence_references: list[str] = Field(
        default_factory=list,
        description="Identifiers of EvidenceRecords supporting the component's configuration.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary domain-specific metadata (e.g. criticality, tier, owner).",
    )

    @field_validator("component_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return ensure_valid_identifier(v, field_name="component_id")

    @field_validator("evidence_references")
    @classmethod
    def validate_evidence_refs(cls, v: list[str]) -> list[str]:
        return [ensure_valid_identifier(ref, field_name="evidence_reference") for ref in v]
