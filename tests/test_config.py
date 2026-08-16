"""Tests for dict-based configuration and API key resolution."""

from pathlib import Path

import pytest
import tomllib
from pydantic import SecretStr, ValidationError

from llm_pycascade.cascade import build_provider
from llm_pycascade.config import (
    AppConfig,
    ProviderConfig,
    ProviderType,
    config_from_dict,
    load_config,
)
from llm_pycascade.providers.anthropic import AnthropicProvider
from llm_pycascade.providers.gemini import GeminiProvider
from llm_pycascade.providers.openai import OpenAIProvider

REPO_ROOT = Path(__file__).resolve().parent.parent

FULL_DICT = {
    "providers": {
        "openai": {"type": "openai", "api_key_env": "OPENAI_API_KEY"},
        "ollama": {"type": "ollama"},
    },
    "cascades": {
        "primary": {
            "entries": [
                {"provider": "openai", "model": "gpt-4o"},
                {"provider": "ollama", "model": "llama3.1"},
            ]
        }
    },
    "database": {"path": "/tmp/custom/db.sqlite"},
    "failure_persistence": {"dir": "/tmp/custom/failed"},
}


class TestConfigFromDict:
    def test_full_dict(self):
        config = config_from_dict(FULL_DICT)

        assert isinstance(config, AppConfig)
        assert set(config.providers) == {"openai", "ollama"}
        assert config.providers["openai"].type is ProviderType.OPENAI
        assert config.providers["openai"].api_key_env == "OPENAI_API_KEY"
        assert config.providers["ollama"].type is ProviderType.OLLAMA

        assert set(config.cascades) == {"primary"}
        entries = config.cascades["primary"].entries
        assert [e.provider for e in entries] == ["openai", "ollama"]
        assert [e.model for e in entries] == ["gpt-4o", "llama3.1"]

        assert config.database.path == "/tmp/custom/db.sqlite"
        assert config.failure_persistence.dir == "/tmp/custom/failed"

    def test_empty_dict_gives_defaults(self):
        config = config_from_dict({})

        assert config.providers == {}
        assert config.cascades == {}
        assert config.database.path == "~/.local/share/llm-pycascade/db.sqlite"
        assert (
            config.failure_persistence.dir
            == "~/.local/share/llm-pycascade/failed_prompts"
        )

    def test_partial_dict_missing_optional_sections(self):
        config = config_from_dict({"providers": {"ollama": {"type": "ollama"}}})

        assert set(config.providers) == {"ollama"}
        assert config.cascades == {}

    def test_invalid_provider_type_raises(self):
        with pytest.raises(ValidationError):
            config_from_dict({"providers": {"bogus": {"type": "not-a-provider"}}})

    def test_cascade_entry_missing_field_raises(self):
        with pytest.raises(ValidationError):
            config_from_dict(
                {"cascades": {"bad": {"entries": [{"provider": "openai"}]}}}  # no model
            )

    def test_unknown_top_level_keys_are_ignored(self):
        """Match load_config() behaviour: unknown top-level keys are not fatal."""
        config = config_from_dict(
            {"providers": {"ollama": {"type": "ollama"}}, "future_section": {"x": 1}}
        )
        assert set(config.providers) == {"ollama"}

    def test_plain_string_api_key_is_coerced_to_secret(self):
        """Dict input uses plain strings; pydantic coerces to SecretStr."""
        config = config_from_dict(
            {
                "providers": {
                    "openai": {
                        "type": "openai",
                        "api_key": "sk-literal-from-dict",
                        "api_key_literal": True,
                    }
                }
            }
        )
        assert config.providers["openai"].api_key is not None
        assert (
            config.providers["openai"].api_key.get_secret_value()
            == "sk-literal-from-dict"
        )
        assert config.providers["openai"].api_key_literal is True

    def test_round_trip_with_load_config(self):
        """A TOML file parsed by tomllib must produce the same AppConfig
        whether loaded via load_config() or config_from_dict()."""
        example = REPO_ROOT / "config.example.toml"

        with open(example, "rb") as f:
            raw = tomllib.load(f)

        assert config_from_dict(raw) == load_config(example)


class TestApiKeyField:
    def test_literal_key_stored_as_secret(self):
        cfg = ProviderConfig(
            type=ProviderType.OPENAI,
            api_key=SecretStr("sk-actual-key-value"),
            api_key_literal=True,
        )
        assert cfg.api_key is not None
        assert cfg.api_key.get_secret_value() == "sk-actual-key-value"

    def test_secret_masked_in_repr(self):
        cfg = ProviderConfig(
            type=ProviderType.OPENAI,
            api_key=SecretStr("sk-super-secret-value-123"),
            api_key_literal=True,
        )
        assert "sk-super-secret-value-123" not in repr(cfg)
        assert "sk-super-secret-value-123" not in str(cfg)

    def test_non_literal_key_is_env_var_name(self):
        cfg = ProviderConfig(
            type=ProviderType.OPENAI,
            api_key=SecretStr("MY_CUSTOM_ENV_VAR"),
        )
        assert cfg.api_key_literal is False


class TestBuildProviderKeyResolution:
    """build_provider() must interpret the api_key field per api_key_literal."""

    def test_inline_key_used_directly(self, monkeypatch):
        """A literal key bypasses keyring/env lookup entirely."""
        import llm_pycascade.secrets as secrets_mod

        def _no_lookup(*args, **kwargs):  # pragma: no cover
            raise AssertionError("resolve_api_key must not be called")

        monkeypatch.setattr(secrets_mod, "resolve_api_key", _no_lookup)

        provider = build_provider(
            "openai",
            ProviderConfig(
                type=ProviderType.OPENAI,
                api_key=SecretStr("sk-inline"),
                api_key_literal=True,
            ),
            "gpt-4o",
        )
        assert isinstance(provider, OpenAIProvider)
        assert provider._api_key == "sk-inline"

    def test_non_literal_api_key_names_env_var(self, monkeypatch):
        monkeypatch.delenv("MY_DICT_KEY", raising=False)
        monkeypatch.setenv("MY_DICT_KEY", "sk-from-env")

        provider = build_provider(
            "openai",
            ProviderConfig(
                type=ProviderType.OPENAI,
                api_key=SecretStr("MY_DICT_KEY"),
            ),
            "gpt-4o",
        )
        assert isinstance(provider, OpenAIProvider)
        assert provider._api_key == "sk-from-env"

    def test_api_key_env_takes_precedence_over_api_key(self, monkeypatch):
        """Explicit api_key_env wins over the api_key env-var shorthand."""
        monkeypatch.delenv("PRIMARY_ENV", raising=False)
        monkeypatch.delenv("SECONDARY_ENV", raising=False)
        monkeypatch.setenv("PRIMARY_ENV", "sk-primary")

        provider = build_provider(
            "openai",
            ProviderConfig(
                type=ProviderType.OPENAI,
                api_key=SecretStr("SECONDARY_ENV"),
                api_key_env="PRIMARY_ENV",
            ),
            "gpt-4o",
        )
        assert isinstance(provider, OpenAIProvider)
        assert provider._api_key == "sk-primary"

    def test_default_env_var_convention(self, monkeypatch):
        monkeypatch.delenv("MYPROVIDER_API_KEY", raising=False)
        monkeypatch.setenv("MYPROVIDER_API_KEY", "sk-conventional")

        provider = build_provider(
            "myprovider",
            ProviderConfig(type=ProviderType.ANTHROPIC),
            "claude-sonnet-4-20250514",
        )
        assert isinstance(provider, AnthropicProvider)
        assert provider._api_key == "sk-conventional"

    def test_missing_everything_raises(self, monkeypatch):
        """No inline key, no keyring entry, no env var → ValueError."""
        import llm_pycascade.secrets as secrets_mod

        monkeypatch.setattr(secrets_mod, "_KEYRING_AVAILABLE", False)
        monkeypatch.delenv("GHOSTPROVIDER_API_KEY", raising=False)

        with pytest.raises(ValueError):
            build_provider(
                "ghostprovider",
                ProviderConfig(type=ProviderType.GEMINI),
                "gemini-2.0-flash",
            )

    def test_gemini_inline_key(self):
        provider = build_provider(
            "gemini",
            ProviderConfig(
                type=ProviderType.GEMINI,
                api_key=SecretStr("AIza-inline"),
                api_key_literal=True,
            ),
            "gemini-2.0-flash",
        )
        assert isinstance(provider, GeminiProvider)
        assert provider._api_key == "AIza-inline"

    def test_ollama_needs_no_key(self):
        from llm_pycascade.providers.ollama import OllamaProvider

        provider = build_provider(
            "ollama",
            ProviderConfig(type=ProviderType.OLLAMA),
            "llama3.1",
        )
        assert isinstance(provider, OllamaProvider)


class TestDictConfigCascadeSmoke:
    """Smoke tests: a dict-built AppConfig flows through run_cascade."""

    @pytest.mark.asyncio
    async def test_unknown_cascade_raises_keyerror(self, tmp_path):
        from llm_pycascade.cascade import run_cascade
        from llm_pycascade.db import init_db
        from llm_pycascade.models.conversation import Conversation

        config = config_from_dict({"providers": {"ollama": {"type": "ollama"}}})
        conn = await init_db(str(tmp_path / "test.db"))
        try:
            conv = Conversation.single_user_prompt("test")
            with pytest.raises(KeyError):
                await run_cascade("nonexistent", conv, config, conn)
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_entries_with_unknown_providers_are_skipped(self, tmp_path):
        """Entries referencing unknown providers are skipped, no network
        is touched, and exhausting the cascade persists the failure."""
        from llm_pycascade.cascade import run_cascade
        from llm_pycascade.db import init_db
        from llm_pycascade.error import CascadeError
        from llm_pycascade.models.conversation import Conversation

        failure_dir = tmp_path / "failed"

        config = config_from_dict(
            {
                "providers": {"ollama": {"type": "ollama"}},
                "cascades": {
                    "only-ghosts": {
                        "entries": [
                            {"provider": "ghost1", "model": "nope"},
                            {"provider": "ghost2", "model": "nada"},
                        ]
                    }
                },
                "database": {"path": str(tmp_path / "test.db")},
                "failure_persistence": {"dir": str(failure_dir)},
            }
        )
        conn = await init_db(str(tmp_path / "test.db"))
        try:
            conv = Conversation.single_user_prompt("test")
            with pytest.raises(CascadeError):
                await run_cascade("only-ghosts", conv, config, conn)
        finally:
            await conn.close()

        # The failed conversation was persisted under a cascade-named
        # subdirectory of the configured directory
        saved = list(failure_dir.glob("only-ghosts/*.json"))
        assert len(saved) == 1
