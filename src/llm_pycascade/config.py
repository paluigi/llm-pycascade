"""Configuration types and TOML loading utilities."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Python ≥ 3.11 has tomllib in the stdlib; fall back to tomli on older versions.
if os.sys.version_info >= (3, 11):
    import tomllib  # type: ignore[import-not-found]
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ImportError:
        import tomli as tomllib  # type: ignore[import-not-found]


class ProviderType(str, Enum):
    """Supported LLM provider types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider.

    Attributes:
        type: The provider type (openai, anthropic, gemini, ollama).
        api_key_service: Service name to look up in the system keyring.
        api_key_env: Environment variable name to read the API key from.
        base_url: Override the default API base URL.
    """

    type: ProviderType
    api_key_service: str | None = Field(default=None, exclude_none=True)
    api_key_env: str | None = Field(default=None, exclude_none=True)
    base_url: str | None = Field(default=None, exclude_none=True)


class CascadeEntry(BaseModel):
    """A single entry in a cascade — one provider/model pair.

    Attributes:
        provider: Key name of the provider (must match a key in ``[providers]``).
        model: The model identifier to use.
    """

    provider: str
    model: str


class CascadeConfig(BaseModel):
    """Ordered list of provider/model entries that form a cascade.

    Attributes:
        entries: The cascade entries, tried in order.
    """

    entries: list[CascadeEntry] = Field(default_factory=list)


class DatabaseConfig(BaseModel):
    """Configuration for the SQLite database used for attempt logging and cooldowns.

    Attributes:
        path: Filesystem path to the SQLite database.
    """

    path: str = "~/.local/share/llm-pycascade/db.sqlite"


class FailureConfig(BaseModel):
    """Configuration for persisting failed conversations.

    Attributes:
        dir: Directory where failed-prompt JSON files are saved.
    """

    dir: str = "~/.local/share/llm-pycascade/failed_prompts"


class AppConfig(BaseModel):
    """Top-level application configuration loaded from TOML.

    Attributes:
        providers: Mapping of provider names to their configurations.
        cascades: Mapping of cascade names to ordered entry lists.
        database: Database configuration.
        failure_persistence: Failed-prompt persistence configuration.
    """

    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    cascades: dict[str, CascadeConfig] = Field(default_factory=dict)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    failure_persistence: FailureConfig = Field(default_factory=FailureConfig)


def expand_tilde(path: str) -> str:
    """Expand a leading ``~`` to the user's home directory.

    Args:
        path: A filesystem path that may start with ``~``.

    Returns:
        The expanded absolute path.
    """
    return os.path.expanduser(path)


def default_config_path() -> Path:
    """Return the default configuration file path.

    Searches (in order):

    1. ``LLM_PYCASCADE_CONFIG`` environment variable
    2. ``~/.config/llm-pycascade/config.toml``
    3. ``~/.llm-pycascade.toml`` (legacy)

    Returns:
        Path to the first config file found, or the preferred default.
    """
    env_path = os.environ.get("LLM_PYCASCADE_CONFIG")
    if env_path:
        return Path(env_path)

    xdg = Path.home() / ".config" / "llm-pycascade" / "config.toml"
    if xdg.exists():
        return xdg

    legacy = Path.home() / ".llm-pycascade.toml"
    if legacy.exists():
        return legacy

    return xdg


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load and parse the application configuration from a TOML file.

    Args:
        path: Explicit path to the configuration file.  If ``None``, uses
              :func:`default_config_path`.

    Returns:
        A fully-resolved :class:`AppConfig` instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        tomllib.TOMLDecodeError: If the file contains invalid TOML.
    """
    path = default_config_path() if path is None else Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "rb") as f:
        raw: dict[str, Any] = tomllib.load(f)

    # Parse the [providers] section
    providers: dict[str, ProviderConfig] = {}
    for name, pcfg in raw.get("providers", {}).items():
        providers[name] = ProviderConfig(**pcfg)

    # Parse the [cascades] section
    cascades: dict[str, CascadeConfig] = {}
    for cascade_name, ccfg in raw.get("cascades", {}).items():
        entries_raw = ccfg.get("entries", [])
        entries = [CascadeEntry(**e) for e in entries_raw]
        cascades[cascade_name] = CascadeConfig(entries=entries)

    # Parse optional [database] and [failure_persistence] sections
    database = (
        DatabaseConfig(**raw["database"]) if "database" in raw else DatabaseConfig()
    )
    failure = (
        FailureConfig(**raw["failure_persistence"])
        if "failure_persistence" in raw
        else FailureConfig()
    )

    return AppConfig(
        providers=providers,
        cascades=cascades,
        database=database,
        failure_persistence=failure,
    )
