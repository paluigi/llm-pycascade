"""Google Gemini generateContent API provider."""

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

_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


class GeminiProvider(LlmProvider):
    """Provider for the Google Gemini generateContent API.

    The API key is passed as a query parameter (``?key=...``).

    Args:
        api_key: Google AI API key.
        model: Model identifier (e.g. ``gemini-2.0-flash``).
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
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    # ── public interface ─────────────────────────────────────────────

    async def complete(self, conversation: Conversation) -> LlmResponse:
        """Send a generateContent request to the Gemini API."""
        url = (
            f"{self._base_url}/v1beta/models/{self._model}:generateContent"
            f"?key={self._api_key}"
        )
        headers = {"Content-Type": "application/json"}
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
        """Build the JSON payload for the Gemini API request."""
        contents: list[dict[str, Any]] = []
        system_instruction: str | None = None

        for msg in conversation.messages:
            if msg.role == MessageRole.SYSTEM:
                system_instruction = msg.content
            elif msg.role == MessageRole.TOOL:
                # Tool results in Gemini are represented as functionResponse parts
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": msg.tool_call_id or "unknown",
                                    "response": {"content": msg.content},
                                }
                            }
                        ],
                    }
                )
            else:
                # Map "assistant" → "model" for Gemini
                gemini_role = (
                    "model" if msg.role == MessageRole.ASSISTANT else msg.role.value
                )
                contents.append(
                    {
                        "role": gemini_role,
                        "parts": [{"text": msg.content}],
                    }
                )

        payload: dict[str, Any] = {"contents": contents}

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}],
            }

        if conversation.tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        }
                        for tool in conversation.tools
                    ],
                }
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
        """Parse the Gemini API response into an :class:`LlmResponse`."""
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise ProviderError.parse("No candidates in response")

            parts = candidates[0].get("content", {}).get("parts", [])
            content_blocks: list[ContentBlock] = []

            for part in parts:
                if "text" in part:
                    content_blocks.append(ContentBlock.make_text(part["text"]))
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    content_blocks.append(
                        ContentBlock.make_tool_call(
                            id=fc.get("name", "unknown"),
                            name=fc.get("name", "unknown"),
                            arguments=json.dumps(fc.get("args", {})),
                        )
                    )

            usage_meta = data.get("usageMetadata", {})
            input_tokens = usage_meta.get("promptTokenCount", 0)
            output_tokens = usage_meta.get("candidatesTokenCount", 0)

            return LlmResponse(
                content=content_blocks,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=data.get("modelVersion", self._model),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError.parse(f"Unexpected response structure: {exc}") from exc
