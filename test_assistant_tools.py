#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from nbchat.ui.styles import assistant_message_with_tools_html, assistant_full_html

tool_calls = [
    {"function": {"name": "run_command", "arguments": '{"command": "ls"}'}},
]

# Test with content
html1 = assistant_message_with_tools_html("I'll run a command", tool_calls)
print("Assistant with tools (content):")
print(html1)
print()

# Test without content
html2 = assistant_message_with_tools_html("", tool_calls)
print("Assistant with tools (no content):")
print(html2)
print()

# Test assistant_full with reasoning
html3 = assistant_full_html("Let me think...", "I'll run a command", tool_calls)
print("Assistant full (reasoning + content + tools):")
print(html3)
print()

# Test empty reasoning
html4 = assistant_full_html("", "I'll run a command", tool_calls)
print("Assistant full (no reasoning):")
print(html4)
print()