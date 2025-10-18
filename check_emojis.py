#!/usr/bin/env python3
"""Check for emoji characters in file"""
from pathlib import Path

file_path = Path("planexe/plan/run_plan_pipeline.py")

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check lines around 5314
print("Checking lines 5390-5400:")
for i in range(5389, 5400):
    if i < len(lines):
        line = lines[i]
        # Show byte representation
        print(f"Line {i+1}: {repr(line[:80])}")

print("\n" + "="*70)
print("Searching entire file for emoji characters...")
emoji_count = 0
emoji_lines = []

for i, line in enumerate(lines, 1):
    # Check for various emoji patterns
    for char in line:
        # Unicode emoji range check
        code_point = ord(char)
        if 0x1F300 <= code_point <= 0x1F9FF:  # Emoji range
            emoji_count += 1
            if i not in [x[0] for x in emoji_lines]:
                emoji_lines.append((i, line[:100].strip()))
            break

if emoji_count > 0:
    print(f"Found {emoji_count} lines with emojis:")
    for line_num, content in emoji_lines[:20]:
        print(f"  Line {line_num}: {content[:60]}")
else:
    print("No emojis found!")
