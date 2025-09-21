#!/usr/bin/env python3
"""
Debug script to test the create_plan function directly
"""

import sys
import traceback
from planexe_api.models import CreatePlanRequest, SpeedVsDetail
from planexe_api.database import SessionLocal

def test_create_plan():
    """Test the create_plan function directly"""

    # Create a test request
    request = CreatePlanRequest(
        prompt="Test plan",
        speed_vs_detail=SpeedVsDetail.ALL_DETAILS_BUT_SLOW
    )

    print(f"Test request created: {request}")

    # Test database connection
    try:
        db = SessionLocal()
        print("Database connection successful")
        db.close()
    except Exception as e:
        print(f"Database connection failed: {e}")
        traceback.print_exc()
        return

    # Try to import and call the function components
    try:
        from planexe.plan.generate_run_id import generate_run_id
        from datetime import datetime

        start_time = datetime.utcnow()
        plan_id = generate_run_id(use_uuid=True, start_time=start_time)
        print(f"Generated plan_id: {plan_id}")

    except Exception as e:
        print(f"Error generating plan ID: {e}")
        traceback.print_exc()
        return

    # Test directory creation
    try:
        from pathlib import Path
        from planexe.utils.planexe_dotenv import PlanExeDotEnv, DotEnvKeyEnum

        planexe_dotenv = PlanExeDotEnv()
        planexe_project_root = Path(__file__).parent.absolute()
        override_run_dir = planexe_dotenv.get_absolute_path_to_dir(DotEnvKeyEnum.PLANEXE_RUN_DIR.value)
        if isinstance(override_run_dir, Path):
            run_dir = override_run_dir
        else:
            run_dir = planexe_project_root / "run"

        run_id_dir = (run_dir / plan_id).resolve()
        print(f"Run directory path: {run_id_dir}")

        run_id_dir.mkdir(parents=True, exist_ok=True)
        print("Directory created successfully")

    except Exception as e:
        print(f"Error creating directory: {e}")
        traceback.print_exc()
        return

    print("All tests passed!")

if __name__ == "__main__":
    test_create_plan()