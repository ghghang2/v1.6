"""UI components for nbchat.

The :mod:`nbchat.ui` package provides a very small framework for rendering
chat messages in a terminal‑friendly format.  It is intentionally light
weight and does not depend on any external UI libraries.

Public symbols
--------------
``ChatBuilder``
    Builds a chat representation from a sequence of messages.
``ChatRenderer``
    Renders a chat representation to a string suitable for display.
``ChatUI``
    High‑level helper that combines the builder and renderer.
``ToolExecutor``
    Executes tool commands and captures their output.
``styles``
    Styling helpers used by the renderer.
``utils``
    Miscellaneous helper functions.
"""

from .chat_builder import ChatBuilder
from .chat_renderer import ChatRenderer
from .chatui import ChatUI
from .tool_executor import ToolExecutor
import styles
import utils

__all__ = [
    "ChatBuilder",
    "ChatRenderer",
    "ChatUI",
    "ToolExecutor",
    "styles",
    "utils",
]