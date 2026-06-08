"""
DATA-AI 会话管理器

管理多会话创建、切换、删除，独立上下文
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..utils.exceptions import SessionException
from ..utils.logging import get_logger
from .llm.manager import ChatMessage
from .memory.manager import get_memory_manager

logger = get_logger(__name__)


@dataclass
class Session:
    """会话定义"""

    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [{"role": m.role, "content": m.content, "name": m.name} for m in self.messages],
            "metadata": self.metadata,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """从字典创建"""
        return cls(
            id=data["id"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            messages=[
                ChatMessage(role=m["role"], content=m["content"], name=m.get("name")) for m in data.get("messages", [])
            ],
            metadata=data.get("metadata", {}),
            is_active=data.get("is_active", False),
        )


class SessionManager:
    """
    会话管理器

    管理多个会话的创建、切换、删除
    """

    _instance: SessionManager | None = None

    def __new__(cls) -> SessionManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sessions: dict[str, Session] = {}
            cls._instance._active_session_id: str | None = None
            cls._instance._storage_path: Path | None = None
            cls._instance._memory = get_memory_manager()
        return cls._instance

    def initialize(self, storage_path: Path | None = None) -> None:
        """
        初始化会话管理器

        Args:
            storage_path: 会话存储路径
        """
        if storage_path:
            self._storage_path = Path(storage_path)
            self._storage_path.mkdir(parents=True, exist_ok=True)
            self._load_sessions()

    def create_session(
        self,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """
        创建新会话

        Args:
            name: 会话名称
            metadata: 元数据

        Returns:
            新会话
        """
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now()

        session = Session(
            id=session_id,
            name=name or f"Session-{session_id}",
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

        self._sessions[session_id] = session
        self._save_session(session)

        logger.info(f"会话已创建: {session.name}", session_id=session_id)

        # 自动切换到新会话
        self.switch_session(session_id)

        return session

    def switch_session(self, session_id: str) -> Session:
        """
        切换会话

        Args:
            session_id: 会话 ID

        Returns:
            会话对象

        Raises:
            SessionException: 会话不存在
        """
        if session_id not in self._sessions:
            raise SessionException(f"Session not found: {session_id}")

        # 停用当前会话
        if self._active_session_id:
            current = self._sessions.get(self._active_session_id)
            if current:
                current.is_active = False
                self._save_session(current)

        # 激活新会话
        session = self._sessions[session_id]
        session.is_active = True
        session.updated_at = datetime.now()
        self._active_session_id = session_id
        self._save_session(session)

        logger.info(f"会话已切换: {session.name}", session_id=session_id)

        return session

    def get_session(self, session_id: str | None = None) -> Session | None:
        """
        获取会话

        Args:
            session_id: 会话 ID，None 表示当前活动会话

        Returns:
            会话对象或 None
        """
        if session_id is None:
            session_id = self._active_session_id

        if session_id is None:
            return None

        return self._sessions.get(session_id)

    def get_active_session(self) -> Session | None:
        """获取当前活动会话"""
        return self.get_session(self._active_session_id)

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话 ID

        Returns:
            是否成功删除
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions.pop(session_id)

        # 删除存储文件
        if self._storage_path:
            session_file = self._storage_path / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()

        # 如果删除的是活动会话，清空活动会话
        if self._active_session_id == session_id:
            self._active_session_id = None

        logger.info(f"会话已删除: {session.name}", session_id=session_id)

        return True

    def list_sessions(self) -> list[Session]:
        """列出所有会话"""
        return sorted(
            self._sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True,
        )

    def add_message(
        self,
        role: str,
        content: str,
        session_id: str | None = None,
    ) -> None:
        """
        添加消息到会话

        Args:
            role: 角色 (system, user, assistant, tool)
            content: 消息内容
            session_id: 会话 ID，None 表示当前活动会话
        """
        session = self.get_session(session_id)
        if session is None:
            # 没有活动会话，创建一个
            session = self.create_session()

        message = ChatMessage(role=role, content=content)
        session.messages.append(message)
        session.updated_at = datetime.now()

        # 同时添加到全局记忆
        self._memory.remember(content, source=role, session_id=session.id)

        self._save_session(session)

    def get_messages(
        self,
        session_id: str | None = None,
        limit: int | None = None,
    ) -> list[ChatMessage]:
        """
        获取会话消息

        Args:
            session_id: 会话 ID
            limit: 限制消息数量

        Returns:
            消息列表
        """
        session = self.get_session(session_id)
        if session is None:
            return []

        messages = session.messages
        if limit:
            messages = messages[-limit:]

        return messages

    def clear_messages(self, session_id: str | None = None) -> None:
        """清空会话消息"""
        session = self.get_session(session_id)
        if session:
            session.messages.clear()
            session.updated_at = datetime.now()
            self._save_session(session)

    def rename_session(
        self,
        session_id: str,
        new_name: str,
    ) -> bool:
        """重命名会话"""
        session = self._sessions.get(session_id)
        if session:
            old_name = session.name
            session.name = new_name
            session.updated_at = datetime.now()
            self._save_session(session)
            logger.info(f"会话重命名: {old_name} -> {new_name}", session_id=session_id)
            return True
        return False

    def _save_session(self, session: Session) -> None:
        """保存会话到存储"""
        if self._storage_path:
            session_file = self._storage_path / f"{session.id}.json"
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_sessions(self) -> None:
        """从存储加载会话"""
        if not self._storage_path:
            return

        for session_file in self._storage_path.glob("*.json"):
            try:
                with open(session_file, encoding="utf-8") as f:
                    data = json.load(f)
                session = Session.from_dict(data)
                self._sessions[session.id] = session

                if session.is_active:
                    self._active_session_id = session.id

                logger.debug(f"会话已加载: {session.name}", session_id=session.id)
            except Exception as e:
                logger.warning(f"加载会话失败: {session_file}", error=str(e))


# 全局管理器
_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """获取全局会话管理器"""
    return _session_manager
