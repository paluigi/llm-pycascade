# How it works

The cascade engine is the heart of `llm-pycascade`. It provides resilient,
ordered multi-provider inference with automatic failover and circuit breaking.

## Architecture

```
┌──────────────┐     ┌──────────────────────────────────────────┐
│   User Code  │────▶│              run_cascade()               │
└──────────────┘     │                                          │
                     │  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
                     │  │ Entry 1 │─▶│ Entry 2 │─▶│ Entry 3 │  │
                     │  │OpenAI   │  │Anthropic│  │ Gemini  │  │
                     │  │gpt-4o   │  │claude.. │  │gemini.. │  │
                     │  └─────────┘  └─────────┘  └─────────┘  │
                     │       ▼            ▼            ▼        │
                     │  ┌─────────────────────────────────────┐ │
                     │  │        Cooldown Tracker (SQLite)     │ │
                     │  │  ┌───────────────────────────────┐  │ │
                     │  │  │ is_on_cooldown() / set_cooldown│  │ │
                     │  │  └───────────────────────────────┘  │ │
                     │  └─────────────────────────────────────┘ │
                     │       ▼            ▼            ▼        │
                     │  ┌─────────────────────────────────────┐ │
                     │  │      Attempt Log (SQLite)            │ │
                     │  │  ┌───────────────────────────────┐  │ │
                     │  │  │ log_attempt(status, latency,  │  │ │
                     │  │  │             tokens)           │  │ │
                     │  │  └───────────────────────────────┘  │ │
                     │  └─────────────────────────────────────┘ │
                     │       ▼ (all failed)                     │
                     │  ┌─────────────────────────────────────┐ │
                     │  │  save_failed_conversation() → JSON   │ │
                     │  └─────────────────────────────────────┘ │
                     └──────────────────────────────────────────┘
```

## Cascade execution

For each entry in the cascade, `run_cascade()` performs these steps:

1. **Cooldown check** — if the entry (`provider/model`) is on cooldown, skip it.
2. **Build provider** — instantiate the provider and resolve its API key.
3. **Send request** — call `provider.complete(conversation)`.
4. **On success** — log the attempt (status, latency, tokens) and return the response.
5. **On failure** — log the attempt, compute & set a cooldown, then continue to the next entry.
6. **All exhausted** — persist the failed conversation to disk and raise `CascadeError`.

## Cooldown and backoff

When a provider fails, it is put on an exponential-backoff cooldown based on
its failure count within the last hour:

| Failure # | Cooldown Duration | Capped At |
|-----------|-------------------|-----------|
| 1st | 60s | — |
| 2nd | 120s | — |
| 3rd | 240s | — |
| 4th | 480s | — |
| 5th | 960s | — |
| 6th+ | 1920s+ | 3600s (1h) |

### Special cases

- **HTTP 429 with `Retry-After`**: the header value (in seconds) is used directly
  instead of the computed exponential backoff.
- **Cooldown check**: an entry on cooldown is **silently skipped** — the cascade
  moves on without consuming a request.
- **Cooldown expiry**: cooldowns are checked against real-time; expired entries
  automatically become available again.

## SQLite tables

Two tables back the engine, created automatically by `init_db()`:

### `attempt_log`

Every attempt — successful or failed — is recorded here.

| Column | Description |
|--------|-------------|
| `timestamp` | When the attempt was made |
| `cascade_name` | Which cascade was running |
| `provider_model` | `provider/model` identifier |
| `http_status` | HTTP status code (`NULL` if not HTTP-related) |
| `latency_ms` | Round-trip latency in milliseconds |
| `input_tokens` | Input tokens reported by the provider |
| `output_tokens` | Output tokens reported by the provider |

### `cooldown`

Tracks the cooldown expiry for each `provider/model` combination.

| Column | Description |
|--------|-------------|
| `provider_model` | `provider/model` identifier (primary key) |
| `cooldown_until` | Unix timestamp when the cooldown expires |

## Failed-prompt persistence

When every entry in a cascade fails, the conversation is saved to disk as a
timestamped JSON file before `CascadeError` is raised:

```
<failure_persistence.dir>/<cascade_name>/<timestamp>.json
```

Each file contains the cascade name, a save timestamp, the full message list,
and any tool definitions. This lets you inspect, retry, or debug failed prompts
after the fact.
