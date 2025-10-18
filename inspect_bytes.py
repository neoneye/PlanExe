#!/usr/bin/env python3
from pathlib import Path

file_path = Path("planexe/plan/run_plan_pipeline.py")

with open(file_path, 'rb') as f:
    lines = f.readlines()

print("Inspecting lines 5393-5396 (0-indexed 5392-5395):")
for i in range(5392, 5396):
    if i < len(lines):
        line = lines[i]
        print(f"\nLine {i+1}:")
        print(f"  Bytes: {line[:100].hex(' ')}")
        print(f"  UTF-8: {line[:100].decode('utf-8', errors='replace')}")
