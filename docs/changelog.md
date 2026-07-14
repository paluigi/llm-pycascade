# Changelog

All notable changes to this project are documented here. For the full release
history, see the [GitHub Releases](https://github.com/paluigi/llm-pycascade/releases)
page.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - Initial release

### Added

- **Cascade inference engine** — ordered fallback chains across multiple LLM
  providers via `run_cascade()`.
- **Automatic failover** — on failure the next cascade entry is tried immediately.
- **Exponential-backoff cooldowns** — providers that fail repeatedly are
  circuit-broken (60s → 120s → 240s → … capped at 1h).
- **Retry-After support** — HTTP 429 `Retry-After` headers are respected.
- **Failed-prompt persistence** — exhausted conversations saved as timestamped JSON.
- **Built-in providers** — OpenAI, Anthropic, Google Gemini, and Ollama.
- **OpenAI-compatible endpoints** — `base_url` override for vLLM, LiteLLM,
  Together AI, and more.
- **Tool/function calling** — first-class support across all providers.
- **Async** — built on `httpx` and `aiosqlite` for non-blocking I/O.
- **Keyring integration** — optional `keyring` extra for secure API key storage.
- **SQLite logging** — attempt log and cooldown tracking via `init_db()`.
- **TOML configuration** — providers, cascades, database, and failure persistence.

[0.1.0]: https://github.com/paluigi/llm-pycascade/releases/tag/v0.1.0
