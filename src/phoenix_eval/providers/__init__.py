"""Model provider interfaces, adapters, and registry for PHOENIX-EVAL."""

from phoenix_eval.providers.base import (
    BaseModelProvider,
    MockModelProvider,
    ProviderPromptRequest,
)
from phoenix_eval.providers.gemini_provider import GoogleGeminiProvider
from phoenix_eval.providers.model_registry import (
    ModelConfig,
    ModelRegistry,
    get_model_registry,
)
from phoenix_eval.providers.openai_provider import OpenAICompatibleProvider

__all__ = [
    "BaseModelProvider",
    "MockModelProvider",
    "OpenAICompatibleProvider",
    "GoogleGeminiProvider",
    "ProviderPromptRequest",
    "ModelConfig",
    "ModelRegistry",
    "get_model_registry",
]
