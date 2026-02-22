import sys
import re

with open('./nbchat/ui/styles.py', 'r') as f:
    lines = f.readlines()

# Find start and end of assistant_full_html
start = None
for i, line in enumerate(lines):
    if line.strip().startswith('def assistant_full_html'):
        start = i
        break
if start is None:
    sys.exit(1)
# Find next function definition after start
end = None
for i in range(start+1, len(lines)):
    if lines[i].strip().startswith('def ') and i > start:
        end = i
        break
if end is None:
    end = len(lines)

print(f'Function lines {start} to {end}')
# Extract function body
func_lines = lines[start:end]

# We'll modify in memory
# 1. Add styling for reasoning raw
# Find line with 'raw = re.sub' inside reasoning block
for i, line in enumerate(func_lines):
    if 'raw = re.sub' in line and 'reasoning' in func_lines[i-2]:
        # insert after this line
        func_lines.insert(i+1, '        raw = _style_code_blocks(raw)\n')
        break

# 2. Fix tool_calls block: indent loop and closing details
# Find line with 'if tool_calls:'
for i, line in enumerate(func_lines):
    if 'if tool_calls:' in line:
        tool_start = i
        # find line with 'raw = md_to_html(content)' after this block
        for j in range(i+1, len(func_lines)):
            if 'raw = md_to_html(content)' in func_lines[j]:
                tool_end = j
                break
        # Now we need to adjust indentation of lines between tool_start+? and tool_end
        # The pattern: after the if line there is tool_summary line and html_parts.append line (already indented)
        # Then there is a for loop line at same indent as if? Actually it's dedented.
        # We'll simply re-write the block manually, but we'll just add 4 spaces to the for loop and closing details
        # Let's just replace the block with corrected version.
        # For simplicity, we'll output the corrected function manually later.
        break

# Write corrected function
for line in func_lines:
    print(line, end='')