import requests
import json
import time

def test_plan_creation():
    """Test plan creation to capture the exact error"""
    
    # Test API health first
    try:
        health_response = requests.get("http://localhost:8000/health")
        print(f"Health check: {health_response.status_code} - {health_response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return
    
    # Create test plan
    plan_data = {
        "prompt": "test snow plow business",
        "llm_model": "gpt-5-mini-2025-08-07",
        "speed_vs_detail": "fast_but_skip_details"
    }
    
    try:
        print(f"Creating plan with data: {plan_data}")
        response = requests.post(
            "http://localhost:8000/api/plans",
            json=plan_data,
            timeout=30
        )
        
        print(f"Plan creation response: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            plan_info = response.json()
            plan_id = plan_info.get('plan_id')
            print(f"Plan created successfully: {plan_id}")
            
            # Wait a moment then check status
            time.sleep(2)
            status_response = requests.get(f"http://localhost:8000/api/plans/{plan_id}")
            print(f"Plan status: {status_response.json()}")
            
        else:
            print(f"Plan creation failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Exception during plan creation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_plan_creation()