"""Shared message utility functions for agent_runtime."""

from typing import Any, Optional


def extract_plain_user_content(message: dict[str, Any]) -> Optional[str]:
    """Extract plain text from a user message payload.

    Used for echo dedup in both service and session_manager layers.
    """
    if message.get("type") != "user":
        return None
    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
        return text or None
    if (
        isinstance(content, list)
        and len(content) == 1
        and isinstance(content[0], dict)
    ):
        block = content[0]
        block_type = block.get("type")
        if block_type in {"text", None}:
            text = block.get("text")
            if isinstance(text, str):
                text = text.strip()
                return text or None
    return None
