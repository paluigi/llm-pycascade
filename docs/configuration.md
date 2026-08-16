# Configuration

`llm-pycascade` is configured entirely via a TOML file. The loader searches
these locations, in order, and uses the first match:

1. The path in the `LLM_PYCASCADE_CONFIG` environment variable
2. `~/.config/llm-pycascade/config.toml`
3. `~/.llm-pycascade.toml` (legacy fallback)

You can also pass an explicit path to `load_config()`:

```python
from llm_pycascade import load_config

config = load_config("/path/to/my-config.toml")
```

## Dict-based configuration

If writing a TOML file is not possible — serverless functions, containers,
ephemeral CI runners — configure the cascade entirely in code with
[`config_from_dict`](reference/config.md):

```python
from llm_pycascade import config_from_dict

config = config_from_dict({
    "providers": {
        "openai": {
            "type": "openai",
            "api_key": "OPENAI_API_KEY",       # env var name (default)
            # "api_key": "sk-...",             # actual key
            # "api_key_literal": True,         # ← marks api_key as the key itself
        },
        "ollama": {"type": "ollama"},
    },
    "cascades": {
        "primary": {
            "entries": [
                {"provider": "openai", "model": "gpt-4o"},
                {"provider": "ollama", "model": "llama3.1"},
            ]
        }
    },
})
```

The dictionary uses **exactly the same schema** as the parsed TOML file:
anything `tomllib` produces from a valid `config.toml` is accepted, and
missing sections fall back to the same defaults. Both loaders share one
parsing core, so TOML and dict configurations behave identically —
including validation errors (`pydantic.ValidationError` for malformed
sections).

On stateless machines, also point the database at an in-memory SQLite
and the failure-persistence dir at a writable path (or `/tmp`):

```python
config = config_from_dict({
    ...,
    "database": {"path": ":memory:"},
    "failure_persistence": {"dir": "/tmp/llm-pycascade/failed_prompts"},
})
```

## Full example

The complete, commented configuration is maintained in
[`config.example.toml`](https://github.com/paluigi/llm-pycascade/blob/main/config.example.toml)
and is included verbatim below:

```toml
--8<-- "config.example.toml"
```

## Sections

### `[providers.<name>]`

Each key under `[providers]` defines a named provider.

| Field | Description | Required |
|-------|-------------|----------|
| `type` | One of `openai`, `anthropic`, `gemini`, `ollama` | Yes |
| `api_key_env` | Environment variable holding the API key | No[^1] |
| `api_key_service` | Keyring service name override | No |
| `api_key` | API key field — actual key if `api_key_literal` is true, else env var name | No[^1] |
| `api_key_literal` | `true` → `api_key` holds the actual key; `false` (default) → `api_key` names an env var | No |
| `base_url` | Override the provider's default API URL | No |

[^1]: Ollama needs no API key. For the others, if neither `api_key_env` nor
`api_key` is set it defaults to the `<PROVIDER>_API_KEY` environment
variable (uppercased provider name). When both are given, `api_key_env`
takes precedence over a non-literal `api_key`.

### `[cascades.<name>]`

Each key under `[cascades]` defines a named cascade — an ordered list of
provider/model entries tried in sequence.

```toml
[cascades.primary]
entries = [
    { provider = "openai", model = "gpt-4o" },
    { provider = "ollama", model = "llama3.1" },
]
```

| Field | Description |
|-------|-------------|
| `provider` | Key name matching a `[providers.*]` entry |
| `model` | Model identifier to use for this entry |

### `[database]`

| Field | Default | Description |
|-------|---------|-------------|
| `path` | `~/.local/share/llm-pycascade/db.sqlite` | SQLite database for the attempt log and cooldown table |

### `[failure_persistence]`

| Field | Default | Description |
|-------|---------|-------------|
| `dir` | `~/.local/share/llm-pycascade/failed_prompts` | Directory where failed conversations are saved as timestamped JSON |

## Environment variable override

Point `llm-pycascade` at any config file without touching the filesystem defaults:

```bash
export LLM_PYCASCADE_CONFIG=/path/to/custom/config.toml
```
