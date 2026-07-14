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
| `base_url` | Override the provider's default API URL | No |

[^1]: Ollama needs no API key. For the others, if `api_key_env` is omitted it
defaults to `<PROVIDER>_API_KEY` (uppercased provider name).

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
