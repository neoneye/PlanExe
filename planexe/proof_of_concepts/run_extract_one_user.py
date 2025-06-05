"""
python -m planexe.proof_of_concepts.run_extract_one_user
"""
import json
from typing import List, Optional
from pydantic import BaseModel
from planexe.llm_factory import get_llm

class User(BaseModel):
    id: int
    name: str = "Jane Doe"

llm = get_llm("ollama-llama3.1")
# llm = get_llm("openrouter-paid-gemini-2.0-flash-001")
sllm = llm.as_structured_llm(User)

text = "location=unspecified, user id=42, role=agent, name=Simon, age=30"

response = sllm.complete(text)

json_response = json.loads(response.text)
print(json.dumps(json_response, indent=2))
