#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from nbchat.ui.styles import tool_result_html

# Test with tool_args empty
html1 = tool_result_html("Hello world", tool_name="run_command", tool_args="", preview="")
print("Test 1 (empty tool_args):")
print(html1)
print()

# Test with tool_args non-empty
html2 = tool_result_html("Hello world", tool_name="run_command", tool_args='{"command": "ls"}', preview="")
print("Test 2 (with tool_args):")
print(html2)
print()

# Test with no tool_name
html3 = tool_result_html("Result", tool_name="", tool_args='{}', preview="Preview")
print("Test 3 (no tool_name):")
print(html3)
print()

# Test _tool_calls_html indirectly via import
from nbchat.ui.styles import _tool_calls_html
tool_calls = [
    {"function": {"name": "run_command", "arguments": '{"command": "ls"}'}},
    {"function": {"name": "browser", "arguments": '{"url": "example.com"}'}},
]
html4 = _tool_calls_html(tool_calls)
print("Test 4 (tool calls html):")
print(html4)
print()