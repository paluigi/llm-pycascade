"""Anthropic Messages API provider."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from llm_pycascade.error import ProviderError
from llm_pycascade.models.conversation import Conversation, MessageRole
from llm_pycascade.models.response import ContentBlock, LlmResponse
from llm_pycascade.providers.base import LlmProvider

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.anthropic.com"
_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_ANTHROPIC_VERSION = "2023-06-01"
_MAX_TOKENS = 4096


class AnthropicProvider(LlmProvider):
    """Provider for the Anthropic Messages API.

    Args:
        api_key: API key (``x-api-key`` header).
        model: Model identifier (e.g. ``claude-sonnet-4-20250514``).
        base_url: Override the default API base URL.
        max_tokens: Maximum tokens to generate (default 4096).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        base_url: str | None = None,
        max_tokens: int = _MAX_TOKENS,
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._max_tokens = max_tokens
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    # ── public interface ─────────────────────────────────────────────

    async def complete(self, conversation: Conversation) -> LlmResponse:
        """Send a messages request to the Anthropic API.

        System messages are extracted and sent as the top-level ``system``
        parameter.  All other messages are sent in the ``messages`` array.
        """
        url = f"{self._base_url}/v1/messages"
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
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
        """Build the JSON payload for the Anthropic API request."""
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []

        for msg in conversation.messages:
            if msg.role == MessageRole.SYSTEM:
                system_parts.append(msg.content)
            elif msg.role == MessageRole.TOOL:
                # Anthropic expects tool results as role=user with
                # tool_result content blocks
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            elif msg.role == MessageRole.ASSISTANT:
                # Simple text assistant message
                messages.append({"role": "assistant", "content": msg.content})
            else:
                messages.append({"role": msg.role.value, "content": msg.content})

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": messages,
        }

        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        if conversation.tools:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in conversation.tools
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
        """Parse the Anthropic API response into an :class:`LlmResponse`."""
        try:
            content_blocks: list[ContentBlock] = []

            for block in data.get("content", []):
                if block.get("type") == "text":
                    content_blocks.append(ContentBlock.make_text(block["text"]))
                elif block.get("type") == "tool_use":
                    content_blocks.append(
                        ContentBlock.make_tool_call(
                            id=block["id"],
                            name=block["name"],
                            arguments=json.dumps(block.get("input", {})),
                        )
                    )

            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            return LlmResponse(
                content=content_blocks,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=data.get("model", self._model),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError.parse(f"Unexpected response structure: {exc}") from exc
