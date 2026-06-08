"""
DATA-AI Session + Memory Integration Tests

Tests session management and memory system integration.
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


# ─── Session + Memory Integration ────────────────────────────────────────────


class TestSessionMemoryIntegration:
    """Test session and memory system integration."""

    def test_session_manager_singleton(self):
        from data_ai.core.session import get_session_manager

        mgr1 = get_session_manager()
        mgr2 = get_session_manager()
        assert mgr1 is mgr2

    def test_create_session_returns_session(self, session_manager):
        session = session_manager.create_session(name="Test")
        assert session is not None
        assert isinstance(session.id, str)
        assert session.name == "Test"
        assert session.is_active is True

    def test_multiple_sessions_independent(self, session_manager):
        s1 = session_manager.create_session(name="Session 1")
        s2 = session_manager.create_session(name="Session 2")

        session_manager.add_message("user", "Message for S1", session_id=s1.id)
        session_manager.add_message("user", "Message for S2", session_id=s2.id)

        msgs1 = session_manager.get_messages(session_id=s1.id)
        msgs2 = session_manager.get_messages(session_id=s2.id)

        assert len(msgs1) == 1
        assert len(msgs2) == 1
        assert msgs1[0].content == "Message for S1"
        assert msgs2[0].content == "Message for S2"

    def test_session_switch_preserves_messages(self, session_manager):
        s1 = session_manager.create_session(name="First")
        session_manager.add_message("user", "Hello S1", session_id=s1.id)

        s2 = session_manager.create_session(name="Second")
        session_manager.add_message("user", "Hello S2", session_id=s2.id)

        # Switch back to S1
        session_manager.switch_session(s1.id)
        active = session_manager.get_active_session()
        assert active.id == s1.id

        msgs = session_manager.get_messages(session_id=s1.id)
        assert len(msgs) == 1
        assert msgs[0].content == "Hello S1"

    def test_session_delete_clears_data(self, session_manager):
        s = session_manager.create_session(name="Temporary")
        session_manager.add_message("user", "Will be deleted", session_id=s.id)

        deleted = session_manager.delete_session(s.id)
        assert deleted is True
        assert session_manager.get_session(s.id) is None

    def test_session_rename(self, session_manager):
        s = session_manager.create_session(name="Old Name")
        result = session_manager.rename_session(s.id, "New Name")
        assert result is True
        assert session_manager.get_session(s.id).name == "New Name"

    def test_session_messages_limit(self, session_manager):
        s = session_manager.create_session(name="Limited")
        for i in range(20):
            session_manager.add_message("user", f"Message {i}", session_id=s.id)

        last_5 = session_manager.get_messages(session_id=s.id, limit=5)
        assert len(last_5) == 5
        assert last_5[-1].content == "Message 19"

    def test_clear_session_messages(self, session_manager):
        s = session_manager.create_session(name="Clearable")
        for i in range(5):
            session_manager.add_message("user", f"Msg {i}", session_id=s.id)

        session_manager.clear_messages(session_id=s.id)
        msgs = session_manager.get_messages(session_id=s.id)
        assert len(msgs) == 0

    def test_session_metadata(self, session_manager):
        s = session_manager.create_session(
            name="With Metadata",
            metadata={"project": "test", "version": "1.0"},
        )
        assert s.metadata["project"] == "test"
        assert s.metadata["version"] == "1.0"


# ─── Session Persistence Integration ──────────────────────────────────────────


class TestSessionPersistence:
    """Test session persistence with storage."""

    def test_save_and_load(self, tmp_path):
        from data_ai.core.session import SessionManager

        mgr = SessionManager()
        mgr._sessions.clear()
        mgr._active_session_id = None
        mgr.initialize(storage_path=tmp_path)

        s = mgr.create_session(name="Persistent")
        mgr.add_message("user", "Saved message", session_id=s.id)

        # Verify file was created
        session_file = tmp_path / f"{s.id}.json"
        assert session_file.exists()

        # Reload
        mgr2 = SessionManager()
        mgr2._sessions.clear()
        mgr2._active_session_id = None
        mgr2.initialize(storage_path=tmp_path)

        loaded = mgr2.get_session(s.id)
        assert loaded is not None
        assert loaded.name == "Persistent"

        msgs = mgr2.get_messages(session_id=s.id)
        assert len(msgs) == 1
        assert msgs[0].content == "Saved message"

    def test_active_session_restored(self, tmp_path):
        from data_ai.core.session import SessionManager

        mgr = SessionManager()
        mgr._sessions.clear()
        mgr._active_session_id = None
        mgr.initialize(storage_path=tmp_path)

        s = mgr.create_session(name="Active Session")
        assert s.is_active is True

        # Reload
        mgr2 = SessionManager()
        mgr2._sessions.clear()
        mgr2._active_session_id = None
        mgr2.initialize(storage_path=tmp_path)

        active = mgr2.get_active_session()
        assert active is not None
        assert active.id == s.id


# ─── MemoryConfig Integration ────────────────────────────────────────────────


class TestMemoryConfigIntegration:
    """Test MemoryConfig with session management."""

    def test_memory_config_with_settings(self):
        from data_ai.utils.config import get_settings

        settings = get_settings()
        assert hasattr(settings, "memory")
        assert settings.memory.enabled is True

    def test_memory_config_custom(self):
        from data_ai.utils.config import MemoryConfig

        config = MemoryConfig(
            enabled=True,
            keep_recent_messages=100,
            summary_interval=20,
        )
        assert config.keep_recent_messages == 100
        assert config.summary_interval == 20
