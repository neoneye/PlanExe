import requests

try:
    response = requests.post(
        'http://localhost:8080/api/plans',
        json={
            'prompt': 'test plan creation',
            'llm_model': 'llm-1',
            'speed_vs_detail': 'all_details_but_slow'
        }
    )
    print(f'Status: {response.status_code}')
    print(f'Response: {response.text[:500]}')
except Exception as e:
    print(f'Error: {e}')
