#!/usr/bin/env python3
"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-21
PURPOSE: Test FastAPI directly to see actual errors
SRP and DRY check: Pass - Single responsibility for testing FastAPI
"""

import os
import json
from pathlib import Path

# Set up environment
os.environ["DATABASE_URL"] = "sqlite:///./planexe.db"

# Add project to path
import sys
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    print("Importing FastAPI app...")
    from planexe_api.api import app
    from planexe_api.models import CreatePlanRequest, SpeedVsDetail
    from fastapi.testclient import TestClient

    print("Creating test client...")
    client = TestClient(app)

    print("Testing health endpoint...")
    response = client.get("/health")
    print(f"Health response: {response.status_code} - {response.json()}")

    print("Testing create plan endpoint...")
    request_data = {
        "prompt": "Test plan for debugging direct API",
        "speed_vs_detail": "fast_but_skip_details"  # Use enum value, not name
    }

    print(f"Request data: {request_data}")

    response = client.post("/api/plans", json=request_data)
    print(f"Create plan response: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")

    if response.status_code == 200:
        print(f"Response data: {response.json()}")
    else:
        print(f"Response text: {response.text}")
        try:
            error_data = response.json()
            print(f"Response JSON: {error_data}")
        except:
            print("Could not parse response as JSON")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()