"""
DATA-AI Memory System Tests

Test MemoryConfig defaults and SessionManager create/list/switch/delete sessions.
"""

import sys
from pathlib import Path

import pytest

# Ensure src is on path
_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def session_manager():
    """Provide a clean SessionManager."""
    from data_ai.core.session import SessionManager

    mgr = SessionManager()
    mgr._sessions.clear()
    mgr._active_session_id = None
    yield mgr
    mgr._sessions.clear()
    mgr._active_session_id = None


# ─── MemoryConfig Tests ──────────────────────────────────────────────────────


class TestMemoryConfig:
    """MemoryConfig defaults tests."""

    def test_enabled_default(self):
        from data_ai.utils.config import MemoryConfig

        config = MemoryConfig()
        assert config.enabled is True

    def test_keep_recent_messages(self):
        from data_ai.utils.config import MemoryConfig

        config = MemoryConfig()
        assert config.keep_recent_messages > 0

    def test_summary_interval(self):
        from data_ai.utils.config import MemoryConfig

        config = MemoryConfig()
        assert config.summary_interval > 0

    def test_custom_config(self):
        from data_ai.utils.config import MemoryConfig

        config = MemoryConfig(keep_recent_messages=50, summary_interval=10)
        assert config.keep_recent_messages == 50
        assert config.summary_interval == 10


# ─── SessionManager Tests ────────────────────────────────────────────────────


class TestSessionManagerMemory:
    """SessionManager memory system tests."""

    def test_create_session(self, session_manager):
        session = session_manager.create_session(name="Memory Test")
        assert session is not None
        assert session.name == "Memory Test"
        assert session.id is not None

    def test_list_sessions_empty(self, session_manager):
        sessions = session_manager.list_sessions()
        assert sessions == []

    def test_list_sessions_after_create(self, session_manager):
        session_manager.create_session(name="S1")
        session_manager.create_session(name="S2")
        session_manager.create_session(name="S3")
        sessions = session_manager.list_sessions()
        assert len(sessions) == 3

    def test_switch_session(self, session_manager):
        s1 = session_manager.create_session(name="S1")
        s2 = session_manager.create_session(name="S2")
        assert session_manager._active_session_id == s2.id

        session_manager.switch_session(s1.id)
        assert session_manager._active_session_id == s1.id

    def test_delete_session(self, session_manager):
        s1 = session_manager.create_session(name="S1")
        session_manager.create_session(name="S2")

        result = session_manager.delete_session(s1.id)
        assert result is True
        assert len(session_manager.list_sessions()) == 1

    def test_delete_nonexistent(self, session_manager):
        result = session_manager.delete_session("nonexistent")
        assert result is False

    def test_add_and_get_messages(self, session_manager):
        s = session_manager.create_session(name="Chat")
        session_manager.add_message("user", "Hello", session_id=s.id)
        session_manager.add_message("assistant", "World", session_id=s.id)

        messages = session_manager.get_messages(session_id=s.id)
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[1].content == "World"

    def test_session_to_dict(self, session_manager):
        s = session_manager.create_session(name="Serialize Test")
        d = s.to_dict()
        assert d["id"] == s.id
        assert d["name"] == "Serialize Test"
        assert "created_at" in d
        assert "updated_at" in d

    def test_session_from_dict(self, session_manager):
        s = session_manager.create_session(name="Original")
        d = s.to_dict()

        from data_ai.core.session import Session

        restored = Session.from_dict(d)
        assert restored.id == s.id
        assert restored.name == s.name
