#!/usr/bin/env python3
"""Manually trigger background task for stuck plan"""

import asyncio
from pathlib import Path
from planexe_api.models import CreatePlanRequest, SpeedVsDetail

# Import the background task function
from planexe_api.api import run_plan_job

def trigger_plan():
    """Manually trigger the background task for the stuck plan"""
    plan_id = "PlanExe_922fae23-c47f-4496-b42c-43fca4d3cf03"

    # Create a mock request object
    request = CreatePlanRequest(
        prompt="simple test",
        llm_model="gpt-4o-mini",
        speed_vs_detail="FAST_BUT_BASIC"
    )

    print(f"Manually triggering background task for plan: {plan_id}")

    try:
        # Call the background task function directly
        run_plan_job(plan_id, request)
        print("Background task completed!")

        # Check if files were created
        run_dir = Path(f"run/{plan_id}")
        setup_file = run_dir / "setup.txt"
        if setup_file.exists():
            print(f"✓ Setup file created: {setup_file}")
        else:
            print("✗ Setup file not created")

    except Exception as e:
        print(f"Background task failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    trigger_plan()