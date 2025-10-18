#!/usr/bin/env python3
"""
Fix emoji characters at the byte level
Fire emoji (🔥) is UTF-8 bytes: F0 9F 94 A5
"""
from pathlib import Path

file_path = Path("planexe/plan/run_plan_pipeline.py")

print("="*70)
print("Fixing Emoji Bytes in File")
print("="*70)

# Read as bytes
with open(file_path, 'rb') as f:
    content = f.read()

original_len = len(content)

# Emoji byte sequences to replace
emoji_replacements = {
    b'\xf0\x9f\x94\xa5': b'[PIPELINE]',  # Fire emoji
    b'\xe2\x9c\x85': b'[OK]',             # Checkmark
    b'\xe2\x9d\x8c': b'[ERROR]',          # X mark
    b'\xe2\x9a\xa0': b'[WARNING]',        # Warning sign
}

total_replacements = 0
for emoji_bytes, replacement_bytes in emoji_replacements.items():
    count = content.count(emoji_bytes)
    if count > 0:
        print(f"Replacing {count} instances of {emoji_bytes.hex()} with {replacement_bytes.decode('utf-8')}")
        content = content.replace(emoji_bytes, replacement_bytes)
        total_replacements += count

if total_replacements > 0:
    # Write back as bytes
    with open(file_path, 'wb') as f:
        f.write(content)
    print(f"\n[SUCCESS] Fixed {total_replacements} emoji byte sequences")
    print(f"File size: {original_len} -> {len(content)} bytes")
else:
    print("\n[INFO] No emoji byte sequences found")

print("="*70)
