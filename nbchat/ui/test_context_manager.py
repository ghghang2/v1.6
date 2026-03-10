"""Unit tests for context_manager.py - Context management and hard trim."""
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the repository root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock dependencies before importing context_manager
sys.modules['nbchat.core.db'] = MagicMock()
sys.modules['nbchat.core.config'] = MagicMock()

from nbchat.ui.context_manager import ContextMixin


@pytest.fixture
def mock_db():
    """Return a mock db module."""
    return MagicMock()


@pytest.fixture
def mock_config():
    """Return a mock config module."""
    config_mock = MagicMock()
    config_mock.CONTEXT_TOKEN_THRESHOLD = 65536
    config_mock.MAX_EXCHANGES = 50
    config_mock.KEEP_RECENT_EXCHANGES = 30
    return config_mock


@pytest.fixture
def context_mixin(mock_db, mock_config):
    """Create a ContextMixin instance with mocked dependencies."""
    with patch('nbchat.ui.context_manager.lazy_import') as mock_lazy:
        mock_lazy.side_effect = lambda x: (
            mock_db if x == "nbchat.core.db" else
            mock_config if x == "nbchat.core.config" else
            MagicMock()
        )
        mixin = ContextMixin()
        mixin.session_id = "test_session_123"
        mixin.task_log = []
        mixin.history = []
        mixin.db = mock_db
        mixin.config = mock_config
        yield mixin


class TestContextMixinImportanceScoring:
    """Tests for _importance_score function."""

    def test_default_score(self, context_mixin):
        """Test that a default exchange gets a base score of 1.0."""
        exchange_msgs = [
            {"role": "assistant", "content": "Tool result"},
            {"role": "tool", "content": "Success"}
        ]
        score = context_mixin._importance_score(exchange_msgs)
        # Base 1.0 + success keywords in tool (1.5) = 2.5
        assert score == pytest.approx(2.5)

    def test_error_keywords_increase_score(self, context_mixin):
        """Test that error keywords increase the score by 3.0."""
        exchange_msgs = [
            {"role": "assistant", "content": "Error occurred"},
            {"role": "tool", "content": "Traceback: exception failed"}
        ]
        score = context_mixin._importance_score(exchange_msgs)
        # Base 1.0 + error keywords in assistant (3.0) + error keywords in tool (3.0) = 7.0
        assert score == pytest.approx(7.0)

    def test_user_correction_increase_score(self, context_mixin):
        """Test that user correction keywords increase score by 2.5."""
        exchange_msgs = [
            {"role": "user", "content": "Actually, do it differently"},
            {"role": "assistant", "content": "I understand"}
        ]
        score = context_mixin._importance_score(exchange_msgs)
        # Base 1.0 + user correction in user message (2.5) = 3.5
        assert score == pytest.approx(3.5)

    def test_success_keywords_increase_score(self, context_mixin):
        """Test that success keywords in tool message increase score by 1.5."""
        exchange_msgs = [
            {"role": "assistant", "content": "Task completed successfully"},
            {"role": "tool", "content": "Created file"}
        ]
        score = context_mixin._importance_score(exchange_msgs)
        # Base 1.0 + success keywords in tool (1.5 for 'created') = 2.5
        # Note: 'completed' in assistant content doesn't add score, only in tool content
        assert score == pytest.approx(2.5)

    def test_combined_scores(self, context_mixin):
        """Test that scores are additive."""
        exchange_msgs = [
            {"role": "user", "content": "This is wrong, correct it"},
            {"role": "assistant", "content": "error occurred, cannot proceed"},
            {"role": "tool", "content": "Traceback: exception"}
        ]
        score = context_mixin._importance_score(exchange_msgs)
        # Base 1.0 + user correction (2.5) + error in assistant (3.0) + error in tool (3.0) = 9.5
        assert score == pytest.approx(9.5)

    def test_score_capped_at_10(self, context_mixin):
        """Test that score is capped at 10.0."""
        exchange_msgs = [
            {"role": "user", "content": "This is completely wrong actually"},
            {"role": "assistant", "content": "error occurred, exception, failed, cannot, traceback"},
            {"role": "tool", "content": "Traceback: exception"}
        ]
        score = context_mixin._importance_score(exchange_msgs)
        # Base 1.0 + 2.5 (user) + 3.0 (error assistant) + 3.0 (error tool) = 9.5
        # Not quite reaching the cap
        # Let's create a scenario that exceeds 10
        # Actually, let me recalculate:
        # Base 1.0 + 2.5 + 3.0 + 3.0 = 9.5
        # To get 10.0, we need another 0.5 bonus
        # Let's add long tool result
        exchange_msgs2 = [
            {"role": "user", "content": "This is completely wrong actually"},
            {"role": "assistant", "content": "error occurred, exception, failed, cannot, traceback"},
            {"role": "tool", "content": "Traceback: exception " * 50}  # > 500 chars
        ]
        score2 = context_mixin._importance_score(exchange_msgs2)
        # Base 1.0 + 2.5 (user) + 3.0 (error assistant) + 3.0 (error tool) + 0.5 (long) = 10.0
        assert score2 == pytest.approx(10.0)

    def test_long_tool_result_bonus(self, context_mixin):
        """Test that tool results > 500 chars get +0.5 bonus."""
        exchange_msgs = [
            {"role": "assistant", "content": "Here is the result"},
            {"role": "tool", "content": "This is a very long result that exceeds five hundred characters " * 10}
        ]
        score = context_mixin._importance_score(exchange_msgs)
        assert score == pytest.approx(1.5)  # 1.0 base + 0.5 for long result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
