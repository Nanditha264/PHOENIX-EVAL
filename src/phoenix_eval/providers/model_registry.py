"""Model registry managing provider configurations, built-in definitions, and provider factory."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from phoenix_eval.core.exceptions import EntityNotFoundError, ProviderAuthenticationError
from phoenix_eval.providers.base import BaseModelProvider, MockModelProvider
from phoenix_eval.providers.gemini_provider import GoogleGeminiProvider
from phoenix_eval.providers.openai_provider import OpenAICompatibleProvider


class ModelConfig(BaseModel):
    """Specification for an AI model evaluated by PHOENIX-EVAL."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(..., description="Unique benchmark model alias or identifier.")
    provider_type: Literal["mock", "openai", "google"] = Field(
        ...,
        description="Underlying provider adapter architecture.",
    )
    model_name: str = Field(..., description="Upstream model identifier passed to provider.")
    model_version: str = Field(default="default", description="Model version or snapshot tag.")
    api_key_env_var: str = Field(
        default="OPENAI_API_KEY",
        description="Name of the environment variable containing API key (never contains secret values).",
    )
    base_url: Optional[str] = Field(
        default=None, description="Optional custom provider endpoint URL."
    )
    default_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    default_max_tokens: int = Field(default=2048, ge=1)
    timeout_seconds: float = Field(default=60.0, gt=0.0)
    max_retries: int = Field(default=3, ge=0)
    is_mock: bool = Field(default=False)
    pricing_per_1k_prompt: Optional[float] = Field(default=None, ge=0.0)
    pricing_per_1k_completion: Optional[float] = Field(default=None, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelRegistry:
    """Central registry of model configurations and provider factory."""

    def __init__(self) -> None:
        self._models: dict[str, ModelConfig] = {}
        self._register_default_models()

    def _register_default_models(self) -> None:
        """Register default mock and real model configurations."""
        # 1. Mock Models
        self.register_model(
            ModelConfig(
                model_id="mock-model-v1",
                provider_type="mock",
                model_name="mock-model-v1",
                model_version="1.0.0",
                api_key_env_var="",
                is_mock=True,
                metadata={
                    "behavior": "valid_migration",
                    "description": "Deterministic valid contract mock model",
                },
            )
        )
        self.register_model(
            ModelConfig(
                model_id="mock-valid-migration",
                provider_type="mock",
                model_name="mock-valid-migration",
                model_version="1.0.0",
                api_key_env_var="",
                is_mock=True,
                metadata={
                    "behavior": "valid_migration",
                    "description": "Deterministic scenario-aware valid migration mock model",
                },
            )
        )
        self.register_model(
            ModelConfig(
                model_id="mock-refusal-v1",
                provider_type="mock",
                model_name="mock-refusal-v1",
                model_version="1.0.0",
                api_key_env_var="",
                is_mock=True,
                metadata={
                    "behavior": "refusal",
                    "description": "Deterministic cautious refusal mock model",
                },
            )
        )
        self.register_model(
            ModelConfig(
                model_id="mock-unsafe-v1",
                provider_type="mock",
                model_name="mock-unsafe-v1",
                model_version="1.0.0",
                api_key_env_var="",
                is_mock=True,
                metadata={
                    "behavior": "unsafe_migration",
                    "description": "Deterministic unsafe flawed mock model",
                },
            )
        )
        self.register_model(
            ModelConfig(
                model_id="mock-unsafe-migration",
                provider_type="mock",
                model_name="mock-unsafe-migration",
                model_version="1.0.0",
                api_key_env_var="",
                is_mock=True,
                metadata={
                    "behavior": "unsafe_migration",
                    "description": "Deterministic unsafe migration mock model",
                },
            )
        )
        self.register_model(
            ModelConfig(
                model_id="mock-malformed-v1",
                provider_type="mock",
                model_name="mock-malformed-v1",
                model_version="1.0.0",
                api_key_env_var="",
                is_mock=True,
                metadata={
                    "behavior": "malformed_response",
                    "description": "Deterministic malformed syntax mock model",
                },
            )
        )
        self.register_model(
            ModelConfig(
                model_id="mock-malformed-response",
                provider_type="mock",
                model_name="mock-malformed-response",
                model_version="1.0.0",
                api_key_env_var="",
                is_mock=True,
                metadata={
                    "behavior": "malformed_response",
                    "description": "Deterministic malformed response mock model",
                },
            )
        )

        # 2. OpenAI-compatible Models
        self.register_model(
            ModelConfig(
                model_id="gpt-4o",
                provider_type="openai",
                model_name="gpt-4o",
                model_version="2024-08-06",
                api_key_env_var="OPENAI_API_KEY",
                pricing_per_1k_prompt=0.0025,
                pricing_per_1k_completion=0.010,
                is_mock=False,
            )
        )
        self.register_model(
            ModelConfig(
                model_id="gpt-4o-mini",
                provider_type="openai",
                model_name="gpt-4o-mini",
                model_version="2024-07-18",
                api_key_env_var="OPENAI_API_KEY",
                pricing_per_1k_prompt=0.00015,
                pricing_per_1k_completion=0.0006,
                is_mock=False,
            )
        )

        # 3. Google Gemini Models
        self.register_model(
            ModelConfig(
                model_id="gemini-1.5-pro",
                provider_type="google",
                model_name="gemini-1.5-pro",
                model_version="002",
                api_key_env_var="GOOGLE_API_KEY",
                pricing_per_1k_prompt=0.00125,
                pricing_per_1k_completion=0.005,
                is_mock=False,
            )
        )
        self.register_model(
            ModelConfig(
                model_id="gemini-1.5-flash",
                provider_type="google",
                model_name="gemini-1.5-flash",
                model_version="002",
                api_key_env_var="GOOGLE_API_KEY",
                pricing_per_1k_prompt=0.000075,
                pricing_per_1k_completion=0.0003,
                is_mock=False,
            )
        )

    def register_model(self, config: ModelConfig) -> None:
        """Register or override a model configuration."""
        self._models[config.model_id] = config

    def get_model_config(self, model_id: str) -> ModelConfig:
        """Retrieve model configuration by model_id."""
        if model_id not in self._models:
            raise EntityNotFoundError(
                f"Model '{model_id}' is not registered in the ModelRegistry. "
                f"Available models: {sorted(self._models.keys())}"
            )
        return self._models[model_id]

    def has_model(self, model_id: str) -> bool:
        """Check if model_id is registered."""
        return model_id in self._models

    def list_models(self) -> list[ModelConfig]:
        """List all registered models in alphabetical order."""
        return [self._models[k] for k in sorted(self._models.keys())]

    def create_provider(self, model_id: str) -> BaseModelProvider:
        """Instantiate a configured model provider adapter.

        Validates credentials upfront for real providers, failing with clear actionable errors.
        Never silently falls back from a real provider to a mock provider.
        """
        config = self.get_model_config(model_id)

        if config.provider_type == "mock":
            behavior = config.metadata.get("behavior", "valid_contract")
            return MockModelProvider(
                provider_name="mock",
                model_identifier=config.model_name,
                model_version=config.model_version,
                behavior=behavior,
            )

        if config.provider_type == "openai":
            provider = OpenAICompatibleProvider(
                provider_name="openai",
                model_identifier=config.model_name,
                model_version=config.model_version,
                api_key_env_var=config.api_key_env_var,
                base_url=config.base_url,
                default_timeout=config.timeout_seconds,
                max_retries=config.max_retries,
                pricing_per_1k_prompt=config.pricing_per_1k_prompt,
                pricing_per_1k_completion=config.pricing_per_1k_completion,
            )
            # Validate credentials upfront
            if not provider.validate_connection():
                raise ProviderAuthenticationError(
                    f"Authentication verification failed for model '{model_id}'. "
                    f"Ensure environment variable '{config.api_key_env_var}' is set."
                )
            return provider

        if config.provider_type == "google":
            gemini_provider = GoogleGeminiProvider(
                provider_name="google",
                model_identifier=config.model_name,
                model_version=config.model_version,
                api_key_env_var=config.api_key_env_var,
                base_url=config.base_url,
                default_timeout=config.timeout_seconds,
                max_retries=config.max_retries,
                pricing_per_1k_prompt=config.pricing_per_1k_prompt,
                pricing_per_1k_completion=config.pricing_per_1k_completion,
            )
            if not gemini_provider.validate_connection():
                raise ProviderAuthenticationError(
                    f"Authentication verification failed for model '{model_id}'. "
                    f"Ensure environment variable '{config.api_key_env_var}' is set."
                )
            return gemini_provider

        raise ValueError(
            f"Unsupported provider type '{config.provider_type}' for model '{model_id}'."
        )


# Global model registry instance
_global_model_registry = ModelRegistry()


def get_model_registry() -> ModelRegistry:
    """Retrieve global model registry instance."""
    return _global_model_registry
