#!/usr/bin/env python3
"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-21
PURPOSE: Debug the API 500 error by calling the function directly
SRP and DRY check: Pass - Single responsibility for debugging API errors
"""

import sys
import os
import traceback
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up environment
os.environ["DATABASE_URL"] = "sqlite:///./planexe.db"

try:
    print("Importing API components...")
    from planexe_api.models import CreatePlanRequest, SpeedVsDetail
    from planexe_api.database import get_database, DatabaseService
    from fastapi import BackgroundTasks

    print("Creating request...")
    request = CreatePlanRequest(
        prompt="Test plan for debugging",
        speed_vs_detail=SpeedVsDetail.FAST_BUT_BASIC
    )
    print(f"Request: {request}")

    print("Getting database session...")
    db_gen = get_database()
    db = next(db_gen)
    print("Database session created")

    print("Creating database service...")
    db_service = DatabaseService(db)
    print("Database service created")

    print("Testing database connection...")
    plans = db_service.list_plans()
    print(f"Found {len(plans)} existing plans")

    print("Testing PlanExe config loading...")
    from planexe.utils.planexe_config import PlanExeConfig
    from planexe.utils.planexe_dotenv import PlanExeDotEnv
    config = PlanExeConfig.load()
    dotenv = PlanExeDotEnv.load()
    print(f"Config loaded: {config}")

    print("Testing path setup...")
    planexe_project_root = Path(project_root)
    run_dir = planexe_project_root / "run"
    print(f"Project root: {planexe_project_root}")
    print(f"Run dir: {run_dir}")

    print("Testing plan ID generation...")
    from planexe.plan.generate_run_id import generate_run_id
    from datetime import datetime

    start_time = datetime.utcnow()
    plan_id = generate_run_id(use_uuid=True, start_time=start_time)
    print(f"Generated plan ID: {plan_id}")

    print("Testing directory creation...")
    run_id_dir = (run_dir / plan_id).resolve()
    run_id_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created directory: {run_id_dir}")

    print("SUCCESS: All imports and operations work!")

except Exception as e:
    print(f"ERROR: {e}")
    print("Full traceback:")
    traceback.print_exc()