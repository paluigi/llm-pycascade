"""Tool definition model."""

from __future__ import annotations

from pydantic import BaseModel


class ToolDefinition(BaseModel):
    """Definition of a tool/function that can be invoked by the LLM.

    Attributes:
        name: The function name.
        description: Human-readable description of what the tool does.
        parameters: JSON Schema object describing the tool's parameters.
    """

    name: str
    description: str = ""
    parameters: dict = {}
