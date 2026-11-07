# PHOENIX-EVAL: Model Provider Adapters & Credential Security Guide

## 1. Provider Architecture

PHOENIX-EVAL abstracts model access through `BaseModelProvider` and the `ModelRegistry`. This ensures that benchmark task generation, prompt construction, and deterministic evaluation remain completely decoupled from specific LLM vendors.

Supported Provider Types:
1. **Mock Provider (`MockModelProvider`):** Deterministic, in-memory simulated responses requiring zero API keys, network calls, or costs.
2. **OpenAI-Compatible Provider (`OpenAICompatibleProvider`):** Connects to OpenAI or any endpoint supporting the standard OpenAI Chat Completions API specification (e.g. vLLM, Ollama, Groq, Together AI, DeepSeek, LocalAI).
3. **Google Gemini Provider (`GoogleGeminiProvider`):** Connects directly to Google's official Generative Language REST endpoints (`gemini-1.5-pro`, `gemini-1.5-flash`, etc.).

---

## 2. Mock Provider (Mode A)

The mock provider enables complete, zero-cost end-to-end testing of the entire benchmark engine:

```python
from phoenix_eval.providers.base import MockModelProvider

provider = MockModelProvider(
    provider_name="mock",
    model_identifier="mock-model-v1",
    behavior="valid_contract",  # "valid_contract", "refusal", "adversarial_unsafe"
)
```

### Configured Mock Behaviors:
- `valid_contract`: Generates a syntactically valid JSON response contract with preparation actions.
- `refusal`: Generates a safe refusal declaring `MIGRATION_BLOCKED` due to detected blockers.
- `adversarial_unsafe`: Generates an unsafe cutover plan referencing unverified external components.

Mock runs always set `metadata={"mock": True, "simulated": True}` and are strictly distinguishable from real model runs in aggregate reporting.

---

## 3. Real Model Providers (Mode B)

### OpenAI-Compatible Provider Setup
Configure via environment variables or model registry entries:

```bash
# In your terminal or deployment environment:
export OPENAI_API_KEY="sk-proj-your-openai-api-key-here"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # Optional, default is official OpenAI
```

The adapter supports custom base URLs for open-weights hosting:
```yaml
# For local vLLM or Ollama:
base_url: "http://localhost:8000/v1"
api_key_env_var: "VLLM_API_KEY"
```

### Google Gemini Provider Setup
Configure via environment variable:

```bash
export GOOGLE_API_KEY="AIzaSyYourGoogleApiKeyHere"
```

The adapter calls Google Generative Language REST endpoints using the `x-goog-api-key` header to ensure keys never appear in URL query strings or network proxy logs.

---

## 4. Credential & Security Invariants

PHOENIX-EVAL enforces strict security controls:

1. **Zero Hardcoded Secrets:**
   API keys are never stored in source code, configuration files, or model registries. Model configurations only reference the **name of the environment variable** (e.g. `"OPENAI_API_KEY"`).
2. **Pre-Flight Validation:**
   Before commencing an experiment, `ExperimentValidator` verifies that all required environment variables are set and non-empty. If a key is missing, the run halts immediately with a clear, actionable error.
3. **No Silent Fallback:**
   The runner **never** silently falls back from a real provider to a mock provider upon an authentication or network failure.
4. **Credential Scrubbing:**
   All logs, exception messages, experiment manifests, evaluation reports, and exported CSV files pass through `sanitize_text()`, `sanitize_dict()`, and `redact_url()`. Authentication headers (`Authorization: Bearer [REDACTED]`, `x-goog-api-key: [REDACTED]`) are masked prior to logging.

---

## 5. Transient Error Handling & Retries

The provider adapters implement bounded exponential backoff with jitter for transient errors:
- **HTTP 429 (Rate Limit):** Backs off exponentially ($T_{\text{delay}} \times 2^{\text{attempt}-1}$) and retries up to `max_retries`.
- **HTTP 5xx (Server Error):** Retried with backoff.
- **Network / Timeout Errors:** Retried with backoff.
- **HTTP 401 / 403 (Authentication):** Fails immediately without retries.
- **HTTP 400 (Bad Request):** Fails immediately without retries.
