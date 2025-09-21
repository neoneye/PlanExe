#!/usr/bin/env python3
"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-21
PURPOSE: Test real Luigi progress monitoring via API
SRP and DRY check: Pass - Single responsibility for testing real progress API
"""

import requests
import time
import json

def test_real_progress():
    """Test the real Luigi progress monitoring via FastAPI"""

    api_base = "http://localhost:8000"

    print("Testing real Luigi progress monitoring...")
    print("=" * 60)

    # Create a test plan
    create_data = {
        "prompt": "Create a simple plan for testing Luigi progress parsing",
        "speed_vs_detail": "FAST_BUT_BASIC"
    }

    print(f"Creating plan with prompt: {create_data['prompt']}")

    try:
        print(f"Making POST request to {api_base}/api/plans")
        print(f"Request data: {create_data}")

        response = requests.post(f"{api_base}/api/plans", json=create_data, timeout=10)

        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            plan_data = response.json()
            plan_id = plan_data["plan_id"]
            print(f"Plan created: {plan_id}")
            print(f"Initial status: {plan_data['status']}")

            # Monitor progress for 30 seconds
            print("\nMonitoring progress...")
            print("-" * 40)

            for i in range(30):  # Monitor for 30 seconds
                time.sleep(1)

                # Get current status
                status_response = requests.get(f"{api_base}/api/plans/{plan_id}")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    progress = status_data["progress_percentage"]
                    message = status_data["progress_message"]
                    status = status_data["status"]

                    print(f"[{i+1:2d}s] {status} - {progress}% - {message}")

                    if status in ["completed", "failed"]:
                        print(f"\nPlan finished with status: {status}")
                        break
                else:
                    print(f"Error getting status: {status_response.status_code}")

        else:
            print(f"Error creating plan: {response.status_code}")
            print(f"Response text: {response.text}")
            try:
                error_json = response.json()
                print(f"Error JSON: {error_json}")
            except:
                print("Could not parse error response as JSON")

    except Exception as e:
        print(f"Error: {e}")

    print("\nTest completed!")

if __name__ == "__main__":
    test_real_progress()