import requests
import json
import os

model_name = "meta-llama/llama-3.3-8b-instruct:free"
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

print("connecting to openrouter...")
response = requests.post(
  url="https://openrouter.ai/api/v1/chat/completions",
  headers={
    "Authorization": f"Bearer {openrouter_api_key}",
    "Content-Type": "application/json"
  },
  data=json.dumps({
    "model": model_name,
    "messages": [
      {
        "role": "user",
        "content": "List names of 3 planets in the solar system. Comma separated. No other text."
      }
    ],
    
  })
)
print(f"response:\n{response.json()}")
