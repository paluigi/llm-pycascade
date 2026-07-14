"""Conversation and message models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from llm_pycascade.models.tool import (
    ToolDefinition,  # noqa: TC001 - needed by Pydantic at runtime
)


class MessageRole(str, Enum):
    """Role of a participant in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """A single message in a conversation.

    Attributes:
        role: The role of the message sender.
        content: The text content of the message.
        tool_call_id: Optional identifier linking this message to a tool call
                      (used for ``tool`` role messages).
    """

    role: MessageRole
    content: str
    tool_call_id: str | None = Field(default=None, exclude_none=True)

    # ── convenience constructors ──────────────────────────────────────

    @classmethod
    def system(cls, content: str) -> Message:
        """Create a system message."""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        """Create a user message."""
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> Message:
        """Create an assistant message."""
        return cls(role=MessageRole.ASSISTANT, content=content)

    @classmethod
    def tool(cls, content: str, tool_call_id: str) -> Message:
        """Create a tool result message."""
        return cls(role=MessageRole.TOOL, content=content, tool_call_id=tool_call_id)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Message):
            return NotImplemented
        return (
            self.role == other.role
            and self.content == other.content
            and self.tool_call_id == other.tool_call_id
        )

    def __hash__(self) -> int:
        return hash((self.role, self.content, self.tool_call_id))


class Conversation(BaseModel):
    """A multi-turn conversation with optional tool definitions.

    Attributes:
        messages: Ordered list of messages.
        tools: Optional list of tool definitions available to the model.
    """

    messages: list[Message] = Field(default_factory=list)
    tools: list[ToolDefinition] | None = Field(default=None, exclude_none=True)

    # ── convenience constructors ──────────────────────────────────────

    @classmethod
    def new(cls) -> Conversation:
        """Create an empty conversation."""
        return cls(messages=[])

    @classmethod
    def single_user_prompt(cls, prompt: str) -> Conversation:
        """Create a conversation with a single user message."""
        return cls(messages=[Message.user(prompt)])

    @classmethod
    def with_tools(
        cls, messages: list[Message], tools: list[ToolDefinition]
    ) -> Conversation:
        """Create a conversation with messages and tool definitions."""
        return cls(messages=messages, tools=tools)
