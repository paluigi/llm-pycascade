"""Failed-conversation persistence utilities."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm_pycascade.models import Conversation


def save_failed_conversation(
    conversation: Conversation,
    directory: str,
    cascade_name: str,
) -> Path:
    """Persist a failed conversation as a timestamped JSON file.

    The file is saved to ``<directory>/<cascade_name>/<timestamp>.json``.

    Args:
        conversation: The conversation that failed.
        directory: Root directory for failed-prompt storage.
        cascade_name: Name of the cascade (used as a subdirectory).

    Returns:
        Path to the saved JSON file.
    """
    directory = os.path.expanduser(directory)
    cascade_dir = Path(directory) / cascade_name
    cascade_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{ts}.json"
    filepath = cascade_dir / filename

    data = {
        "cascade_name": cascade_name,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "messages": [msg.model_dump() for msg in conversation.messages],
    }
    if conversation.tools:
        data["tools"] = [t.model_dump() for t in conversation.tools]

    filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return filepath
