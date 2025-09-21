#!/usr/bin/env python3
"""
Test if there are any module import issues with the API
"""

import sys
import traceback

def test_api_import():
    """Test importing the API and calling functions"""
    try:
        print("Testing basic FastAPI imports...")
        from fastapi import FastAPI
        print("OK FastAPI imported")

        print("Testing planexe_api imports...")
        from planexe_api.models import CreatePlanRequest, SpeedVsDetail
        print("OK Models imported")

        print("Testing planexe_api.api import...")
        from planexe_api import api
        print("OK API module imported")

        print("Testing app instance...")
        app = api.app
        print("OK App instance accessed")

        print("Testing create_plan function directly...")
        # Create test request
        request = CreatePlanRequest(
            prompt="Test plan",
            speed_vs_detail=SpeedVsDetail.ALL_DETAILS_BUT_SLOW
        )

        # Try to access the function (without calling it)
        create_plan_func = api.create_plan
        print("OK create_plan function accessed")

        print("Testing database dependency...")
        from planexe_api.database import SessionLocal
        db = SessionLocal()
        db.close()
        print("OK Database works")

        print("ALL API IMPORT TESTS PASSED!")

    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_api_import()