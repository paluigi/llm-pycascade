# Providers

`llm-pycascade` ships with four built-in providers and an extensible base
class for adding your own.

## Built-in providers

| Provider | Type | API key required | Default base URL |
|----------|------|------------------|------------------|
| OpenAI | `openai` | Yes | `https://api.openai.com/v1` |
| Anthropic | `anthropic` | Yes | `https://api.anthropic.com` |
| Google Gemini | `gemini` | Yes | `https://generativelanguage.googleapis.com` |
| Ollama | `ollama` | No | `http://localhost:11434` |

## Configuration

Each provider is defined under `[providers.<name>]`:

```toml
[providers.openai]
type = "openai"
api_key_env = "OPENAI_API_KEY"
base_url = "https://api.openai.com/v1"   # optional, shown with default
```

| Field | Description |
|-------|-------------|
| `type` | Provider type: `openai`, `anthropic`, `gemini`, or `ollama` |
| `api_key_env` | Environment variable holding the key (defaults to `<NAME>_API_KEY`) |
| `api_key_service` | Keyring service name override (defaults to the provider name) |
| `base_url` | Override the default API URL |

See [Secrets & keyring](secrets.md) for how API keys are resolved.

## OpenAI-compatible endpoints

Because the OpenAI provider uses the standard Chat Completions API, you can
point `base_url` at any compatible endpoint:

=== "vLLM"

    ```toml
    [providers.vllm]
    type = "openai"
    api_key_env = "VLLM_API_KEY"
    base_url = "http://localhost:8000/v1"
    ```

=== "LiteLLM"

    ```toml
    [providers.litellm]
    type = "openai"
    api_key_env = "LITELLM_API_KEY"
    base_url = "http://localhost:4000/v1"
    ```

=== "Together AI"

    ```toml
    [providers.together]
    type = "openai"
    api_key_env = "TOGETHER_API_KEY"
    base_url = "https://api.together.xyz/v1"
    ```

Then reference the provider in any cascade entry:

```toml
[cascades.local]
entries = [
    { provider = "vllm", model = "meta-llama/Llama-3.1-70B-Instruct" },
]
```

## Reusing a provider across models

A single provider definition can back multiple cascade entries with different
models — cooldowns are tracked per `provider/model` pair:

```toml
[cascades.flexible]
entries = [
    { provider = "openai", model = "gpt-4o" },
    { provider = "openai", model = "gpt-4o-mini" },
]
```

## Custom providers

All built-in providers implement the abstract [`LlmProvider`](reference/providers.md)
base class. To add your own, subclass it and implement `complete()`,
`provider_name`, and `model_name`:

```python
from llm_pycascade.models import Conversation, LlmResponse
from llm_pycascade.providers.base import LlmProvider


class MyProvider(LlmProvider):
    def __init__(self, model: str) -> None:
        self._model = model

    @property
    def provider_name(self) -> str:
        return "mine"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(self, conversation: Conversation) -> LlmResponse:
        # ... your API call here ...
        ...
```

See the [API reference](reference/providers.md) for the full base class
contract and the built-in implementations.
