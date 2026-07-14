"""Tests for the full cascade flow."""

import pytest

from llm_pycascade.cascade import run_cascade
from llm_pycascade.config import (
    AppConfig,
    CascadeConfig,
    CascadeEntry,
    DatabaseConfig,
    FailureConfig,
    ProviderConfig,
    ProviderType,
)
from llm_pycascade.error import CascadeError
from llm_pycascade.models.conversation import Conversation


@pytest.fixture
def config(tmp_path):
    """Minimal config for testing."""
    return AppConfig(
        providers={
            "openai": ProviderConfig(
                type=ProviderType.OPENAI,
                api_key_env="TEST_OPENAI_KEY",
            ),
            "anthropic": ProviderConfig(
                type=ProviderType.ANTHROPIC,
                api_key_env="TEST_ANTHROPIC_KEY",
            ),
        },
        cascades={
            "primary": CascadeConfig(
                entries=[
                    CascadeEntry(provider="openai", model="gpt-4o"),
                    CascadeEntry(
                        provider="anthropic",
                        model="claude-sonnet-4-20250514",
                    ),
                ]
            ),
        },
        database=DatabaseConfig(path=str(tmp_path / "test.db")),
        failure_persistence=FailureConfig(dir=str(tmp_path / "failed")),
    )


@pytest.fixture
async def db_conn(tmp_path):
    """Create a temporary SQLite database."""
    db_path = str(tmp_path / "test.db")
    from llm_pycascade.db import init_db

    conn = await init_db(db_path)
    yield conn
    await conn.close()


@pytest.mark.asyncio
class TestCascadeBasics:
    """Smoke tests that don't require real API calls."""

    async def test_unknown_cascade_raises_keyerror(self, config, db_conn):
        conv = Conversation.single_user_prompt("test")
        with pytest.raises(KeyError):
            await run_cascade("nonexistent", conv, config, db_conn)

    async def test_missing_api_key_skipped(self, config, db_conn, monkeypatch):
        """Entries with missing API keys should be skipped, not crash."""
        # Ensure no API keys are set
        monkeypatch.delenv("TEST_OPENAI_KEY", raising=False)
        monkeypatch.delenv("TEST_ANTHROPIC_KEY", raising=False)

        conv = Conversation.single_user_prompt("test")
        with pytest.raises(CascadeError) as exc_info:
            await run_cascade("primary", conv, config, db_conn)

        # All entries should have failed
        assert "failed" in str(exc_info.value).lower()
