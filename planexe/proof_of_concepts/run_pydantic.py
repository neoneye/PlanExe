"""
Check that Pydantic can be used to parse LLM "structured output".

PROMPT> python -m planexe.proof_of_concepts.run_pydantic
"""
from pydantic import BaseModel

class MyStruct(BaseModel):
    weather: str = "sunshine"
    count: str = "999"
    state: str = "start"

json_data = {
    "weather": "rain",
    "count": "42",
    "state": "halted"
}

my_struct = MyStruct(**json_data)
print(my_struct)
