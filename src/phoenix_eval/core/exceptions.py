"""Custom exception hierarchy for PHOENIX-EVAL."""

from typing import Any, Optional


class PhoenixEvalError(Exception):
    """Base exception for all PHOENIX-EVAL errors."""

    def __init__(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} (Context: {context_str})"
        return self.message


class ConfigurationError(PhoenixEvalError):
    """Raised when application configuration is missing, invalid, or malformed."""


class SchemaValidationError(PhoenixEvalError):
    """Raised when a data contract or Pydantic validation fails."""


class DatasetError(PhoenixEvalError):
    """Base error for dataset reading, loading, or parsing failures."""


class ScenarioError(DatasetError):
    """Raised when scenario structure or graph references are invalid."""


class TaskNotFoundError(DatasetError):
    """Raised when a requested benchmark task cannot be located."""


class GroundTruthError(DatasetError):
    """Raised when ground-truth files are missing, invalid, or inaccessible."""


class GroundTruthLeakageError(GroundTruthError):
    """Security violation raised if an attempt is made to expose evaluator ground truth to models."""


class SerializationError(PhoenixEvalError):
    """Raised when data serialization or deserialization fails."""


class RegistryError(PhoenixEvalError):
    """Base error for benchmark registry operations."""


class DuplicateEntityError(RegistryError):
    """Raised when an entity with an existing ID is registered again."""


class EntityNotFoundError(RegistryError):
    """Raised when an entity cannot be found in the registry."""


class IntegrityError(RegistryError):
    """Raised when graph, reference, or cross-entity integrity is violated."""


class ProviderError(PhoenixEvalError):
    """Base error for model provider operations."""


class ProviderTimeoutError(ProviderError):
    """Raised when a model provider request exceeds configured timeout."""


class ProviderRateLimitError(ProviderError):
    """Raised when a model provider rate limit or quota is exceeded."""


class ProviderAuthenticationError(ProviderError):
    """Raised when model provider credentials are missing or rejected."""


class ProviderExecutionError(ProviderError):
    """Raised when a model provider returns an unrecoverable execution error."""


class ProviderNetworkError(ProviderError):
    """Raised when network connectivity to provider endpoint fails."""


class ProviderInvalidRequestError(ProviderError):
    """Raised when provider rejects request due to invalid parameters or formatting."""


class ProviderServerError(ProviderError):
    """Raised when provider returns HTTP 5xx or transient upstream server failure."""


class ProviderEmptyResponseError(ProviderError):
    """Raised when provider returns an empty or whitespace-only response."""


class EvaluationError(PhoenixEvalError):
    """Base error for evaluation and scoring operations."""


class ExperimentError(PhoenixEvalError):
    """Base error for benchmark experiment coordination and execution."""
