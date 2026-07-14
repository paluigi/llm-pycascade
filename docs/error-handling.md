# Error handling

`llm-pycascade` uses two exception types to model failures at different
levels of the cascade.

## ProviderError

A [`ProviderError`](reference/error.md) represents a failure from a single
LLM provider. It mirrors a tagged enum with five variants, each built via a
dedicated classmethod:

| Variant | Constructor | Meaning |
|---------|-------------|---------|
| `http` | `ProviderError.http(status, body, retry_after=None)` | HTTP-level failure with a status code |
| `request` | `ProviderError.request(message)` | Problem building or sending the request |
| `parse` | `ProviderError.parse(message)` | Could not parse the provider response |
| `missing_api_key` | `ProviderError.missing_api_key(provider, env_var=None)` | No API key found |
| `other` | `ProviderError.other(message)` | Unclassified error |

Each instance exposes these convenience properties:

| Property | Description |
|----------|-------------|
| `variant` | The tag string (`"http"`, `"request"`, …) |
| `http_status` | HTTP status code, or `None` if not an HTTP error |
| `retry_after_seconds` | `Retry-After` value in seconds, or `None` |
| `message` | Human-readable error message |

### Retry-After handling

When a provider returns an HTTP 429 with a `Retry-After` header, the resulting
`ProviderError.http(...)` carries `retry_after`. The cascade uses this value
directly for the cooldown instead of the computed exponential backoff.

```python
from llm_pycascade import ProviderError

err = ProviderError.http(429, "rate limited", retry_after=60)
print(err.retry_after_seconds)  # 60
print(err.http_status)          # 429
```

## CascadeError

A [`CascadeError`](reference/error.md) is raised only when **every** entry
in a cascade has been exhausted. It carries the context needed to inspect the
total failure:

| Attribute | Description |
|-----------|-------------|
| `cascade_name` | Name of the cascade that failed |
| `failed_prompt_path` | Path to the saved failed-conversation JSON, or `None` |

```python
from llm_pycascade import CascadeError, Conversation, run_cascade

try:
    response = await run_cascade("primary", conversation, config, conn)
except CascadeError as exc:
    print(f"Cascade '{exc.cascade_name}' failed.")
    if exc.failed_prompt_path:
        print(f"Failed conversation saved to: {exc.failed_prompt_path}")
```

## Failed-prompt persistence

Before raising `CascadeError`, the engine saves the conversation to disk as a
timestamped JSON file:

```
<failure_persistence.dir>/<cascade_name>/<timestamp>.json
```

The file contains:

- `cascade_name` — which cascade ran
- `saved_at` — ISO timestamp
- `messages` — the full message list
- `tools` — any tool definitions (if present)

This lets you inspect, replay, or debug prompts that exhausted all providers.
See [`save_failed_conversation`](reference/persistence.md) in the API
reference.
