"""API key resolution with optional keyring support."""

from __future__ import annotations

import logging
import os

_KEYRING_AVAILABLE = False
try:
    import keyring  # type: ignore[import-not-found]

    _KEYRING_AVAILABLE = True
except ImportError:
    keyring = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_SERVICE_PREFIX = "llm-pycascade"


def resolve_api_key(service_name: str, env_var: str) -> str:
    """Resolve an API key for a provider.

    Resolution order:

    1. System keyring (if the ``keyring`` package is installed).
    2. Environment variable.

    Args:
        service_name: Keyring service name (e.g. ``openai``).
        env_var: Name of the environment variable to fall back to.

    Returns:
        The resolved API key string.

    Raises:
        ValueError: If no API key can be found through any method.
    """
    # 1. Try keyring
    if _KEYRING_AVAILABLE:
        key = _get_key(service_name)
        if key is not None:
            logger.debug("Resolved API key for %r from keyring", service_name)
            return key

    # 2. Try environment variable
    key = os.environ.get(env_var)
    if key:
        logger.debug("Resolved API key for %r from env var %r", service_name, env_var)
        return key

    raise ValueError(
        f"Could not resolve API key for '{service_name}': "
        f"keyring {'not available or ' if not _KEYRING_AVAILABLE else ''}no entry, "
        f"env var '{env_var}' not set"
    )


def _qualified_service(service_name: str) -> str:
    """Return the fully-qualified keyring service name."""
    return f"{_SERVICE_PREFIX}/{service_name}"


def set_key(service_name: str, key: str) -> None:
    """Store an API key in the system keyring.

    Args:
        service_name: Logical service name (e.g. ``openai``).
        key: The API key to store.

    Raises:
        RuntimeError: If the ``keyring`` package is not installed.
    """
    if not _KEYRING_AVAILABLE:
        raise RuntimeError(
            "The 'keyring' package is required for key storage. "
            "Install it with: pip install keyring"
        )
    keyring.set_password(_qualified_service(service_name), "api_key", key)  # type: ignore[union-attr]
    logger.debug("Stored API key for %r in keyring", service_name)


def _get_key(service_name: str) -> str | None:
    """Retrieve an API key from the system keyring.

    Args:
        service_name: Logical service name.

    Returns:
        The API key, or ``None`` if not found.
    """
    if not _KEYRING_AVAILABLE:
        return None
    result = keyring.get_password(_qualified_service(service_name), "api_key")  # type: ignore[union-attr]
    return result


def get_key(service_name: str) -> str | None:
    """Retrieve an API key from the system keyring.

    Args:
        service_name: Logical service name.

    Returns:
        The API key, or ``None`` if not found / keyring unavailable.
    """
    return _get_key(service_name)


def delete_key(service_name: str) -> None:
    """Remove an API key from the system keyring.

    Args:
        service_name: Logical service name.

    Raises:
        RuntimeError: If the ``keyring`` package is not installed.
    """
    if not _KEYRING_AVAILABLE:
        raise RuntimeError(
            "The 'keyring' package is required for key storage. "
            "Install it with: pip install keyring"
        )
    keyring.delete_password(_qualified_service(service_name), "api_key")  # type: ignore[union-attr]
    logger.debug("Deleted API key for %r from keyring", service_name)


def has_key(service_name: str) -> bool:
    """Check whether an API key exists in the system keyring.

    Args:
        service_name: Logical service name.

    Returns:
        ``True`` if a key exists, ``False`` otherwise.
    """
    return _get_key(service_name) is not None


def mask_key(key: str) -> str:
    """Return a masked version of an API key for safe logging/display.

    Shows the first 4 and last 4 characters, masking everything in between.

    Args:
        key: The API key string.

    Returns:
        A masked representation, e.g. ``sk-a...xyz1``.

    Examples:
        >>> mask_key("sk-abcdef1234567890")
        'sk-a...7890'
    """
    if len(key) <= 12:
        # Too short to meaningfully mask; just return asterisks
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"
