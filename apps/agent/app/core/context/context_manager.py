"""Conversation and Execution Context Manager."""

from typing import Any

from app.protocol.models import ProtocolMessage


class ContextManager:
    """Maintains working memory, recent messages, and task context."""

    def __init__(self, max_recent_messages: int = 50) -> None:
        self.max_recent_messages = max_recent_messages
        self._history: list[ProtocolMessage] = []
        self._metadata: dict[str, Any] = {}

    def add_message(self, message: ProtocolMessage) -> None:
        self._history.append(message)
        if len(self._history) > self.max_recent_messages:
            self._history.pop(0)

    def get_history(self) -> list[ProtocolMessage]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
        self._metadata.clear()
