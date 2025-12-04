import json
from pydantic import BaseModel, Field
from planexe.llm_factory import get_llm

class PlanStep(BaseModel):
    """Details about a single step in the plan."""
    step_title: str = Field(
        description="What does this step do briefly. Without formatted text."
    )
    detailed_instructions: str = Field(
        description="What does this step do in great detail"
    )

class DocumentDetails(BaseModel):
    """A description of what problem needs to be solved."""
    step_items: list[PlanStep] = Field(
        description="A list with the first 3 steps in the plan"
    )

if False:
    # This is what gets POSTed to the Ollama API, it goes inside root dictionary with the key `"format"`
    schema = DocumentDetails.model_json_schema()
    print(json.dumps(schema, indent=2))

llm = get_llm("ollama-llama3.1")
sllm = llm.as_structured_llm(DocumentDetails)

text = """
Create a rough plan for how to solve an ARC (Abstraction & Reasoning Corpus) puzzle. 
You have the input and output of the puzzle as a list of 2D arrays.
Then you need to create a plan for how to solve the puzzle.
"""

response = sllm.complete(text)

json_response = json.loads(response.text)
print(json.dumps(json_response, indent=2))
