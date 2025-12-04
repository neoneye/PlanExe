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
        description="A list with the steps of the plan"
    )

llm = get_llm("ollama-llama3.1")
sllm = llm.as_structured_llm(DocumentDetails)

text = """
You are an expert at breaking down complex problems into smaller, more manageable parts.

Create a rough plan for how to solve an ARC (Abstraction & Reasoning Corpus) puzzle. 
You have the input and output of the puzzle as a list of 2D arrays.

Ideas to include in the plan:
- Input/Output Analysis, look for clues within the input or output, are the shapes always square?
- Hypothesis Generation, is this a sorting problem? are there things that has to be counted?
- Refinement and Iteration
- Document your thought process
- Failure Analysis, did one of the step miss something crucial?
- Solution Verification
"""

response = sllm.complete(text)

json_response = json.loads(response.text)
print(json.dumps(json_response, indent=2))
