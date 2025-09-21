#!/usr/bin/env python3
"""
Test what enum format the backend actually expects
"""

import requests
import json

def test_enum_formats():
    """Test different enum formats to see what works"""

    base_url = "http://localhost:8000"

    # Test different enum values
    test_cases = [
        ("ALL_DETAILS_BUT_SLOW", "Enum name"),
        ("all_details_but_slow", "Enum value"),
        ("FAST_BUT_BASIC", "Fast enum name"),
        ("fast_but_skip_details", "Fast enum value"),
    ]

    for enum_value, description in test_cases:
        print(f"\n--- Testing {description}: '{enum_value}' ---")

        payload = {
            "prompt": "Test plan",
            "speed_vs_detail": enum_value
        }

        try:
            response = requests.post(
                f"{base_url}/api/plans",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                print("SUCCESS! This enum format works")
                print(f"Response: {response.json()}")
                break
            elif response.status_code == 422:
                print("Validation Error:")
                print(json.dumps(response.json(), indent=2))
            elif response.status_code == 500:
                print("Internal Server Error (likely not enum issue)")
            else:
                print(f"Unexpected status: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    test_enum_formats()