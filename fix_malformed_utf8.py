#!/usr/bin/env python3
"""
Fix malformed UTF-8 emoji representations in Python files
These appear as 'ðŸ"¥' instead of proper emoji due to encoding issues
"""
from pathlib import Path
import re

file_path = Path("planexe/plan/run_plan_pipeline.py")

print("="*70)
print("Fixing Malformed UTF-8 Emoji Patterns")
print("="*70)

# Read file with explicit UTF-8
with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

original_content = content

# Pattern replacements for malformed fire emoji variations
# These are the common malformed representations of 🔥
patterns_to_fix = [
    ('ðŸ"¥', '[PIPELINE]'),        # Fire emoji malformed
    ('âœ…', '[OK]'),                 # Checkmark malformed  
    ('âŒ', '[ERROR]'),               # X malformed
]

total_fixes = 0
for old_pattern, new_pattern in patterns_to_fix:
    count = content.count(old_pattern)
    if count > 0:
        print(f"Replacing {count} instances of '{repr(old_pattern)}' with '{new_pattern}'")
        content = content.replace(old_pattern, new_pattern)
        total_fixes += count

if total_fixes > 0:
    # Write back with UTF-8
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n[SUCCESS] Fixed {total_fixes} malformed characters in {file_path}")
else:
    print(f"\n[INFO] No malformed characters found")

print("="*70)
