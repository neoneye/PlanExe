#!/usr/bin/env python3
"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-21
PURPOSE: Test the Luigi progress parsing logic with real log data
SRP and DRY check: Pass - Single responsibility for testing Luigi parsing
"""

import re

def test_luigi_parsing():
    """Test Luigi task parsing with real log lines"""

    # Sample Luigi log lines from actual run
    test_lines = [
        "2025-09-21 10:51:26,664 - luigi-interface - DEBUG - Checking if StartTimeTask(run_id_dir=D:\\1Projects\\PlanExe\\run\\PlanExe_dba1ef90-35f6-433a-90b9-0c1ae34f9f0e, speedvsdetail=FAST_BUT_SKIP_DETAILS, llm_models=[\"gemini-2.0-flash\", \"gpt-4o-mini\", \"gpt-4o\", \"gpt-4-turbo\", \"qwen-qwen3-max\", \"x-ai-grok-4-fast-free\"]) is complete",
        "2025-09-21 10:51:26,666 - luigi-interface - DEBUG - Checking if SetupTask(run_id_dir=D:\\1Projects\\PlanExe\\run\\PlanExe_dba1ef90-35f6-433a-90b9-0c1ae34f9f0e, speedvsdetail=FAST_BUT_SKIP_DETAILS, llm_models=[\"gemini-2.0-flash\", \"gpt-4o-mini\", \"gpt-4o\", \"gpt-4-turbo\", \"qwen-qwen3-max\", \"x-ai-grok-4-fast-free\"]) is complete",
        "2025-09-21 10:51:26,668 - luigi-interface - DEBUG - Checking if RedlineGateTask(run_id_dir=D:\\1Projects\\PlanExe\\run\\PlanExe_dba1ef90-35f6-433a-90b9-0c1ae34f9f0e, speedvsdetail=FAST_BUT_SKIP_DETAILS, llm_models=[\"gemini-2.0-flash\", \"gpt-4o-mini\", \"gpt-4o\", \"gpt-4-turbo\", \"qwen-qwen3-max\", \"x-ai-grok-4-fast-free\"]) is complete"
    ]

    completed_tasks = set()
    total_tasks = 61

    print("Testing Luigi task parsing...")
    print("=" * 50)

    for line in test_lines:
        line = line.strip()
        print(f"Processing: {line[:100]}...")

        task_updated = False
        task_name = None

        # Pattern 1: "luigi-interface - DEBUG - Checking if TaskName(...) is complete"
        checking_match = re.search(r'Checking if (\w+Task)\(.*\) is complete', line)
        if checking_match:
            task_name = checking_match.group(1)
            if task_name not in completed_tasks and task_name != "FullPlanPipeline":
                completed_tasks.add(task_name)
                task_updated = True

        # Pattern 2: Look for actual task execution indicators
        elif re.search(r'(Running|Starting|Executing).*(\w+Task)', line, re.IGNORECASE):
            task_match = re.search(r'(\w+Task)', line)
            if task_match:
                task_name = task_match.group(1)
                if task_name not in completed_tasks and task_name != "FullPlanPipeline":
                    completed_tasks.add(task_name)
                    task_updated = True

        if task_updated:
            progress_percentage = min(95, int((len(completed_tasks) / total_tasks) * 100))
            progress_message = f"Task {len(completed_tasks)} of {total_tasks}: {task_name}"
            print(f"DETECTED: {progress_percentage}% - {progress_message}")
        else:
            print("   No task detected")

        print()

    print("=" * 50)
    print(f"Final Results:")
    print(f"Tasks detected: {len(completed_tasks)}")
    print(f"Task names: {sorted(completed_tasks)}")
    print(f"Final progress: {min(95, int((len(completed_tasks) / total_tasks) * 100))}%")

if __name__ == "__main__":
    test_luigi_parsing()