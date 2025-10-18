#!/usr/bin/env python3
"""
Quick script to replace emoji characters with ASCII markers for Windows compatibility
"""
from pathlib import Path

# Files to fix
files_to_fix = [
    "planexe/plan/run_plan_pipeline.py",
]

# Emoji replacements
replacements = {
    "🔥": "[PIPELINE]",
    "✅": "[OK]",
    "❌": "[ERROR]",
    "⚠️": "[WARNING]",
    "⚠": "[WARNING]",
    "💡": "[INFO]",
    "📋": "[LOG]",
    "🔔": "[NOTIFY]",
}

total_replacements = 0

for file_path in files_to_fix:
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"[SKIP] {file_path} - File not found")
        continue
    
    print(f"\n[PROCESSING] {file_path}")
    
    # Read file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count and replace emojis
    file_replacements = 0
    for emoji, replacement in replacements.items():
        count = content.count(emoji)
        if count > 0:
            print(f"  - Replacing {count} instances of '{emoji}' with '{replacement}'")
            content = content.replace(emoji, replacement)
            file_replacements += count
            total_replacements += count
    
    if file_replacements > 0:
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  [OK] Fixed {file_replacements} emoji instances")
    else:
        print(f"  [OK] No emojis found")

print(f"\n{'='*70}")
print(f"[COMPLETE] Total replacements: {total_replacements}")
print(f"{'='*70}")
