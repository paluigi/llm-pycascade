# Tools & function calling

`llm-pycascade` provides first-class support for tool (function) calling
across all built-in providers.

## Defining tools

A tool is defined with a name, description, and a JSON Schema describing its
parameters:

```python
from llm_pycascade import ToolDefinition

tools = [
    ToolDefinition(
        name="get_weather",
        description="Get the current weather for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
            },
            "required": ["city"],
        },
    )
]
```

## Sending a conversation with tools

Use `Conversation.with_tools()` to attach tools to your messages:

```python
from llm_pycascade import Conversation, Message

conversation = Conversation.with_tools(
    messages=[Message.user("What's the weather in Tokyo?")],
    tools=tools,
)
```

## Reading the response

A response contains a list of [`ContentBlock`](reference/models.md) objects,
each of which is either text or a tool call. The block `type` determines which
fields are meaningful.

!!! note "Importing the block-type enum"

    `ContentBlockType` is not exported from the top-level package. Import it
    directly from the response model module:

    ```python
    from llm_pycascade.models.response import ContentBlockType
    ```

```python
import asyncio

from llm_pycascade import (
    Conversation,
    Message,
    ToolDefinition,
    init_db,
    load_config,
    run_cascade,
)
from llm_pycascade.config import expand_tilde
from llm_pycascade.models.response import ContentBlockType

tools = [
    ToolDefinition(
        name="get_weather",
        description="Get the current weather for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
            },
            "required": ["city"],
        },
    )
]


async def main() -> None:
    config = load_config()
    conn = await init_db(expand_tilde(config.database.path))

    conversation = Conversation.with_tools(
        messages=[Message.user("What's the weather in Tokyo?")],
        tools=tools,
    )

    try:
        response = await run_cascade("primary", conversation, config, conn)

        for block in response.content:
            if block.type == ContentBlockType.TEXT:
                print(f"Text: {block.text}")
            elif block.type == ContentBlockType.TOOL_CALL:
                print(f"Tool call: {block.name}({block.arguments})")
    finally:
        await conn.close()


asyncio.run(main())
```

## Handling tool calls

When the model returns a `tool_call` block, it expects you to:

1. Execute the tool with the decoded `arguments` (a JSON string).
2. Append the result as a `tool` role message referencing the call's `id`.
3. Re-run the cascade.

```python
import json

from llm_pycascade import Message

for block in response.content:
    if block.type == ContentBlockType.TOOL_CALL:
        # Decode and execute the tool
        args = json.loads(block.arguments)
        result = get_weather(**args)  # your implementation

        # Feed the result back into the conversation
        conversation.messages.append(
            Message.tool(content=str(result), tool_call_id=block.id)
        )

        # Re-run the cascade so the model can use the tool result
        response = await run_cascade("primary", conversation, config, conn)
```

## Convenience constructors

`ContentBlock` provides helpers for building blocks programmatically:

| Constructor | Purpose |
|-------------|---------|
| `ContentBlock.make_text(text)` | Create a text block |
| `ContentBlock.make_tool_call(id, name, arguments)` | Create a tool-call block |

See the [models API reference](reference/models.md) for the full type details.
