#!/usr/bin/env python3
"""
Test Luigi subprocess execution to diagnose issues
"""
import subprocess
import sys
import os
from pathlib import Path

# Ensure environment variables are loaded
from dotenv import load_dotenv
load_dotenv()

print("=" * 70)
print("Luigi Subprocess Diagnostic Test")
print("=" * 70)

# Check API keys
print("\n1. Checking API Keys:")
api_keys = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
for key in api_keys:
    value = os.environ.get(key)
    if value:
        print(f"   [OK] {key}: {value[:10]}...{value[-4:]}")
    else:
        print(f"   [MISSING] {key}")

# Test Python executable
print(f"\n2. Python Executable: {sys.executable}")

# Test module import
print("\n3. Testing module import:")
try:
    import planexe.plan.run_plan_pipeline
    print("   [OK] planexe.plan.run_plan_pipeline imported successfully")
except Exception as e:
    print(f"   [ERROR] Failed to import: {e}")
    sys.exit(1)

# Test subprocess command
print("\n4. Testing Luigi subprocess:")
run_id_dir = Path("run/test_diagnostic_run").absolute()  # Must be absolute!
run_id_dir.mkdir(parents=True, exist_ok=True)

# Write minimal input files
(run_id_dir / "001-1-start_time.json").write_text("2025-10-17T20:00:00")
(run_id_dir / "001-2-plan.txt").write_text("test plan")

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
env["RUN_ID_DIR"] = str(run_id_dir)  # Now absolute
env["SPEED_VS_DETAIL"] = "fast_but_skip_details"
env["LLM_MODEL"] = "gpt-5-mini-2025-08-07"

cmd = [
    sys.executable,
    "-m", "planexe.plan.run_plan_pipeline"
]

print(f"   Command: {' '.join(cmd)}")
print(f"   Working Dir: {Path.cwd()}")
print(f"   Run ID Dir: {run_id_dir}")

try:
    print("\n5. Starting subprocess...")
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',  # Explicit UTF-8 encoding for Windows
        errors='replace',   # Replace decode errors instead of crashing
        bufsize=1,
        universal_newlines=True
    )
    
    print("   [OK] Subprocess started, PID:", process.pid)
    print("\n6. Reading output (first 30 lines):")
    
    line_count = 0
    for line in process.stdout:
        line_count += 1
        print(f"   [{line_count:3d}] {line.rstrip()}")
        if line_count >= 30:
            print("   ... (stopping after 30 lines)")
            break
    
    # Wait a bit for process
    try:
        return_code = process.wait(timeout=10)
        print(f"\n7. Process finished with return code: {return_code}")
    except subprocess.TimeoutExpired:
        print("\n7. Process still running after 10 seconds (this is normal)")
        process.terminate()
        print("   Terminated subprocess")
    
except Exception as e:
    print(f"\n   [ERROR] Subprocess failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("Test Complete")
print("=" * 70)
