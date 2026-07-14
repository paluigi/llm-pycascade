# Quickstart

This guide walks through a minimal, runnable cascade from configuration to a
successful response.

## 1. Configure providers & a cascade

Create a TOML config file. By default `llm-pycascade` looks for:

1. The `LLM_PYCASCADE_CONFIG` environment variable
2. `~/.config/llm-pycascade/config.toml`
3. `~/.llm-pycascade.toml` (legacy)

A minimal example:

```toml
[providers.openai]
type = "openai"
api_key_env = "OPENAI_API_KEY"

[providers.ollama]
type = "ollama"

[cascades.primary]
entries = [
    { provider = "openai", model = "gpt-4o" },
    { provider = "ollama", model = "llama3.1" },
]
```

See [Configuration](configuration.md) for the full schema.

## 2. Set your API key

```bash
export OPENAI_API_KEY="sk-..."
```

## 3. Run the cascade

```python
import asyncio

from llm_pycascade import (
    Conversation,
    init_db,
    load_config,
    run_cascade,
)
from llm_pycascade.config import expand_tilde


async def main() -> None:
    config = load_config()

    # Open the SQLite database used for logging & cooldowns
    conn = await init_db(expand_tilde(config.database.path))

    conversation = Conversation.single_user_prompt(
        "Explain quantum computing in one sentence."
    )

    try:
        response = await run_cascade("primary", conversation, config, conn)
        print(response.text_only())
    finally:
        await conn.close()


asyncio.run(main())
```

If `openai/gpt-4o` succeeds, you get its response immediately. If it fails
(e.g. rate limited), the cascade automatically tries `ollama/llama3.1`.

## What just happened?

1. `load_config()` read your TOML file into an [`AppConfig`](reference/config.md).
2. `init_db()` opened (or created) the SQLite database for attempt logging and cooldowns.
3. `run_cascade()` iterated the `primary` cascade entries in order until one succeeded.
4. On any failure, the provider was put on a [cooldown](concepts.md#cooldown-and-backoff) and the next entry was tried.

## Next

- Add more cascades and models in [Configuration](configuration.md).
- Expose tools to the model in [Tools & function calling](tools.md).
- Handle failures gracefully in [Error handling](error-handling.md).
