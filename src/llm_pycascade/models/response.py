"""LLM response and content block models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ContentBlockType(str, Enum):
    """Discriminator for the different content block types."""

    TEXT = "text"
    TOOL_CALL = "tool_call"


class ContentBlock(BaseModel):
    """A single block in an LLM response — either text or a tool call.

    This is a discriminated-union model.  The ``type`` field determines
    which other fields are meaningful.

    Attributes:
        type: ``"text"`` or ``"tool_call"``.
        text: The text content (only for type=text).
        id: Tool-call identifier (only for type=tool_call).
        name: Tool function name (only for type=tool_call).
        arguments: JSON-encoded arguments string (only for type=tool_call).
    """

    type: ContentBlockType
    text: str | None = Field(default=None, exclude_none=True)
    id: str | None = Field(default=None, exclude_none=True)
    name: str | None = Field(default=None, exclude_none=True)
    arguments: str | None = Field(default=None, exclude_none=True)

    # ── convenience constructors ──────────────────────────────────────

    @classmethod
    def make_text(cls, text_content: str) -> ContentBlock:
        """Create a text content block."""
        return cls(type=ContentBlockType.TEXT, text=text_content)

    @classmethod
    def make_tool_call(cls, call_id: str, name: str, arguments: str) -> ContentBlock:
        """Create a tool-call content block."""
        return cls(
            type=ContentBlockType.TOOL_CALL,
            id=call_id,
            name=name,
            arguments=arguments,
        )

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ContentBlock):
            return NotImplemented
        return (
            self.type == other.type
            and self.text == other.text
            and self.id == other.id
            and self.name == other.name
            and self.arguments == other.arguments
        )

    def __hash__(self) -> int:
        return hash((self.type, self.text, self.id, self.name, self.arguments))


class LlmResponse(BaseModel):
    """Response from an LLM provider.

    Attributes:
        content: Ordered list of content blocks (text and/or tool calls).
        input_tokens: Number of tokens in the prompt.
        output_tokens: Number of tokens in the completion.
        model: Identifier of the model that generated the response.
    """

    content: list[ContentBlock] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    def text_only(self) -> str:
        """Concatenate all text content blocks into a single string.

        Returns:
            Joined text from all text blocks, separated by newlines.
        """
        parts: list[str] = []
        for block in self.content:
            if block.type == ContentBlockType.TEXT and block.text is not None:
                parts.append(block.text)
        return "\n".join(parts)
