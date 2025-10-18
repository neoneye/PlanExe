#!/usr/bin/env python3
"""
Fix double-encoded emoji characters
The fire emoji got double-encoded as: c3 b0 c5 b8 e2 80 9d c2 a5
"""
from pathlib import Path

file_path = Path("planexe/plan/run_plan_pipeline.py")

print("="*70)
print("Fixing Double-Encoded Emoji Bytes")
print("="*70)

# Read as bytes
with open(file_path, 'rb') as f:
    content = f.read()

original_len = len(content)

# The double-encoded fire emoji pattern
double_encoded_fire = b'\xc3\xb0\xc5\xb8\xe2\x80\x9d\xc2\xa5'
replacement = b'[PIPELINE]'

count = content.count(double_encoded_fire)
print(f"Found {count} instances of double-encoded fire emoji")

if count > 0:
    content = content.replace(double_encoded_fire, replacement)
    
    # Write back as bytes
    with open(file_path, 'wb') as f:
        f.write(content)
    print(f"[SUCCESS] Replaced {count} instances")
    print(f"File size: {original_len} -> {len(content)} bytes")
else:
    print("[INFO] No double-encoded emojis found")

print("="*70)
