"""Tests for the OpenAI provider."""

import json

import httpx
import pytest

from llm_pycascade.error import ProviderError
from llm_pycascade.models.conversation import Conversation, Message
from llm_pycascade.models.response import ContentBlockType
from llm_pycascade.models.tool import ToolDefinition
from llm_pycascade.providers.openai import OpenAIProvider


@pytest.fixture
def provider():
    return OpenAIProvider(api_key="test-key", model="gpt-4o")


@pytest.fixture
def conversation():
    return Conversation(
        messages=[
            Message.system("You are helpful."),
            Message.user("Hello"),
        ]
    )


@pytest.fixture
def conversation_with_tools():
    return Conversation.with_tools(
        messages=[Message.user("What is the weather in Tokyo?")],
        tools=[
            ToolDefinition(
                name="get_weather",
                description="Get weather for a city",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            )
        ],
    )


class TestOpenAIBuildPayload:
    def test_basic_messages(self, provider, conversation):
        payload = provider._build_payload(conversation)
        assert payload["model"] == "gpt-4o"
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "You are helpful."
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == "Hello"

    def test_no_tools_by_default(self, provider, conversation):
        payload = provider._build_payload(conversation)
        assert "tools" not in payload

    def test_tools_included(self, provider, conversation_with_tools):
        payload = provider._build_payload(conversation_with_tools)
        assert "tools" in payload
        assert payload["tools"][0]["type"] == "function"
        assert payload["tools"][0]["function"]["name"] == "get_weather"
        assert payload["tools"][0]["function"]["parameters"]["required"] == ["city"]


class TestOpenAIParseResponse:
    def test_text_response(self, provider):
        data = {
            "choices": [
                {"message": {"content": "Hello!", "role": "assistant"}},
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "gpt-4o",
        }
        result = provider._parse_response(data, latency_ms=100)
        assert result.text_only() == "Hello!"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.model == "gpt-4o"

    def test_tool_call_response(self, provider):
        data = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city": "Tokyo"}',
                                },
                            }
                        ],
                    }
                },
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 15},
            "model": "gpt-4o",
        }
        result = provider._parse_response(data, latency_ms=100)
        assert len(result.content) == 1
        block = result.content[0]
        assert block.type == ContentBlockType.TOOL_CALL
        assert block.name == "get_weather"
        assert json.loads(block.arguments) == {"city": "Tokyo"}

    def test_no_choices_raises(self, provider):
        data = {"choices": [], "usage": {}}
        with pytest.raises(ProviderError) as exc_info:
            provider._parse_response(data, latency_ms=100)
        assert exc_info.value.variant == "parse"


class TestOpenAIComplete:
    @pytest.mark.asyncio
    async def test_successful_request(self, provider, conversation):
        """Test the full complete() flow with a mocked HTTP response."""
        mock_response_data = {
            "choices": [
                {"message": {"content": "Hi there!", "role": "assistant"}},
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            "model": "gpt-4o",
        }

        mock_resp = httpx.Response(
            200,
            json=mock_response_data,
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )

        with httpx.MockTransport(lambda req: mock_resp) as transport:
            client = httpx.AsyncClient(transport=transport)
            # Patch the client context manager
            original_client_init = httpx.AsyncClient.__init__

            def patched_init(self, *args, **kwargs):
                kwargs["transport"] = transport
                original_client_init(self, **kwargs)

            httpx.AsyncClient.__init__ = patched_init
            try:
                result = await provider.complete(conversation)
            finally:
                httpx.AsyncClient.__init__ = original_client_init
                await client.aclose()

        assert result.text_only() == "Hi there!"

    @pytest.mark.asyncio
    async def test_http_error_raises_provider_error(self, provider, conversation):
        """Test that HTTP errors are converted to ProviderError."""
        mock_resp = httpx.Response(
            429,
            text="Rate limited",
            headers={"retry-after": "30"},
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )

        with httpx.MockTransport(lambda req: mock_resp) as transport:
            original_client_init = httpx.AsyncClient.__init__

            def patched_init(self, *args, **kwargs):
                kwargs["transport"] = transport
                original_client_init(self, **kwargs)

            httpx.AsyncClient.__init__ = patched_init
            try:
                with pytest.raises(ProviderError) as exc_info:
                    await provider.complete(conversation)
            finally:
                httpx.AsyncClient.__init__ = original_client_init

        assert exc_info.value.variant == "http"
        assert exc_info.value.http_status == 429
        assert exc_info.value.retry_after_seconds == 30


class TestOpenAIProviderProperties:
    def test_provider_name(self, provider):
        assert provider.provider_name == "openai"

    def test_model_name(self, provider):
        assert provider.model_name == "gpt-4o"

    def test_entry_key(self, provider):
        assert provider.entry_key == "openai/gpt-4o"

    def test_base_url_trailing_slash_stripped(self):
        p = OpenAIProvider(api_key="k", model="m", base_url="https://custom.com/v1/")
        assert p._base_url == "https://custom.com/v1"
