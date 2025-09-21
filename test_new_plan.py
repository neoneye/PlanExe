#!/usr/bin/env python3
"""Test the background task for the new plan"""

import os
from pathlib import Path
from planexe_api.database import SessionLocal, DatabaseService
from planexe_api.models import CreatePlanRequest, SpeedVsDetail
from planexe.utils.planexe_dotenv import PlanExeDotEnv

# Load environment variables
dotenv = PlanExeDotEnv.load()
dotenv.update_os_environ()

def test_specific_plan():
    """Test the new plan that's stuck"""
    plan_id = "PlanExe_b574ed85-b3c5-4753-be15-6e9655ec8501"

    print(f"Testing plan: {plan_id}")
    print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")

    try:
        # Test database connection
        db = SessionLocal()
        db_service = DatabaseService(db)
        print("OK Database connection successful")

        # Get plan
        plan = db_service.get_plan(plan_id)
        if not plan:
            print("FAIL Plan not found in database")
            return
        print(f"OK Plan found: {plan.status}")

        # Test file operations
        run_id_dir = Path(plan.output_dir)
        print(f"OK Output directory: {run_id_dir}")

        # Try to create setup file (what background task should do)
        setup_file = run_id_dir / "setup.txt"
        print(f"Creating setup file: {setup_file}")

        with open(setup_file, "w", encoding="utf-8") as f:
            f.write(plan.prompt)
        print("OK Setup file created")

        # Test environment setup
        environment = os.environ.copy()
        environment["RUN_ID_DIR"] = str(run_id_dir.absolute())
        environment["SPEED_VS_DETAIL"] = "FAST_BUT_BASIC"

        print(f"OK Environment setup: RUN_ID_DIR={environment['RUN_ID_DIR']}")

        # Test Luigi command (don't actually run it)
        import subprocess
        command = ["python", "-m", "planexe.plan.run_plan_pipeline"]
        print(f"OK Luigi command would be: {command}")

        print("All tests passed - background task logic should work!")

    except Exception as e:
        print(f"FAIL Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            db.close()
        except:
            pass

if __name__ == "__main__":
    test_specific_plan()