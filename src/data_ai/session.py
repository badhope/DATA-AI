"""
DATA-AI 会话管理

管理对话会话的生命周期，包括消息历史、记忆和工具状态。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .core.llm.manager import ChatMessage
from .utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Unnamed Session"
    messages: list[ChatMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str, **kwargs) -> ChatMessage:
        msg = ChatMessage(role=role, content=content, **kwargs)
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def add_user_message(self, content: str) -> ChatMessage:
        return self.add_message("user", content)

    def add_assistant_message(self, content: str, tool_calls: list[dict] | None = None) -> ChatMessage:
        return self.add_message("assistant", content, tool_calls=tool_calls)

    def add_tool_message(self, content: str, tool_call_id: str) -> ChatMessage:
        return self.add_message("tool", content, tool_call_id=tool_call_id)

    def get_messages(self, include_system: bool = True, limit: int | None = None) -> list[ChatMessage]:
        msgs = [m for m in self.messages if include_system or m.role != "system"]
        if limit:
            return msgs[-limit:]
        return msgs

    def get_last_n_messages(self, n: int) -> list[ChatMessage]:
        return self.messages[-n:]

    def clear(self) -> None:
        self.messages = []
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "message_count": len(self.messages),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def get_stats(self) -> dict[str, Any]:
        roles = {}
        for msg in self.messages:
            roles[msg.role] = roles.get(msg.role, 0) + 1
        return {
            "id": self.id,
            "name": self.name,
            "message_count": len(self.messages),
            "role_distribution": roles,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._active_session: str | None = None

    def create_session(self, name: str = "Unnamed Session", system_prompt: str | None = None) -> Session:
        session = Session(name=name)
        if system_prompt:
            session.add_message("system", system_prompt)
        self._sessions[session.id] = session
        self._active_session = session.id
        logger.info(f"Session created: {session.id}", name=name)
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def get_active_session(self) -> Session | None:
        if self._active_session:
            return self._sessions.get(self._active_session)
        return None

    def set_active_session(self, session_id: str) -> None:
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        self._active_session = session_id

    def delete_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._active_session == session_id:
                self._active_session = None

    def list_sessions(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._sessions.values()]

    def clear_all(self) -> None:
        self._sessions = {}
        self._active_session = None


_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    return _session_manager
