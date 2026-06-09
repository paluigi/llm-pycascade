# llm-pycascade

**Resilient cascading LLM inference with automatic failover, circuit breaking, and retry cooldowns.**

A faithful Python port of the [llm-cascade](https://github.com/nicholasgasior/llm-cascade) Rust crate.

## Features

- **Cascade inference** — define ordered fallback chains across multiple LLM providers
- **Automatic failover** — if a provider fails, the next in the cascade is tried immediately
- **Circuit breaking / cooldowns** — providers that fail repeatedly are put on exponential backoff
- **Retry-After support** — respects HTTP 429 `Retry-After` headers
- **Failed-prompt persistence** — conversations that exhaust all providers are saved as timestamped JSON
- **Multi-provider** — OpenAI, Anthropic, Google Gemini, and Ollama out of the box
- **OpenAI-compatible** — works with vLLM, LiteLLM, Together AI, and any OpenAI-compatible endpoint
- **Tool/function calling** — first-class support across all providers
- **Async** — built on `httpx` and `aiosqlite` for non-blocking I/O
- **Keyring integration** — optional `keyring` package for secure API key storage

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

## Installation

### pip

```bash
pip install llm-pycascade
```

### uv

```bash
uv add llm-pycascade
```

### With optional keyring support

```bash
pip install llm-pycascade[keyring]
```

## Configuration

Create a TOML config file (defaults to `~/.config/llm-pycascade/config.toml`):

```toml
# config.example.toml — full example configuration

[providers.openai]
type = "openai"
api_key_env = "OPENAI_API_KEY"

[providers.anthropic]
type = "anthropic"
api_key_env = "ANTHROPIC_API_KEY"

[providers.gemini]
type = "gemini"
api_key_env = "GEMINI_API_KEY"

[providers.ollama]
type = "ollama"
# No API key needed for local Ollama

[cascades.primary]
entries = [
    { provider = "openai",    model = "gpt-4o" },
    { provider = "anthropic", model = "claude-sonnet-4-20250514" },
    { provider = "gemini",    model = "gemini-2.0-flash" },
    { provider = "ollama",    model = "llama3.1" },
]

[cascades.fast]
entries = [
    { provider = "anthropic", model = "claude-haiku-4-20250507" },
    { provider = "openai",    model = "gpt-4o-mini" },
    { provider = "ollama",    model = "mistral" },
]

[database]
path = "~/.local/share/llm-pycascade/db.sqlite"

[failure_persistence]
dir = "~/.local/share/llm-pycascade/failed_prompts"
```

## Usage

### Basic cascade

```python
import asyncio
from llm_pycascade import (
    AppConfig,
    Conversation,
    init_db,
    load_config,
    run_cascade,
)

async def main():
    config = load_config()
    db_path = config.database.path.replace("~", "/home/user")
    conn = await init_db(db_path)

    conversation = Conversation.single_user_prompt("Explain quantum computing in one sentence.")

    try:
        response = await run_cascade("primary", conversation, config, conn)
        print(response.text_only())
    finally:
        await conn.close()

asyncio.run(main())
```

### With tools

```python
from llm_pycascade import ContentBlock, Message, ToolDefinition

tools = [
    ToolDefinition(
        name="get_weather",
        description="Get the current weather for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
            },
            "required": ["city"],
        },
    )
]

conversation = Conversation.with_tools(
    messages=[Message.user("What's the weather in Tokyo?")],
    tools=tools,
)

response = await run_cascade("primary", conversation, config, conn)

for block in response.content:
    if block.type == ContentBlockType.TEXT:
        print(f"Text: {block.text}")
    elif block.type == ContentBlockType.TOOL_CALL:
        print(f"Tool call: {block.name}({block.arguments})")
```

### Environment variable override

```bash
export LLM_PYCASCADE_CONFIG=/path/to/custom/config.toml
```

## Key Types

| Type | Module | Description |
|------|--------|-------------|
| `run_cascade()` | `cascade` | Main entry point — runs a named cascade |
| `AppConfig` | `config` | Top-level configuration loaded from TOML |
| `ProviderConfig` | `config` | Per-provider settings (type, API key, base URL) |
| `CascadeConfig` | `config` | Ordered list of provider/model entries |
| `CascadeEntry` | `config` | Single provider/model pair in a cascade |
| `Conversation` | `models` | Multi-turn conversation with optional tools |
| `Message` | `models` | Single message (role + content) |
| `MessageRole` | `models` | Enum: `system`, `user`, `assistant`, `tool` |
| `LlmResponse` | `models` | Provider response with content blocks and usage |
| `ContentBlock` | `models` | Discriminated union: `text` or `tool_call` |
| `ToolDefinition` | `models` | Tool/function schema definition |
| `ProviderError` | `error` | Provider-level failure (HTTP, parse, missing key) |
| `CascadeError` | `error` | All-providers-exhausted failure |

## Cooldown & Backoff

| Failure # | Cooldown Duration | Capped At |
|-----------|-------------------|-----------|
| 1st | 30s | — |
| 2nd | 60s | — |
| 3rd | 120s | — |
| 4th | 240s | — |
| 5th | 480s | — |
| 6th+ | 960s+ | 3600s (1h) |

**Special cases:**

- **HTTP 429 with `Retry-After`**: uses the header value directly instead of exponential backoff
- **Cooldown check**: the entry is silently skipped if still on cooldown
- **Cooldown expiry**: cooldowns are checked against real-time; expired entries are automatically available

## License

MIT — see [LICENSE](LICENSE).
