#!/usr/bin/env python3
"""Debug script to test the background task manually"""

from pathlib import Path
from planexe_api.database import SessionLocal, DatabaseService
from planexe_api.models import CreatePlanRequest, SpeedVsDetail

def test_background_task():
    """Test the background task logic manually"""

    # Test plan ID from the latest API call
    plan_id = "PlanExe_609ce46b-afc5-4f5e-bfae-454d1d064e56"

    print(f"DEBUG: Testing background task for plan_id: {plan_id}")

    # Create database session
    try:
        db = SessionLocal()
        db_service = DatabaseService(db)
        print("DEBUG: Database service created successfully")
    except Exception as e:
        print(f"Database connection error: {e}")
        return

    try:
        # Get plan from database
        print(f"DEBUG: Looking up plan in database: {plan_id}")
        plan = db_service.get_plan(plan_id)
        if not plan:
            print(f"DEBUG: Plan not found in database: {plan_id}")
            return
        print(f"DEBUG: Plan found: {plan.plan_id}, status: {plan.status}")

        # Test file creation
        run_id_dir = Path(plan.output_dir)
        print(f"DEBUG: Output directory: {run_id_dir}")

        # Try to create setup file
        setup_file = run_id_dir / "setup.txt"
        print(f"DEBUG: Attempting to write setup file: {setup_file}")

        with open(setup_file, "w", encoding="utf-8") as f:
            f.write(plan.prompt)
        print("DEBUG: Setup file written successfully")

    except Exception as e:
        print(f"DEBUG: Exception occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            db.close()
        except Exception as e:
            print(f"Error closing database: {e}")

if __name__ == "__main__":
    test_background_task()