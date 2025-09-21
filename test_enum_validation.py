#!/usr/bin/env python3
"""
Test what enum format the backend actually expects
"""

import sys
sys.path.insert(0, '.')

from planexe_api.models import CreatePlanRequest, SpeedVsDetail

def test_enum_formats():
    """Test different enum formats to see what works"""

    test_cases = [
        # Test enum names
        ("ALL_DETAILS_BUT_SLOW", "Enum Name"),
        ("FAST_BUT_BASIC", "Enum Name"),
        ("BALANCED_SPEED_AND_DETAIL", "Enum Name"),

        # Test enum values
        ("all_details_but_slow", "Enum Value"),
        ("fast_but_skip_details", "Enum Value"),
        ("balanced_speed_and_detail", "Enum Value"),

        # Test actual enum objects
        (SpeedVsDetail.ALL_DETAILS_BUT_SLOW, "Enum Object"),
        (SpeedVsDetail.FAST_BUT_BASIC, "Enum Object"),
        (SpeedVsDetail.BALANCED_SPEED_AND_DETAIL, "Enum Object"),
    ]

    for enum_value, description in test_cases:
        try:
            request = CreatePlanRequest(
                prompt="Test plan",
                speed_vs_detail=enum_value
            )
            print(f"OK {description} '{enum_value}' WORKS")
            print(f"  Parsed as: {request.speed_vs_detail}")
            print(f"  Type: {type(request.speed_vs_detail)}")
            print(f"  Value: {request.speed_vs_detail.value if hasattr(request.speed_vs_detail, 'value') else 'N/A'}")
            print()
        except Exception as e:
            print(f"ERROR {description} '{enum_value}' FAILED: {e}")
            print()

if __name__ == "__main__":
    test_enum_formats()