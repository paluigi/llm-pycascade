"""Cascade engine — resilient multi-provider LLM inference with failover.

The cascade iterates through an ordered list of provider/model entries.
For each entry, it checks whether the combination is on cooldown, attempts
the request, and on failure computes an exponential-backoff cooldown
before moving to the next entry.

If every entry is exhausted, the failed conversation is persisted to disk
and a :class:`CascadeError` is raised.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from llm_pycascade.config import (
    AppConfig,
    CascadeConfig,
    ProviderConfig,
    ProviderType,
    expand_tilde,
)
from llm_pycascade.db import is_on_cooldown, log_attempt, set_cooldown
from llm_pycascade.error import CascadeError, ProviderError
from llm_pycascade.persistence import save_failed_conversation
from llm_pycascade.providers.anthropic import AnthropicProvider
from llm_pycascade.providers.gemini import GeminiProvider
from llm_pycascade.providers.ollama import OllamaProvider
from llm_pycascade.providers.openai import OpenAIProvider

if TYPE_CHECKING:
    import aiosqlite

    from llm_pycascade.models import Conversation, LlmResponse
    from llm_pycascade.providers.base import LlmProvider

logger = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────

BASE_COOLDOWN_SECS: float = 30.0
MAX_COOLDOWN_SECS: float = 3600.0


# ── provider factory ────────────────────────────────────────────────────


def build_provider(
    provider_name: str,
    provider_config: ProviderConfig,
    model: str,
) -> LlmProvider:
    """Instantiate the correct provider class based on the configuration.

    Args:
        provider_name: Logical name of the provider (for error messages).
        provider_config: The provider's configuration block.
        model: Model identifier to use.

    Returns:
        A fully-constructed :class:`LlmProvider` instance.

    Raises:
        ProviderError.missing_api_key: If no API key can be resolved.
        ValueError: If the provider type is unknown.
    """
    from llm_pycascade.secrets import resolve_api_key

    base_url = provider_config.base_url
    api_key_env = provider_config.api_key_env or f"{provider_name.upper()}_API_KEY"
    api_key_service = provider_config.api_key_service or provider_name

    ptype = provider_config.type

    if ptype == ProviderType.OPENAI:
        api_key = resolve_api_key(api_key_service, api_key_env)
        return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)

    if ptype == ProviderType.ANTHROPIC:
        api_key = resolve_api_key(api_key_service, api_key_env)
        return AnthropicProvider(api_key=api_key, model=model, base_url=base_url)

    if ptype == ProviderType.GEMINI:
        api_key = resolve_api_key(api_key_service, api_key_env)
        return GeminiProvider(api_key=api_key, model=model, base_url=base_url)

    if ptype == ProviderType.OLLAMA:
        return OllamaProvider(model=model, base_url=base_url)

    raise ValueError(f"Unknown provider type: {ptype}")


# ── cooldown computation ──────────────────────────────────────────────────


async def compute_cooldown(
    entry_key: str,
    conn: aiosqlite.Connection,
) -> timedelta:
    """Compute the cooldown duration based on recent failure history.

    Uses exponential backoff:

    * 1st failure  → ``BASE_COOLDOWN_SECS``
    * 2nd failure  → ``2 × BASE_COOLDOWN_SECS``
    * 3rd failure  → ``4 × BASE_COOLDOWN_SECS``
    * …capped at ``MAX_COOLDOWN_SECS``

    Args:
        entry_key: ``provider/model`` identifier.
        conn: Open database connection for querying failure history.

    Returns:
        The computed cooldown duration.
    """
    # Count recent failures within the last hour for this entry
    one_hour_ago = time.time() - 3600.0
    cursor = await conn.execute(
        "SELECT COUNT(*) FROM attempt_log "
        "WHERE provider_model = ? AND http_status IS NOT NULL AND timestamp > ?",
        (entry_key, datetime.fromtimestamp(one_hour_ago, tz=timezone.utc).isoformat()),
    )
    row = await cursor.fetchone()
    failure_count = row[0] if row else 0

    # Exponential backoff: 2^n * BASE_COOLDOWN_SECS, capped

    cooldown_secs = min(
        (2**failure_count) * BASE_COOLDOWN_SECS,
        MAX_COOLDOWN_SECS,
    )
    return timedelta(seconds=cooldown_secs)


# ── main cascade function ──────────────────────────────────────────────


async def run_cascade(
    cascade_name: str,
    conversation: Conversation,
    config: AppConfig,
    conn: aiosqlite.Connection,
) -> LlmResponse:
    """Run the named cascade against *conversation*.

    Iterates through the cascade's entries in order:

    1. Check if the entry is on cooldown → skip if so.
    2. Build the provider and send the request.
    3. On success: log the attempt and return the response.
    4. On failure: log the attempt, compute & set a cooldown, and continue
       to the next entry.
    5. If all entries are exhausted: persist the failed conversation to disk
       and raise :class:`CascadeError`.

    Args:
        cascade_name: Name of the cascade (must exist in ``config.cascades``).
        conversation: The conversation to send.
        config: The full application configuration.
        conn: Open database connection for logging and cooldown queries.

    Returns:
        The first successful :class:`LlmResponse`.

    Raises:
        CascadeError: If every provider in the cascade fails.
        KeyError: If the cascade name is not found in the configuration.
    """
    if cascade_name not in config.cascades:
        raise KeyError(f"Cascade '{cascade_name}' not found in configuration")

    cascade_config: CascadeConfig = config.cascades[cascade_name]
    errors: list[tuple[str, ProviderError]] = []

    for entry in cascade_config.entries:
        provider_model_key = f"{entry.provider}/{entry.model}"

        # 1. Check cooldown
        if await is_on_cooldown(conn, provider_model_key):
            logger.info(
                "Skipping %s — on cooldown",
                provider_model_key,
            )
            continue

        # 2. Build provider
        provider_cfg = config.providers.get(entry.provider)
        if provider_cfg is None:
            logger.warning(
                "Provider '%s' not in config, skipping entry %s",
                entry.provider,
                provider_model_key,
            )
            continue

        try:
            provider = build_provider(entry.provider, provider_cfg, entry.model)
        except (ProviderError, ValueError) as exc:
            logger.error(
                "Failed to build provider for %s: %s",
                provider_model_key,
                exc,
            )
            errors.append(
                (
                    provider_model_key,
                    exc
                    if isinstance(exc, ProviderError)
                    else ProviderError.other(str(exc)),
                )
            )
            continue

        # 3. Send request
        start = time.monotonic()
        try:
            response = await provider.complete(conversation)
        except ProviderError as exc:
            latency_ms = int((time.monotonic() - start) * 1000)

            # 4. Log failure and set cooldown
            logger.warning(
                "Provider %s failed: %s",
                provider_model_key,
                exc,
            )
            await log_attempt(
                conn,
                cascade_name=cascade_name,
                provider_model=provider_model_key,
                http_status=exc.http_status,
                latency_ms=latency_ms,
                input_tokens=0,
                output_tokens=0,
            )

            # Compute cooldown (respect Retry-After if available)
            if exc.retry_after_seconds is not None:
                cooldown_duration = timedelta(seconds=exc.retry_after_seconds)
            else:
                cooldown_duration = await compute_cooldown(provider_model_key, conn)

            cooldown_until = time.time() + cooldown_duration.total_seconds()
            await set_cooldown(conn, provider_model_key, cooldown_until)

            logger.info(
                "Cooldown set for %s until %s",
                provider_model_key,
                datetime.fromtimestamp(cooldown_until, tz=timezone.utc).isoformat(),
            )

            errors.append((provider_model_key, exc))
            continue

        latency_ms = int((time.monotonic() - start) * 1000)

        # 5. Success — log and return
        await log_attempt(
            conn,
            cascade_name=cascade_name,
            provider_model=provider_model_key,
            http_status=None,
            latency_ms=latency_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        logger.info(
            "Cascade '%s' succeeded via %s (%dms)",
            cascade_name,
            provider_model_key,
            latency_ms,
        )
        return response

    # 6. All entries exhausted — persist and raise
    failure_dir = expand_tilde(config.failure_persistence.dir)
    failed_path = save_failed_conversation(conversation, failure_dir, cascade_name)

    error_summary = "; ".join(f"{k}: {v}" for k, v in errors)
    raise CascadeError(
        cascade_name=cascade_name,
        message=f"All providers failed. {error_summary}",
        failed_prompt_path=failed_path,
    )
