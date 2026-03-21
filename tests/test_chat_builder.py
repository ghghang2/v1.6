"""Tests for nbchat.ui.chat_builder.

Run from repo root:
    pytest tests/test_chat_builder.py -v

Tests verify the KV-cache alignment contract:
  messages[0]["content"] == system_prompt  (NEVER modified)
  volatile context (L1/L2/task_log) goes into messages[1] as a user turn
  actual conversation starts at messages[2] or messages[3]
"""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# The module has no heavyweight dependencies so we can import directly.
# ---------------------------------------------------------------------------
from nbchat.ui.chat_builder import build_messages, _CTX_LABEL, _CTX_ACK

SYSTEM = "You are a helpful assistant."


def _row(role, content="", tool_id="", tool_name="", tool_args="", error_flag=0):
    """Convenience factory for canonical 6-tuples."""
    return (role, content, tool_id, tool_name, tool_args, error_flag)


# ---------------------------------------------------------------------------
# 1. KV-cache alignment: messages[0] is always exactly system_prompt
# ---------------------------------------------------------------------------

class TestSystemPromptUnmodified:
    """The core caching contract: messages[0]["content"] == system_prompt."""

    def test_no_history_no_task_log(self):
        msgs = build_messages([], SYSTEM)
        assert msgs[0] == {"role": "system", "content": SYSTEM}

    def test_with_task_log(self):
        msgs = build_messages([], SYSTEM, task_log=["tool_a() -> ok"])
        assert msgs[0]["content"] == SYSTEM

    def test_with_leading_system_row(self):
        history = [_row("system", "[L1 CORE MEMORY]\nGoal: fix bug\n[END]")]
        msgs = build_messages(history, SYSTEM)
        assert msgs[0]["content"] == SYSTEM

    def test_with_l1_and_l2_and_prior(self):
        history = [
            _row("system", "[CORE MEMORY]\nGoal: refactor\n[END CORE MEMORY]"),
            _row("system", "[EPISODIC]\nbash: ran tests\n[END EPISODIC]"),
            _row("system", "[PRIOR CONTEXT]\nTurn 1...\n[END PRIOR CONTEXT]"),
            _row("user", "Hello"),
        ]
        msgs = build_messages(history, SYSTEM, task_log=["bash() -> ok"])
        assert msgs[0]["content"] == SYSTEM

    def test_system_prompt_not_mutated_across_calls(self):
        """Repeated calls must return the identical string object (or equal)."""
        history = [_row("user", "msg")]
        msgs1 = build_messages(history, SYSTEM, task_log=["a"])
        msgs2 = build_messages(history, SYSTEM, task_log=["a", "b"])
        assert msgs1[0]["content"] == SYSTEM
        assert msgs2[0]["content"] == SYSTEM


# ---------------------------------------------------------------------------
# 2. Volatile context turn (messages[1] / messages[2])
# ---------------------------------------------------------------------------

class TestVolatileContextTurn:
    def test_no_volatile_no_context_turn(self):
        """Fresh session with no task log and no system rows → no context turn."""
        msgs = build_messages([_row("user", "hi")], SYSTEM)
        assert msgs[1]["role"] == "user"
        assert _CTX_LABEL not in msgs[1]["content"]

    def test_task_log_creates_context_turn(self):
        msgs = build_messages([], SYSTEM, task_log=["bash() -> exit 0"])
        assert len(msgs) >= 3
        assert msgs[1]["role"] == "user"
        assert _CTX_LABEL in msgs[1]["content"]
        assert "bash() -> exit 0" in msgs[1]["content"]

    def test_context_turn_followed_by_ack(self):
        msgs = build_messages([], SYSTEM, task_log=["step1"])
        assert msgs[2]["role"] == "assistant"
        assert msgs[2]["content"] == _CTX_ACK

    def test_l1_block_in_context_turn(self):
        l1 = "[CORE MEMORY]\nGoal: test\n[END CORE MEMORY]"
        history = [_row("system", l1)]
        msgs = build_messages(history, SYSTEM)
        assert msgs[1]["role"] == "user"
        assert "CORE MEMORY" in msgs[1]["content"]
        assert l1 not in msgs[0]["content"]   # NOT in system prompt

    def test_multiple_system_blocks_all_in_context_turn(self):
        l1 = "[CORE MEMORY]...[END CORE MEMORY]"
        l2 = "[EPISODIC]...[END EPISODIC]"
        prior = "[PRIOR CONTEXT]...[END PRIOR CONTEXT]"
        history = [
            _row("system", l1),
            _row("system", l2),
            _row("system", prior),
            _row("user", "hello"),
        ]
        msgs = build_messages(history, SYSTEM)
        ctx_content = msgs[1]["content"]
        assert "CORE MEMORY" in ctx_content
        assert "EPISODIC" in ctx_content
        assert "PRIOR CONTEXT" in ctx_content

    def test_task_log_capped_at_20(self):
        log = [f"step_{i}" for i in range(30)]
        msgs = build_messages([], SYSTEM, task_log=log)
        ctx = msgs[1]["content"]
        # Only the last 20 entries should appear
        assert "step_29" in ctx
        assert "step_9" not in ctx   # step_9 is entry 9, excluded (last 20 = 10..29)

    def test_empty_task_log_no_context_turn(self):
        msgs = build_messages([_row("user", "hi")], SYSTEM, task_log=[])
        assert msgs[1]["role"] == "user"
        assert _CTX_LABEL not in msgs[1]["content"]


# ---------------------------------------------------------------------------
# 3. Analysis rows skipped
# ---------------------------------------------------------------------------

class TestAnalysisRowsSkipped:
    def test_analysis_not_in_messages(self):
        history = [
            _row("user", "task"),
            _row("analysis", "I should call bash first"),
            _row("assistant", "done"),
        ]
        msgs = build_messages(history, SYSTEM)
        roles = [m["role"] for m in msgs]
        assert "analysis" not in roles

    def test_analysis_content_not_in_messages(self):
        history = [
            _row("user", "task"),
            _row("analysis", "SECRET_REASONING"),
            _row("assistant", "response"),
        ]
        msgs = build_messages(history, SYSTEM)
        full_text = json.dumps(msgs)
        assert "SECRET_REASONING" not in full_text

    def test_multiple_analysis_rows_all_skipped(self):
        history = [
            _row("user", "q"),
            _row("analysis", "reasoning_1"),
            _row("analysis", "reasoning_2"),
            _row("assistant", "a"),
        ]
        msgs = build_messages(history, SYSTEM)
        for m in msgs:
            assert "reasoning_" not in m.get("content", "")


# ---------------------------------------------------------------------------
# 4. User, assistant, tool roles
# ---------------------------------------------------------------------------

class TestConversationRoles:
    def test_user_message(self):
        history = [_row("user", "hello")]
        msgs = build_messages(history, SYSTEM)
        user_msgs = [m for m in msgs if m["role"] == "user"]
        # Filter out the context note if present
        real_user = [m for m in user_msgs if _CTX_LABEL not in m.get("content", "")]
        assert any(m["content"] == "hello" for m in real_user)

    def test_assistant_plain_message(self):
        history = [
            _row("user", "q"),
            _row("assistant", "answer"),
        ]
        msgs = build_messages(history, SYSTEM)
        ass = [m for m in msgs if m["role"] == "assistant" and m.get("content") == "answer"]
        assert ass

    def test_assistant_with_tool_call(self):
        history = [
            _row("user", "q"),
            _row("assistant", "", "call_1", "bash", '{"cmd":"ls"}'),
        ]
        msgs = build_messages(history, SYSTEM)
        tool_ass = [
            m for m in msgs
            if m.get("role") == "assistant" and m.get("tool_calls")
        ]
        assert len(tool_ass) == 1
        tc = tool_ass[0]["tool_calls"][0]
        assert tc["id"] == "call_1"
        assert tc["function"]["name"] == "bash"
        assert tc["function"]["arguments"] == '{"cmd":"ls"}'

    def test_tool_result_message(self):
        history = [
            _row("user", "q"),
            _row("assistant", "", "call_1", "bash", '{"cmd":"ls"}'),
            _row("tool", "file1.txt\nfile2.txt", "call_1", "bash", '{"cmd":"ls"}'),
        ]
        msgs = build_messages(history, SYSTEM)
        tool_msgs = [m for m in msgs if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "call_1"
        assert "file1.txt" in tool_msgs[0]["content"]

    def test_assistant_full_reconstruction(self):
        full = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "tc_1",
                "type": "function",
                "function": {"name": "grep", "arguments": '{"pattern":"TODO"}'},
            }],
        }
        history = [
            _row("user", "q"),
            _row("assistant_full", "", "full", "full", json.dumps(full)),
        ]
        msgs = build_messages(history, SYSTEM)
        reconstructed = [
            m for m in msgs
            if m.get("role") == "assistant" and m.get("tool_calls")
        ]
        assert len(reconstructed) == 1
        assert reconstructed[0]["tool_calls"][0]["id"] == "tc_1"

    def test_assistant_full_reasoning_content_stripped(self):
        full = {
            "role": "assistant",
            "content": "response",
            "reasoning_content": "INTERNAL_REASONING",
            "tool_calls": None,
        }
        history = [
            _row("user", "q"),
            _row("assistant_full", "", "full", "full", json.dumps(full)),
        ]
        msgs = build_messages(history, SYSTEM)
        full_text = json.dumps(msgs)
        assert "INTERNAL_REASONING" not in full_text

    def test_assistant_full_malformed_json_falls_back(self):
        history = [
            _row("user", "q"),
            _row("assistant_full", "fallback text", "full", "full", "NOTJSON"),
        ]
        msgs = build_messages(history, SYSTEM)
        ass = [m for m in msgs if m.get("role") == "assistant"]
        # Filter out ack
        real_ass = [m for m in ass if m.get("content") != _CTX_ACK]
        assert any(m.get("content") == "fallback text" for m in real_ass)


# ---------------------------------------------------------------------------
# 5. Mid-conversation system rows demoted
# ---------------------------------------------------------------------------

class TestMidConversationSystemRows:
    def test_mid_system_row_demoted_to_user(self):
        history = [
            _row("user", "first message"),
            _row("assistant", "response"),
            _row("system", "late system injection"),
            _row("user", "second message"),
        ]
        msgs = build_messages(history, SYSTEM)
        system_msgs = [m for m in msgs if m["role"] == "system"]
        assert len(system_msgs) == 1  # only messages[0]
        context_notes = [
            m for m in msgs
            if m.get("role") == "user" and "[CONTEXT NOTE]" in m.get("content", "")
        ]
        assert len(context_notes) == 1
        assert "late system injection" in context_notes[0]["content"]

    def test_leading_system_rows_not_demoted(self):
        history = [
            _row("system", "L1 block"),
            _row("system", "L2 block"),
            _row("user", "hello"),
        ]
        msgs = build_messages(history, SYSTEM)
        context_notes = [
            m for m in msgs
            if m.get("role") == "user" and "[CONTEXT NOTE]" in m.get("content", "")
        ]
        assert len(context_notes) == 0


# ---------------------------------------------------------------------------
# 6. Empty history and edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_history_produces_only_system(self):
        msgs = build_messages([], SYSTEM)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "system"

    def test_only_system_rows_produces_only_system_plus_context(self):
        history = [_row("system", "L1"), _row("system", "L2")]
        msgs = build_messages(history, SYSTEM)
        # system + context user + ack
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert msgs[2]["role"] == "assistant"
        assert len(msgs) == 3

    def test_assistant_tool_call_content_none_not_empty_string(self):
        history = [
            _row("user", "q"),
            _row("assistant", "", "call_1", "bash", "{}"),
        ]
        msgs = build_messages(history, SYSTEM)
        tool_ass = [m for m in msgs if m.get("tool_calls")]
        assert tool_ass[0]["content"] is None

    def test_no_extra_system_messages_ever(self):
        history = [
            _row("system", "L1"),
            _row("user", "a"),
            _row("assistant", "b"),
            _row("system", "late"),
            _row("user", "c"),
        ]
        msgs = build_messages(history, SYSTEM, task_log=["step"])
        system_msgs = [m for m in msgs if m["role"] == "system"]
        assert len(system_msgs) == 1

    def test_multi_turn_conversation_order(self):
        history = [
            _row("user", "turn1"),
            _row("assistant", "resp1"),
            _row("user", "turn2"),
            _row("assistant", "resp2"),
        ]
        msgs = build_messages(history, SYSTEM)
        # Strip system + optional context turns
        conv = [m for m in msgs if m["role"] not in ("system",)
                and _CTX_LABEL not in m.get("content", "")
                and m.get("content") != _CTX_ACK]
        assert conv[0]["content"] == "turn1"
        assert conv[1]["content"] == "resp1"
        assert conv[2]["content"] == "turn2"
        assert conv[3]["content"] == "resp2"