#!/usr/bin/env python3
"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-21
PURPOSE: Test the Luigi pipeline with a simple prompt to verify end-to-end functionality
SRP and DRY check: Pass - Single responsibility for testing pipeline, reuses existing infrastructure
"""

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from planexe.plan.generate_run_id import generate_run_id
from planexe.plan.filenames import FilenameEnum

def test_pipeline():
    """Test the pipeline with a simple prompt"""

    # Generate run ID and directory
    start_time = datetime.utcnow()
    plan_id = generate_run_id(use_uuid=True, start_time=start_time)
    run_id_dir = Path("run") / plan_id
    run_id_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting pipeline test")
    print(f"   Plan ID: {plan_id}")
    print(f"   Directory: {run_id_dir.resolve()}")

    # Create required files
    start_time_file = run_id_dir / FilenameEnum.START_TIME.value
    initial_plan_file = run_id_dir / FilenameEnum.INITIAL_PLAN.value

    # Write start time
    import json
    start_time_data = {
        "timestamp": start_time.isoformat(),
        "plan_id": plan_id
    }
    with open(start_time_file, "w", encoding="utf-8") as f:
        json.dump(start_time_data, f, indent=2)

    # Write test prompt
    test_prompt = "Create a plan for launching a simple mobile app that helps people track their daily water intake"
    with open(initial_plan_file, "w", encoding="utf-8") as f:
        f.write(test_prompt)

    print(f"Created required files:")
    print(f"   {start_time_file}")
    print(f"   {initial_plan_file}")

    # Set up environment
    environment = os.environ.copy()
    environment["RUN_ID_DIR"] = str(run_id_dir.resolve())
    environment["SPEED_VS_DETAIL"] = "fast_but_skip_details"

    # Start the pipeline
    command = ["python", "-m", "planexe.plan.run_plan_pipeline"]

    print(f"Starting Luigi pipeline...")
    print(f"   Command: {' '.join(command)}")
    print(f"   RUN_ID_DIR: {environment['RUN_ID_DIR']}")

    try:
        process = subprocess.Popen(
            command,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        print(f"Pipeline running (PID: {process.pid})")
        print("Monitoring output...")

        # Monitor output for 30 seconds
        start_time = time.time()
        task_count = 0

        while process.poll() is None and (time.time() - start_time) < 30:
            # Check for new output
            if process.stdout.readable():
                line = process.stdout.readline()
                if line:
                    line = line.strip()
                    if any(keyword in line.upper() for keyword in ["TASK", "PROCESSING", "SUCCESS", "DONE", "RUNNING"]):
                        task_count += 1
                        print(f"   [{task_count:2d}] {line[:80]}...")

            time.sleep(0.1)

        if process.poll() is None:
            print(f"Pipeline still running after 30 seconds")
            print(f"Tasks detected: {task_count}")
            print(f"Output directory: {run_id_dir}")
            print(f"Generated files:")

            # List generated files
            for file_path in sorted(run_id_dir.iterdir()):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    print(f"     {file_path.name} ({size} bytes)")

            # Terminate gracefully
            process.terminate()
            process.wait(timeout=5)

        else:
            exit_code = process.returncode
            stdout, stderr = process.communicate()

            print(f"Pipeline completed with exit code: {exit_code}")

            if stdout:
                print("STDOUT:")
                print(stdout[-1000:])  # Last 1000 chars

            if stderr:
                print("STDERR:")
                print(stderr[-1000:])  # Last 1000 chars

        return plan_id, run_id_dir

    except Exception as e:
        print(f"❌ Error running pipeline: {e}")
        return None, None

if __name__ == "__main__":
    test_pipeline()