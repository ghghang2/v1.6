"""Token counting and history compaction for managing context size."""
from __future__ import annotations
import threading
from typing import List, Tuple
from nbchat.ui.chat_builder import build_messages
from nbchat.core.client import get_client


class CompactionEngine:
    """Compacts chat history when token count exceeds threshold."""

    def __init__(self, threshold: int, tail_messages: int = 5,
                 summary_prompt: str = None, summary_model: str = None,
                 system_prompt: str = ""):
        self.threshold = threshold
        self.tail_messages = tail_messages
        self.summary_prompt = summary_prompt or (
            "Summarize the conversation so far, focusing on:\n"
            "1. Key decisions made\n"
            "2. Important file paths and edits\n"
            "3. Tool calls and their outcomes (summarize large outputs)\n"
            "4. Next steps planned\n"
            "Keep it concise but preserve teach-a-man-to-fish information."
        )
        self.summary_model = summary_model
        self.system_prompt = system_prompt
        self._cache: dict = {}
        self._cache_lock = threading.Lock()

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def total_tokens(self, history: List[Tuple[str, str, str, str, str]]) -> int:
        total = 0
        for role, content, tool_id, tool_name, tool_args in history:
            msg_hash = hash((content, tool_args))
            with self._cache_lock:
                if msg_hash in self._cache:
                    total += self._cache[msg_hash]
                    continue
            msg_tokens = self._estimate_tokens(content)
            if tool_args:
                msg_tokens += self._estimate_tokens(tool_args)
            with self._cache_lock:
                self._cache[msg_hash] = msg_tokens
            total += msg_tokens
        return total

    def should_compact(self, history: List[Tuple[str, str, str, str, str]]) -> bool:
        return self.total_tokens(history) >= self.threshold

    def compact_history(self, history: List[Tuple[str, str, str, str, str]]) -> List[Tuple[str, str, str, str, str]]:
        if len(history) <= self.tail_messages:
            return history

        tail_start = len(history) - self.tail_messages
        while tail_start > 0 and history[tail_start][0] in ("tool", "analysis", "assistant_full"):
            tail_start -= 1

        if tail_start == 0:
            return history

        older = history[:tail_start]
        tail = history[tail_start:]

        messages = build_messages(older, "")
        messages.append({"role": "user", "content": self.summary_prompt})

        try:
            client = get_client()
            response = client.chat.completions.create(
                model=self.summary_model,
                messages=messages,
                max_tokens=4096,
            )
        except Exception as e:
            raise RuntimeError(f"Summarization failed: {e}")

        with self._cache_lock:
            self._cache.clear()

        summary_text = response.choices[0].message.content
        return [("compacted", summary_text, "", "", "")] + tail


__all__ = ["CompactionEngine"]