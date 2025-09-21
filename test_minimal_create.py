#!/usr/bin/env python3
"""
Minimal test to reproduce the create_plan error
"""

import sys
import traceback
from pathlib import Path

# Test the exact code from create_plan function
def test_minimal():
    try:
        print("Step 1: Testing imports...")
        from planexe_api.models import CreatePlanRequest, SpeedVsDetail
        from planexe.plan.generate_run_id import generate_run_id
        from datetime import datetime
        import hashlib
        print("OK Imports successful")

        print("Step 2: Testing request creation...")
        request = CreatePlanRequest(
            prompt="Test plan",
            speed_vs_detail=SpeedVsDetail.ALL_DETAILS_BUT_SLOW
        )
        print("OK Request created")

        print("Step 3: Testing plan ID generation...")
        start_time = datetime.utcnow()
        plan_id = generate_run_id(use_uuid=True, start_time=start_time)
        print(f"OK Plan ID: {plan_id}")

        print("Step 4: Testing path setup...")
        # This is the exact code from the API
        from planexe.utils.planexe_dotenv import PlanExeDotEnv, DotEnvKeyEnum

        planexe_project_root = Path(__file__).parent.absolute()
        planexe_dotenv = PlanExeDotEnv.load()  # Use .load() like in the API
        override_run_dir = planexe_dotenv.get_absolute_path_to_dir(DotEnvKeyEnum.PLANEXE_RUN_DIR.value)
        if isinstance(override_run_dir, Path):
            run_dir = override_run_dir
        else:
            run_dir = planexe_project_root / "run"

        run_id_dir = (run_dir / plan_id).resolve()
        print(f"OK Run directory: {run_id_dir}")

        print("Step 5: Testing directory creation...")
        run_id_dir.mkdir(parents=True, exist_ok=True)
        print("OK Directory created")

        print("Step 6: Testing API key hash...")
        api_key_hash = None
        if request.openrouter_api_key:
            api_key_hash = hashlib.sha256(request.openrouter_api_key.encode()).hexdigest()
        print("OK API key hash handled")

        print("Step 7: Testing database service...")
        from planexe_api.database import DatabaseService, SessionLocal
        db = SessionLocal()
        db_service = DatabaseService(db)
        print("OK Database service created")

        print("Step 8: Testing plan data preparation...")
        plan_data = {
            "plan_id": plan_id,
            "prompt": request.prompt,
            "llm_model": request.llm_model,
            "speed_vs_detail": request.speed_vs_detail.value,
            "openrouter_api_key_hash": api_key_hash,
            "status": "pending",
            "progress_percentage": 0,
            "progress_message": "Plan queued for processing...",
            "output_dir": str(run_id_dir)
        }
        print("OK Plan data prepared")

        print("Step 9: Testing database insertion...")
        plan = db_service.create_plan(plan_data)
        print("OK Plan created in database")

        db.close()
        print("ALL TESTS PASSED!")

    except Exception as e:
        print(f"ERROR at step: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_minimal()