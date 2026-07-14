# Secrets & keyring

`llm-pycascade` resolves API keys through a layered lookup so you can store
secrets either in environment variables or, optionally, in the OS keyring.

## Resolution order

When a provider is built, [`resolve_api_key`](reference/secrets.md) checks
sources in this order:

1. **System keyring** — if the `keyring` package is installed *and* a key
   exists for the service.
2. **Environment variable** — the variable named by `api_key_env`.

If neither yields a key, a `ProviderError` (missing API key variant) is raised
and the cascade moves to the next entry.

## Using environment variables

This is the zero-dependency default. Set the variable named in your config's
`api_key_env` field:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AIza..."
```

If `api_key_env` is omitted, it defaults to `<PROVIDER_NAME>_API_KEY`
(uppercased provider name).

## Using the keyring (optional)

Install the extra to enable OS-backed secure storage:

```bash
pip install llm-pycascade[keyring]
```

Then store keys programmatically:

```python
from llm_pycascade.secrets import set_key

set_key("openai", "sk-...")
set_key("anthropic", "sk-ant-...")
```

Keys are stored under the qualified service name
`llm-pycascade/<provider>`, e.g. `llm-pycascade/openai`.

### Keyring helper functions

| Function | Description |
|----------|-------------|
| `set_key(service, key)` | Store a key in the keyring |
| `get_key(service)` | Retrieve a key (returns `None` if absent) |
| `has_key(service)` | Check whether a key exists |
| `delete_key(service)` | Remove a key |
| `mask_key(key)` | Return a masked representation for safe display |

### Masking keys for logging

Never log raw API keys. Use `mask_key()` to show only the first and last
characters:

```python
from llm_pycascade.secrets import mask_key

print(mask_key("sk-abcdef1234567890"))  # sk-a...7890
```

## Overriding the keyring service name

By default the keyring service name matches the provider key (e.g. `openai`).
Override it per-provider with `api_key_service`:

```toml
[providers.openai]
type = "openai"
api_key_service = "my-company-openai"
api_key_env = "OPENAI_API_KEY"
```
