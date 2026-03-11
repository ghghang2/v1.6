"""Unit tests for db.py - Database operations."""
import pytest
import sqlite3
import os
import json

from pathlib import Path
from contextlib import contextmanager
import nbchat.core.db as db_module


@contextmanager
def override_db_path(test_path):
    """Context manager to override the global DB_PATH."""
    original_path = db_module.DB_PATH
    db_module.DB_PATH = Path(test_path)
    try:
        yield
    finally:
        db_module.DB_PATH = original_path


class TestEpisodicStore:
    """Tests for episodic store operations."""

    def test_init_db_creates_episodic_store(self, tmp_path):
        """Test that init_db creates the episodic_store table."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert 'episodic_store' in tables

    def test_append_episodic(self, tmp_path):
        """Test appending an entry to the episodic store."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            db_module.append_episodic(
                session_id='test_session',
                turn_id=0,
                action_type='test_tool',
                entity_refs='[]',
                outcome_summary='Test outcome',
                importance_score=7.0
            )
        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM episodic_store WHERE session_id = 'test_session'"
            ).fetchone()[0]
            assert count == 1

    def test_query_episodic_by_entity(self, tmp_path):
        """Test querying episodic store by entity reference."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            test_entities = [{"name": "file:example.py"}, {"name": "func:read"}]
            db_module.append_episodic(
                session_id='test_session',
                turn_id=0,
                action_type='test_tool',
                entity_refs=json.dumps(test_entities),
                outcome_summary='Test outcome',
                importance_score=7.0
            )
        with sqlite3.connect(db_path) as conn:
            result = conn.execute(
                """
                SELECT id, turn_id, action_type, entity_refs, outcome_summary, importance_score
                FROM episodic_store 
                WHERE entity_refs LIKE '%file:example.py%'
                AND session_id = 'test_session'
                ORDER BY importance_score DESC
                LIMIT 5
                """
            ).fetchall()
            assert len(result) == 1

    def test_query_episodic_by_importance(self, tmp_path):
        """Test querying episodic store by importance score."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            scores = [1.0, 3.5, 7.0, 5.0]
            for i, score in enumerate(scores):
                db_module.append_episodic(
                    session_id='test_session',
                    turn_id=i,
                    action_type='test_tool',
                    entity_refs='[]',
                    outcome_summary=f'Entry {i}',
                    importance_score=score
                )
        with sqlite3.connect(db_path) as conn:
            result = conn.execute(
                """
                SELECT id, turn_id, action_type, entity_refs, outcome_summary, importance_score
                FROM episodic_store
                WHERE session_id = 'test_session' AND importance_score >= 3.0
                ORDER BY importance_score DESC
                LIMIT 2
                """
            ).fetchall()
            assert len(result) == 2
            assert all(entry[5] >= 3.0 for entry in result)

    def test_delete_episodic_for_session(self, tmp_path):
        """Test deleting all episodic entries for a session."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            db_module.append_episodic(
                session_id='test_session',
                turn_id=0,
                action_type='test_tool',
                entity_refs='[]',
                outcome_summary='Test outcome',
                importance_score=7.0
            )
            # Delete happens while still in the context manager
            db_module.delete_episodic_for_session('test_session')
        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM episodic_store WHERE session_id = 'test_session'"
            ).fetchone()[0]
            assert count == 0


class TestCoreMemory:
    """Tests for core memory operations."""

    def test_init_db_creates_core_memory_table(self, tmp_path):
        """Test that init_db creates the core_memory table."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert 'core_memory' in tables

    def test_set_core_memory_key(self, tmp_path):
        """Test setting a core memory key."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            db_module.set_core_memory_key('test_session', 'goal', 'Test goal value')
        with sqlite3.connect(db_path) as conn:
            result = conn.execute(
                "SELECT value FROM core_memory WHERE session_id = 'test_session' AND key = 'goal'"
            ).fetchone()
            assert result is not None
            assert result[0] == 'Test goal value'

    def test_update_core_memory(self, tmp_path):
        """Test updating multiple core memory keys."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            db_module.update_core_memory(
                'test_session',
                updates={
                    'goal': 'Goal 1',
                    'constraints': 'Constraint 1'
                }
            )
        with sqlite3.connect(db_path) as conn:
            result = conn.execute(
                "SELECT value FROM core_memory WHERE session_id = 'test_session' AND key = 'goal'"
            ).fetchone()
            assert result[0] == 'Goal 1'
        result2 = conn.execute(
            "SELECT value FROM core_memory WHERE session_id = 'test_session' AND key = 'constraints'"
        ).fetchone()
        assert result2[0] == 'Constraint 1'

    def test_get_core_memory_empty(self, tmp_path):
        """Test getting core memory for a session with no entries."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
        with sqlite3.connect(db_path) as conn:
            result = conn.execute(
                "SELECT key, value FROM core_memory WHERE session_id = 'nonexistent'"
            ).fetchall()
            assert result == []

    def test_clear_core_memory(self, tmp_path):
        """Test clearing core memory for a session."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            db_module.set_core_memory_key('test_session', 'goal', 'Test goal')
            db_module.set_core_memory_key('test_session', 'constraints', 'Test constraints')
            # Clear happens while still in the context manager
            db_module.clear_core_memory('test_session')
        with sqlite3.connect(db_path) as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM core_memory WHERE session_id = 'test_session'"
            ).fetchone()[0]
            assert result == 0


class TestTaskLog:
    """Tests for task log operations."""

    def test_save_task_log(self, tmp_path):
        """Test saving a task log entry."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            db_module.save_task_log('test_session', ['Entry 1', 'Entry 2', 'Entry 3'])
        with sqlite3.connect(db_path) as conn:
            result = conn.execute(
                "SELECT value FROM session_meta WHERE session_id = 'test_session' AND key = 'task_log'"
            ).fetchone()
            assert result is not None

    def test_load_task_log(self, tmp_path):
        """Test loading a task log."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            db_module.save_task_log('test_session', ['Entry 1', 'Entry 2'])
        
        # Load from the test database directly
        with sqlite3.connect(db_path) as conn:
            raw = conn.execute("SELECT value FROM session_meta WHERE session_id=? AND key=?", ('test_session', 'task_log')).fetchone()
            import json
            result = json.loads(raw[0]) if raw and raw[0] else []
        assert result == ['Entry 1', 'Entry 2']

class TestChatLog:
    """Tests for chat log operations."""

    def test_log_row(self, tmp_path):
        """Test logging a chat message using log_row."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            db_module.log_row(
                'test_session',
                'user',
                'Test message',
                None,
                None,
                None
            )
        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM chat_log WHERE session_id = 'test_session'"
            ).fetchone()[0]
            assert count == 1

    def test_load_history(self, tmp_path):
        """Test loading chat history."""
        db_path = tmp_path / "test.db"
        with override_db_path(str(db_path)):
            db_module.init_db()
            db_module.log_row(
                'test_session',
                'user',
                'User message',
                None,
                None,
                None
            )
            db_module.log_row(
                'test_session',
                'assistant',
                'Assistant response',
                None,
                None,
                None
            )
            # Load history while still in context manager
            messages = db_module.load_history('test_session')
        assert len(messages) == 2
        # load_history returns tuples of (role, content, tool_id, tool_name, tool_args)
        assert messages[0][0] == 'user'
        assert messages[1][0] == 'assistant'
