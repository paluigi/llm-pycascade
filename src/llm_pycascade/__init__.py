"""llm-pycascade — Resilient cascading LLM inference
with failover and circuit breaking."""

from llm_pycascade.cascade import run_cascade
from llm_pycascade.config import (
    AppConfig,
    CascadeConfig,
    CascadeEntry,
    DatabaseConfig,
    FailureConfig,
    ProviderConfig,
    ProviderType,
    load_config,
)
from llm_pycascade.db import init_db
from llm_pycascade.error import CascadeError, ProviderError
from llm_pycascade.models import (
    ContentBlock,
    Conversation,
    LlmResponse,
    Message,
    MessageRole,
    ToolDefinition,
)

__all__ = [
    "run_cascade",
    "AppConfig",
    "CascadeConfig",
    "CascadeEntry",
    "DatabaseConfig",
    "FailureConfig",
    "ProviderConfig",
    "ProviderType",
    "load_config",
    "init_db",
    "CascadeError",
    "ProviderError",
    "ContentBlock",
    "Conversation",
    "LlmResponse",
    "Message",
    "MessageRole",
    "ToolDefinition",
]

__version__ = "0.1.0"
