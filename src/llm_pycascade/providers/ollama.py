"""Ollama local inference provider."""

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

_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(LlmProvider):
    """Provider for Ollama local inference via the ``/api/chat`` endpoint.

    Ollama does not require an API key.  It supports tool calling through
    the ``tools`` parameter.

    Args:
        model: Model identifier (e.g. ``llama3.1``, ``mistral``).
        base_url: Override the default Ollama base URL.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        self._model = model
        self._base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    # ── public interface ─────────────────────────────────────────────

    async def complete(self, conversation: Conversation) -> LlmResponse:
        """Send a non-streaming chat request to Ollama."""
        url = f"{self._base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        payload = self._build_payload(conversation)

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError.request(f"Request timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            msg = f"Cannot connect to Ollama at {self._base_url}: {exc}"
            raise ProviderError.request(msg) from exc
        except httpx.HTTPError as exc:
            raise ProviderError.request(f"HTTP error: {exc}") from exc

        latency_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code != 200:
            body = resp.text
            raise ProviderError.http(resp.status_code, body)

        return self._parse_response(resp.json(), latency_ms)

    # ── internal helpers ─────────────────────────────────────────────

    def _build_payload(self, conversation: Conversation) -> dict[str, Any]:
        """Build the JSON payload for the Ollama API request."""
        messages: list[dict[str, str]] = []

        for msg in conversation.messages:
            if msg.role == MessageRole.SYSTEM:
                # Ollama accepts system as a regular message role
                messages.append(
                    {"role": "system", "content": msg.content}
                )
            else:
                messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
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

    def _parse_response(self, data: dict[str, Any], latency_ms: int) -> LlmResponse:
        """Parse the Ollama API response into an :class:`LlmResponse`."""
        try:
            content_blocks: list[ContentBlock] = []

            message = data.get("message", {})
            if message:
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
                            arguments=json.dumps(func.get("arguments", {})),
                        )
                    )

            # Ollama reports usage as eval_count (output) and prompt_eval_count (input)
            input_tokens = data.get("prompt_eval_count", 0) or 0
            output_tokens = data.get("eval_count", 0) or 0

            return LlmResponse(
                content=content_blocks,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=data.get("model", self._model),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError.parse(f"Unexpected response structure: {exc}") from exc
