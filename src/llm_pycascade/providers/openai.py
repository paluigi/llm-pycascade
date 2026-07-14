"""OpenAI Chat Completions API provider.

Compatible with any OpenAI-compatible endpoint (e.g. vLLM, LiteLLM,
Together AI, etc.) by overriding ``base_url``.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import httpx

from llm_pycascade.error import ProviderError
from llm_pycascade.models.response import ContentBlock, LlmResponse
from llm_pycascade.providers.base import LlmProvider

if TYPE_CHECKING:
    from llm_pycascade.models.conversation import Conversation

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(LlmProvider):
    """Provider for the OpenAI Chat Completions API.

    Args:
        api_key: Bearer token for authentication.
        model: Model identifier (e.g. ``gpt-4o``, ``gpt-4o-mini``).
        base_url: Override the default API base URL.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    # ── public interface ─────────────────────────────────────────────

    async def complete(self, conversation: Conversation) -> LlmResponse:
        """Send a chat completion request to the OpenAI API.

        Maps the canonical conversation model to OpenAI's ``messages`` format,
        sends the request, and parses the response including tool calls and
        usage statistics.
        """
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(conversation)

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError.request(f"Request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError.request(f"HTTP error: {exc}") from exc

        latency_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code != 200:
            body = resp.text
            retry_after = self._parse_retry_after(resp.headers)
            raise ProviderError.http(resp.status_code, body, retry_after)

        return self._parse_response(resp.json(), latency_ms)

    # ── internal helpers ─────────────────────────────────────────────

    def _build_payload(self, conversation: Conversation) -> dict[str, Any]:
        """Build the JSON payload for the OpenAI API request."""
        messages: list[dict[str, Any]] = []

        for msg in conversation.messages:
            msg_dict: dict[str, Any] = {
                "role": msg.role.value,
                "content": msg.content,
            }
            # Attach tool_call_id for tool-role messages
            if msg.tool_call_id is not None:
                msg_dict["tool_call_id"] = msg.tool_call_id
            messages.append(msg_dict)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }

        if conversation.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in conversation.tools
            ]

        return payload

    @staticmethod
    def _parse_retry_after(headers: httpx.Headers) -> int | None:
        """Extract the ``Retry-After`` header value."""
        val = headers.get("retry-after")
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    def _parse_response(self, data: dict[str, Any], latency_ms: int) -> LlmResponse:
        """Parse the OpenAI API response into an :class:`LlmResponse`."""
        try:
            choices = data.get("choices", [])
            if not choices:
                raise ProviderError.parse("No choices in response")

            content_blocks: list[ContentBlock] = []

            for choice in choices:
                message = choice.get("message", {})

                # Text content
                text = message.get("content")
                if text:
                    content_blocks.append(ContentBlock.make_text(text))

                # Tool calls
                tool_calls = message.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    content_blocks.append(
                        ContentBlock.make_tool_call(
                            call_id=tc.get("id", ""),
                            name=func.get("name", ""),
                            arguments=func.get("arguments", "{}"),
                        )
                    )

            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return LlmResponse(
                content=content_blocks,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=data.get("model", self._model),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError.parse(f"Unexpected response structure: {exc}") from exc
