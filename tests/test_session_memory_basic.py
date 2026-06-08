"""
DATA-AI Memory Explorer Tests

Test SessionManager (create, switch, delete, rename) and MemoryConfig
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
    """Provide a fresh SessionManager for each test."""
    from data_ai.core.session import SessionManager

    mgr = SessionManager()
    # Clear any pre-existing sessions
    mgr._sessions.clear()
    mgr._active_session_id = None
    yield mgr
    # Cleanup
    mgr._sessions.clear()
    mgr._active_session_id = None


# ─── MemoryConfig Tests ──────────────────────────────────────────────────────


class TestMemoryConfig:
    """MemoryConfig tests."""

    def test_defaults(self):
        from data_ai.utils.config import MemoryConfig

        config = MemoryConfig()
        assert config.enabled is True
        assert config.keep_recent_messages > 0
        assert config.summary_interval > 0


# ─── SessionManager Tests ────────────────────────────────────────────────────


class TestSessionManager:
    """SessionManager tests."""

    def test_create_session(self, session_manager):
        session = session_manager.create_session(name="Test Session")
        assert session.name == "Test Session"
        assert session.id is not None
        assert len(session.id) > 0
        assert session.is_active is True

    def test_create_session_default_name(self, session_manager):
        session = session_manager.create_session()
        assert session.name.startswith("Session-")

    def test_create_multiple_sessions(self, session_manager):
        s1 = session_manager.create_session(name="S1")
        s2 = session_manager.create_session(name="S2")
        assert s1.id != s2.id
        sessions = session_manager.list_sessions()
        assert len(sessions) == 2

    def test_switch_session(self, session_manager):
        s1 = session_manager.create_session(name="S1")
        s2 = session_manager.create_session(name="S2")
        # After creating s2, it should be active
        assert session_manager._active_session_id == s2.id

        # Switch back to s1
        switched = session_manager.switch_session(s1.id)
        assert switched.id == s1.id
        assert session_manager._active_session_id == s1.id

    def test_switch_nonexistent_session(self, session_manager):
        from data_ai.utils.exceptions import SessionException

        with pytest.raises(SessionException):
            session_manager.switch_session("nonexistent")

    def test_get_session(self, session_manager):
        s1 = session_manager.create_session(name="S1")
        fetched = session_manager.get_session(s1.id)
        assert fetched is not None
        assert fetched.name == "S1"

    def test_get_active_session(self, session_manager):
        s = session_manager.create_session(name="Active")
        active = session_manager.get_active_session()
        assert active is not None
        assert active.id == s.id

    def test_get_active_session_none(self, session_manager):
        active = session_manager.get_active_session()
        assert active is None

    def test_delete_session(self, session_manager):
        s1 = session_manager.create_session(name="S1")
        session_manager.create_session(name="S2")

        deleted = session_manager.delete_session(s1.id)
        assert deleted is True
        assert session_manager.get_session(s1.id) is None
        assert len(session_manager.list_sessions()) == 1

    def test_delete_nonexistent_session(self, session_manager):
        deleted = session_manager.delete_session("nonexistent")
        assert deleted is False

    def test_delete_active_session(self, session_manager):
        s = session_manager.create_session(name="Active")
        deleted = session_manager.delete_session(s.id)
        assert deleted is True
        assert session_manager._active_session_id is None

    def test_rename_session(self, session_manager):
        s = session_manager.create_session(name="Old Name")
        renamed = session_manager.rename_session(s.id, "New Name")
        assert renamed is True
        assert session_manager.get_session(s.id).name == "New Name"

    def test_rename_nonexistent_session(self, session_manager):
        renamed = session_manager.rename_session("nonexistent", "New")
        assert renamed is False

    def test_add_message(self, session_manager):
        s = session_manager.create_session(name="Chat")
        session_manager.add_message("user", "Hello", session_id=s.id)
        session_manager.add_message("assistant", "Hi!", session_id=s.id)

        messages = session_manager.get_messages(session_id=s.id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].content == "Hi!"

    def test_get_messages_with_limit(self, session_manager):
        s = session_manager.create_session(name="Chat")
        for i in range(10):
            session_manager.add_message("user", f"msg {i}", session_id=s.id)

        messages = session_manager.get_messages(session_id=s.id, limit=3)
        assert len(messages) == 3

    def test_clear_messages(self, session_manager):
        s = session_manager.create_session(name="Chat")
        session_manager.add_message("user", "Hello", session_id=s.id)
        session_manager.clear_messages(session_id=s.id)
        messages = session_manager.get_messages(session_id=s.id)
        assert len(messages) == 0

    def test_list_sessions_sorted(self, session_manager):
        session_manager.create_session(name="First")
        s2 = session_manager.create_session(name="Second")

        sessions = session_manager.list_sessions()
        # Most recently updated first
        assert sessions[0].id == s2.id

    def test_session_persistence(self, tmp_path):
        from data_ai.core.session import SessionManager

        mgr = SessionManager()
        mgr._sessions.clear()
        mgr._active_session_id = None
        mgr.initialize(storage_path=tmp_path)

        s = mgr.create_session(name="Persisted")
        mgr.add_message("user", "test message", session_id=s.id)

        # Create a new manager and load from storage
        mgr2 = SessionManager()
        mgr2._sessions.clear()
        mgr2._active_session_id = None
        mgr2.initialize(storage_path=tmp_path)

        loaded = mgr2.get_session(s.id)
        assert loaded is not None
        assert loaded.name == "Persisted"
        messages = mgr2.get_messages(session_id=s.id)
        assert len(messages) == 1
        assert messages[0].content == "test message"
