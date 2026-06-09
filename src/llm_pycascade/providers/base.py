"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm_pycascade.models import Conversation, LlmResponse


class LlmProvider(ABC):
    """Abstract base that every LLM provider must implement.

    Subclasses handle the specifics of translating between the library's
    canonical :class:`~llm_pycascade.models.Conversation` /
    :class:`~llm_pycascade.models.LlmResponse` and a given provider's HTTP API.
    """

    @abstractmethod
    async def complete(self, conversation: Conversation) -> LlmResponse:
        """Send a completion request to the provider.

        Args:
            conversation: The conversation to send.

        Returns:
            The provider's response.

        Raises:
            ProviderError: On any failure communicating with the provider.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the canonical name of this provider (e.g. ``openai``)."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier (e.g. ``gpt-4o``)."""
        ...

    @property
    def entry_key(self) -> str:
        """Return a unique ``provider/model`` key used for cooldown tracking."""
        return f"{self.provider_name}/{self.model_name}"
