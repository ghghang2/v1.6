"""ChatUI — main entry point.

Composes ContextMixin and ConversationMixin into a single widget-based
chat interface.  This file contains only widget creation, history
rendering, and event handling.  Context management lives in
context_manager.py and the conversation loop in conversation.py.
"""
from __future__ import annotations

import ipywidgets as widgets
import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import List, Tuple

from IPython.display import display

from nbchat.ui import chat_renderer as renderer
from nbchat.ui import chat_builder
from nbchat.ui.context_manager import ContextMixin
from nbchat.ui.conversation import ConversationMixin
from nbchat.ui.utils import changed_files
from nbchat.core.utils import lazy_import


class ChatUI(ContextMixin, ConversationMixin):
    """Chat interface with streaming, reasoning, and tool execution."""
    config = lazy_import("nbchat.core.config")

    MAX_TOOL_TURNS = config.MAX_TOOL_TURNS
    WINDOW_TURNS = config.WINDOW_TURNS
    MAX_VISIBLE_WIDGETS = 120

    def __init__(self):
        db = lazy_import("nbchat.core.db")
        db.init_db()

        config = lazy_import("nbchat.core.config")
        self.system_prompt = config.DEFAULT_SYSTEM_PROMPT
        self.model_name = config.MODEL_NAME

        self.session_id = str(uuid.uuid4())
        # Canonical row shape: (role, content, tool_id, tool_name, tool_args, error_flag)
        self.history: List[Tuple[str, str, str, str, str, int]] = []
        self.task_log: List[str] = []
        self._turn_summary_cache: dict = {}

        self._stop_streaming = False
        self._stream_thread = None
        # True while executor.run_tool() is in flight — used by the metrics
        # updater to keep proc green during tool execution when the LLM server
        # is idle between calls.
        self._tool_running = False

        # Initialise per-session compressor state for lossless learning.
        comp = lazy_import("nbchat.core.compressor")
        comp.init_session(self.session_id)

        self._create_widgets()
        self._start_metrics_updater()
        self._load_history()
        display(self.layout)
        self._inject_scroll_preservation()

    # ------------------------------------------------------------------
    # Scroll preservation
    # ------------------------------------------------------------------

    def _inject_scroll_preservation(self) -> None:
        """Inject a one-time JS MutationObserver that preserves scroll position."""
        from IPython.display import Javascript, display as ipy_display
        js = """
        (function() {
            function attach() {
                var el = document.querySelector('.nbchat-history');
                if (!el) { setTimeout(attach, 400); return; }
                if (el._nbchatObserver) return;

                var savedScroll = 0;
                el.addEventListener('scroll', function() {
                    savedScroll = el.scrollTop;
                }, { passive: true });

                el._nbchatObserver = new MutationObserver(function() {
                    requestAnimationFrame(function() {
                        el.scrollTop = savedScroll;
                    });
                });
                el._nbchatObserver.observe(el, { childList: true });
            }
            attach();
        })();
        """
        ipy_display(Javascript(js))

    # ------------------------------------------------------------------
    # Session state reset
    # ------------------------------------------------------------------

    def _reset_session_state(self) -> None:
        """Clear all per-session in-memory state and associated DB rows."""
        # Flush monitoring data for the departing session before clearing it.
        try:
            mon = lazy_import("nbchat.core.monitoring")
            db = lazy_import("nbchat.core.db")
            mon.flush_session_monitor(self.session_id, db)
        except Exception:
            pass
        self.history = []
        self.task_log = []
        self._turn_summary_cache = {}
        try:
            db = lazy_import("nbchat.core.db")
            db.clear_core_memory(self.session_id)
            db.delete_episodic_for_session(self.session_id)
        except Exception:
            pass
        # Clear session-local compressor state (lossless set, recent_compressed).
        try:
            comp = lazy_import("nbchat.core.compressor")
            comp.clear_session(self.session_id)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------

    def _create_widgets(self):
        db = lazy_import("nbchat.core.db")

        self.metrics_output = widgets.HTML(
            value="<i>Loading server status...</i>",
            layout=widgets.Layout(width="100%", border="1px solid gray", padding="10px"),
        )
        self.tools_output = widgets.HTML(
            layout=widgets.Layout(
                width="100%", border="1px solid lightgray", padding="2px"
            )
        )
        self.monitoring_output = widgets.HTML(
            value="<i>No monitoring data yet.</i>",
            layout=widgets.Layout(
                width="100%", border="1px solid lightgray", padding="4px"
            ),
        )
        self._refresh_tools_list()

        new_chat_btn = widgets.Button(
            description="+", button_style="primary",
            layout=widgets.Layout(width="100%"),
        )
        new_chat_btn.on_click(self._on_new_chat)

        options = list(db.get_session_ids())
        if self.session_id not in options:
            options.append(self.session_id)
        self.session_dropdown = widgets.Dropdown(
            options=options, value=self.session_id,
            layout=widgets.Layout(width="100%"),
        )
        self.session_dropdown.observe(self._on_session_change, names="value")

        sidebar = widgets.VBox([
            self.metrics_output,
            widgets.HTML("<hr>"),
            new_chat_btn,
            widgets.HTML("<hr>"),
            self.tools_output,
            widgets.HTML("<hr>"),
            self.monitoring_output,
            widgets.HTML("<hr>"),
            self.session_dropdown,
        ], layout=widgets.Layout(width="15%", border="1px solid lightgray"))

        self.chat_history = widgets.VBox([], layout=widgets.Layout(
            width="100%", height="100%", max_height="800px", overflow_y="auto",
            border="1px solid #ccc",
        ), _dom_classes=["nbchat-history"])
        self.input_text = widgets.Textarea(
            placeholder="...",
            layout=widgets.Layout(width="90%", min_height="50px", height="auto"),
            rows=2,
        )
        send_btn = widgets.Button(
            description="Send", button_style="success",
            layout=widgets.Layout(width="5%", padding="0", margin="0"),
        )
        stop_btn = widgets.Button(
            description="Stop", button_style="warning",
            layout=widgets.Layout(width="5%", padding="0", margin="0"),
        )
        send_btn.on_click(self._on_send)
        stop_btn.on_click(lambda *_: setattr(self, "_stop_streaming", True))

        main = widgets.VBox([
            widgets.HTML(""),
            self.chat_history,
            widgets.HBox([self.input_text, send_btn, stop_btn]),
        ], layout=widgets.Layout(width="100%", padding="0px"))

        self.layout = widgets.HBox([sidebar, main])

    def _refresh_tools_list(self):
        tools = lazy_import("nbchat.tools")
        names = "<br>".join(t["function"]["name"] for t in tools)
        self.tools_output.value = f"<b>Tools</b><br>{names}"

    # ------------------------------------------------------------------
    # Metrics updater
    # ------------------------------------------------------------------

    def _start_metrics_updater(self):
        def update_loop():
            from nbchat.ui.styles import CODE_COLOR
            while True:
                try:
                    log_path = Path("llama_server.log")
                    if log_path.exists():
                        with open(log_path, "rb") as f:
                            f.seek(0, 2)
                            f.seek(max(0, f.tell() - 4000))
                            lines = f.read().decode("utf-8", errors="ignore").splitlines()
                        # proc is True when the LLM server is actively processing
                        # tokens OR when a tool is currently executing.  The LLM
                        # server is legitimately idle between tool calls, but the
                        # agent loop is still running — showing black during tool
                        # execution was a false signal to the user.
                        server_active = any(
                            "slot update_slots:" in l.lower() for l in lines[-10:]
                        )
                        if any("all slots are idle" in l.lower() for l in lines[-5:]):
                            server_active = False
                        proc = server_active or self._tool_running
                        tps = 0.0
                        for line in reversed(lines):
                            if "eval time" in line.lower():
                                m = re.search(
                                    r"(?P<value>\d+(?:\.\d+)?)\s+tokens per second",
                                    line, re.IGNORECASE,
                                )
                                if m:
                                    tps = float(m.group("value"))
                                    break
                        emoji = "🟢" if proc else "⚫"
                        content = (
                            f'<b>Server</b> {emoji}<br>'
                            f'<b>TPS:</b> <code style="color:{CODE_COLOR};">{tps}</code><br>'
                            f'<i>{time.strftime("%H:%M:%S")}</i>'
                        )
                        try:
                            cf = changed_files()
                            if cf:
                                content += (
                                    "<br><br><b>Changed files:</b><br>"
                                    + "<br>".join(cf)
                                )
                        except Exception:
                            pass
                    else:
                        content = "<i>Log file not found</i>"
                except Exception as e:
                    content = f"<i>Error: {e}</i>"
                self.metrics_output.value = content
                time.sleep(1)

        threading.Thread(target=update_loop, daemon=True).start()

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _load_history(self):
        db = lazy_import("nbchat.core.db")
        self.history = list(db.load_history(self.session_id))
        self.task_log = db.load_task_log(self.session_id)
        self._turn_summary_cache = db.load_turn_summaries(self.session_id)
        self._render_history()
        self._refresh_monitoring_panel()

    def _refresh_monitoring_panel(self) -> None:
        """Re-render the monitoring sidebar widget from current session data.

        Called after each tool execution and at the end of each conversation
        turn — not on a timer.  Safe to call from the background conversation
        thread; ipywidgets handles the widget value update thread-safely.
        """
        try:
            from nbchat.ui.styles import CODE_COLOR
            mon = lazy_import("nbchat.core.monitoring")
            db = lazy_import("nbchat.core.db")

            session_report = mon.get_session_monitor(self.session_id).get_session_report()

            global_report: dict | None = None
            try:
                raw = db.load_global_monitoring_stats()
                if raw:
                    global_report = mon.get_global_report(raw)
            except Exception:
                pass

            self.monitoring_output.value = mon.format_monitoring_html(
                session_report, global_report, code_color=CODE_COLOR
            )
        except Exception:
            pass  # monitoring panel must never crash the agent loop

    def _render_history(self):
        """Render the windowed slice of history into the chat panel."""
        window, effective_cut = self._window()

        # effective_cut is the number of self.history rows excluded from the
        # window — the exact count for the "omitted messages" notice.
        children = []
        if effective_cut > 0:
            children.append(renderer.render_system(
                f"[{effective_cut} earlier messages are outside the context "
                f"window and have been omitted from this view.]"
            ))

        for role, content, tool_id, tool_name, tool_args, _error_flag in window:
            if role == "user":
                children.append(renderer.render_user(content))
            elif role == "analysis":
                children.append(renderer.render_reasoning(content))
            elif role == "assistant":
                children.append(
                    self._widget_for_assistant(content, tool_id, tool_args)
                )
            elif role == "assistant_full":
                try:
                    msg = json.loads(tool_args)
                    children.append(renderer.render_assistant_full(
                        msg.get("reasoning_content", ""),
                        msg.get("content", ""),
                        msg.get("tool_calls", []),
                    ))
                except Exception:
                    children.append(renderer.render_assistant(content))
            elif role == "tool":
                children.append(
                    renderer.render_tool(content, tool_name, str(tool_args))
                )
            elif role == "system":
                children.append(renderer.render_system(content))

        self.chat_history.children = children

    def _widget_for_assistant(
        self, content: str, tool_id: str, tool_args: str
    ) -> widgets.HTML:
        if tool_id == "multiple":
            try:
                return renderer.render_assistant_with_tools(
                    content, json.loads(tool_args)
                )
            except Exception:
                pass
        return renderer.render_assistant(content)

    def _append(self, widget: widgets.HTML):
        """Append a widget to the chat panel without pruning (scroll-safe)."""
        self.chat_history.children = list(self.chat_history.children) + [widget]

    def _prune_widgets(self) -> None:
        """Prune oldest widgets if the panel exceeds MAX_VISIBLE_WIDGETS."""
        children = list(self.chat_history.children)
        if len(children) > self.MAX_VISIBLE_WIDGETS:
            trim = len(children) - self.MAX_VISIBLE_WIDGETS
            note = renderer.render_system(
                f"[{trim} earlier messages pruned from view to maintain "
                f"performance. Full history is saved in the database.]"
            )
            self.chat_history.children = [note] + children[trim:]

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_new_chat(self, _):
        db = lazy_import("nbchat.core.db")
        self.session_id = str(uuid.uuid4())
        self._reset_session_state()
        # Initialise compressor state for the new session.
        comp = lazy_import("nbchat.core.compressor")
        comp.init_session(self.session_id)
        options = list(db.get_session_ids())
        if self.session_id not in options:
            options.append(self.session_id)
        self.session_dropdown.options = options
        self.session_dropdown.value = self.session_id
        self._render_history()

    def _on_session_change(self, change):
        if change["new"]:
            self.session_id = change["new"]
            self._reset_session_state()
            # Initialise compressor state for the switched-to session.
            comp = lazy_import("nbchat.core.compressor")
            comp.init_session(self.session_id)
            self._load_history()

    def _on_send(self, _):
        user_input = self.input_text.value.strip()
        if not user_input:
            return

        db = lazy_import("nbchat.core.db")

        if self._stream_thread and self._stream_thread.is_alive():
            self._stop_streaming = True
            self._stream_thread.join()

        self._prune_widgets()
        # Canonical 6-tuple: error_flag=0 for user messages
        self.history.append(("user", user_input, "", "", "", 0))
        self._append(renderer.render_user(user_input))
        db.log_message(self.session_id, "user", user_input)

        self.input_text.value = ""
        self._stop_streaming = False
        self._stream_thread = threading.Thread(
            target=self._process_conversation_turn,
            daemon=True,
        )
        self._stream_thread.start()