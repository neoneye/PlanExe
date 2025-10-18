import requests
import json

plan_id = "PlanExe_bc2ebd50-5484-4e99-8234-b4563e9143b7"
response = requests.get(f"http://localhost:8080/api/plans/{plan_id}")
print(json.dumps(response.json(), indent=2))
