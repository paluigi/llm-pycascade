"""Tests for the Ollama provider."""

import json

import pytest

from llm_pycascade.models.conversation import Conversation, Message
from llm_pycascade.models.response import ContentBlockType
from llm_pycascade.providers.ollama import OllamaProvider


@pytest.fixture
def provider():
    return OllamaProvider(model="llama3.1")


@pytest.fixture
def conversation():
    return Conversation(
        messages=[
            Message.system("You are helpful."),
            Message.user("Hello"),
        ]
    )


class TestOllamaBuildPayload:
    def test_basic_messages(self, provider, conversation):
        payload = provider._build_payload(conversation)
        assert payload["model"] == "llama3.1"
        assert payload["stream"] is False
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"

    def test_no_tools_by_default(self, provider, conversation):
        payload = provider._build_payload(conversation)
        assert "tools" not in payload


class TestOllamaParseResponse:
    def test_text_response(self, provider):
        data = {
            "model": "llama3.1",
            "message": {"content": "Hi there!", "role": "assistant"},
            "prompt_eval_count": 15,
            "eval_count": 8,
        }
        result = provider._parse_response(data, latency_ms=50)
        assert result.text_only() == "Hi there!"
        assert result.input_tokens == 15
        assert result.output_tokens == 8
        assert result.model == "llama3.1"

    def test_empty_message(self, provider):
        data = {"model": "llama3.1", "message": {}}
        result = provider._parse_response(data, latency_ms=10)
        assert result.text_only() == ""
        assert len(result.content) == 0

    def test_tool_call_response(self, provider):
        data = {
            "model": "llama3.1",
            "message": {
                "content": "",
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "get_weather",
                            "arguments": {"city": "Tokyo"},
                        },
                    }
                ],
            },
            "eval_count": 10,
        }
        result = provider._parse_response(data, latency_ms=50)
        assert len(result.content) == 1
        block = result.content[0]
        assert block.type == ContentBlockType.TOOL_CALL
        assert block.name == "get_weather"
        assert json.loads(block.arguments) == {"city": "Tokyo"}


class TestOllamaProviderProperties:
    def test_provider_name(self, provider):
        assert provider.provider_name == "ollama"

    def test_model_name(self, provider):
        assert provider.model_name == "llama3.1"

    def test_entry_key(self, provider):
        assert provider.entry_key == "ollama/llama3.1"

    def test_base_url_default(self, provider):
        assert provider._base_url == "http://localhost:11434"

    def test_base_url_override(self):
        p = OllamaProvider(model="m", base_url="http://gpu-box:11434/")
        assert p._base_url == "http://gpu-box:11434"
