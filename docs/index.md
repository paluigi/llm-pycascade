# llm-pycascade

**Resilient cascading LLM inference with automatic failover, circuit breaking, and retry cooldowns.**

A faithful Python port of the [llm-cascade](https://github.com/nicholasgasior/llm-cascade) Rust crate.

## Why?

Production LLM applications break when a single provider goes down.
`llm-pycascade` lets you define an ordered fallback chain across multiple
providers so that a failure on one transparently falls through to the next —
all while protecting each provider with exponential-backoff cooldowns.

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

## Next steps

- :material-download: [Install](installation.md) the package
- :material-rocket-launch: Run the [Quickstart](quickstart.md)
- :material-cog: Configure providers and cascades in [Configuration](configuration.md)
- :material-lightbulb: Understand the engine in [How it works](concepts.md)
- :material-code-braces: Browse the full [API Reference](reference/cascade.md)
