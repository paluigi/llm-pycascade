"""Async SQLite database for attempt logging and cooldown tracking."""

from __future__ import annotations

import time

import aiosqlite

_CREATE_ATTEMPT_LOG = """
CREATE TABLE IF NOT EXISTS attempt_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now')),
    cascade_name    TEXT NOT NULL,
    provider_model  TEXT NOT NULL,
    http_status     INTEGER,
    latency_ms      INTEGER,
    input_tokens    INTEGER,
    output_tokens   INTEGER
);
"""

_CREATE_COOLDOWN = """
CREATE TABLE IF NOT EXISTS cooldown (
    provider_model  TEXT PRIMARY KEY,
    cooldown_until  REAL NOT NULL
);
"""


async def init_db(path: str) -> aiosqlite.Connection:
    """Open (or create) the SQLite database and ensure tables exist.

    Args:
        path: Filesystem path to the SQLite database file.

    Returns:
        An open :class:`aiosqlite.Connection`.
    """
    conn = await aiosqlite.connect(path)
    await conn.execute(_CREATE_ATTEMPT_LOG)
    await conn.execute(_CREATE_COOLDOWN)
    await conn.commit()
    return conn


async def log_attempt(
    conn: aiosqlite.Connection,
    cascade_name: str,
    provider_model: str,
    http_status: int | None,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Insert a row into the attempt log.

    Args:
        conn: Open database connection.
        cascade_name: Name of the cascade that was running.
        provider_model: ``provider/model`` identifier string.
        http_status: HTTP status code (``None`` if not HTTP-related).
        latency_ms: Round-trip latency in milliseconds.
        input_tokens: Input tokens reported by the provider.
        output_tokens: Output tokens reported by the provider.
    """
    await conn.execute(
        "INSERT INTO attempt_log "
        "(cascade_name, provider_model, http_status, latency_ms, "
        "input_tokens, output_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            cascade_name,
            provider_model,
            http_status,
            latency_ms,
            input_tokens,
            output_tokens,
        ),
    )
    await conn.commit()


async def is_on_cooldown(conn: aiosqlite.Connection, provider_model: str) -> bool:
    """Check whether a provider/model combination is currently in cooldown.

    Args:
        conn: Open database connection.
        provider_model: ``provider/model`` identifier string.

    Returns:
        ``True`` if the entry has an active cooldown.
    """
    cursor = await conn.execute(
        "SELECT cooldown_until FROM cooldown WHERE provider_model = ?",
        (provider_model,),
    )
    row = await cursor.fetchone()
    if row is None:
        return False
    cooldown_until = row[0]
    return time.time() < cooldown_until


async def set_cooldown(
    conn: aiosqlite.Connection,
    provider_model: str,
    cooldown_until: float,
) -> None:
    """Set (or update) the cooldown for a provider/model combination.

    Uses ``INSERT OR REPLACE`` so repeated cooldowns simply update the expiry.

    Args:
        conn: Open database connection.
        provider_model: ``provider/model`` identifier string.
        cooldown_until: Unix timestamp (seconds since epoch) when the cooldown expires.
    """
    await conn.execute(
        "INSERT OR REPLACE INTO cooldown "
        "(provider_model, cooldown_until) VALUES (?, ?)",
        (provider_model, cooldown_until),
    )
    await conn.commit()
