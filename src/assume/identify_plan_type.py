"""
Determine if the plan can be executed digitally without any physical location. Or if the plan requires a physical location.

PROMPT> python -m src.assume.identify_plan_type
"""
import os
import json
import time
import logging
from math import ceil
from enum import Enum
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class PlanType(str, Enum):
    # A plan that can be executed digitally without any physical location.
    digital = 'digital'
    # A plan that requires a physical location.
    physical = 'physical'

class DocumentDetails(BaseModel):
    plan_type: PlanType = Field(
        description="Classify the type of plan."
    )
    summary: str = Field(
        description="Providing a high level context."
    )

PLAN_TYPE_SYSTEM_PROMPT = """
You are a world-class planning expert specializing in real-world physical locations. Your goal is to generate a JSON response that follows the `DocumentDetails` model precisely. 

Use the following guidelines:

## JSON Model

### DocumentDetails
- **plan_type** (PlanType):
  - `digital` if it's a digital task, that doesn't require any physical location (e.g., automated coding, automated writing).
  - `physical` if the user’s plan requires acquiring or using a new physical site (e.g., construction, large event, daily commute between addresses) or using an existing location (e.g. repair bike in garage).

- **summary** (string):
  - A concise explanation of why physical locations are relevant. 
  - If no physical location is necessary, explain **why** (e.g., "A LLM can generate the python code", "This task is purely online and needs no physical space.").

---

Example scenarios:

- **Implied Physical Location - Eiffel Tower:**
  Given "Visit the Eiffel Tower."
  The correct output is:
  {
    "plan_type": "physical",
    "summary": "The plan is to visit the Eiffel Tower, which is located in Paris, France."
  }

- **Purely Digital / No Physical Location**
  Given "Print hello world in Python."
  The correct output is:
  {
    "plan_type": "digital",
    "summary": "This task is purely digital and needs no physical space. A LLM can generate the python code."
  }

- **Purely Digital / Location - Paris**
  Given "Write a blog post about Paris, listing the top attractions."
  The correct output is:
  {
    "plan_type": "digital",
    "summary": "Even though Paris is the subject of the blog post, the plan itself doesn't require the writer to be in Paris. A LLM can generate the blog post."
  }
"""

@dataclass
class IdentifyPlanType:
    """
    Take a look at the vague plan description and determine:
    - If it's a plan that can be executed digitally, without any physical location.
    - Or if the plan requires a physical location.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'IdentifyPlanType':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = PLAN_TYPE_SYSTEM_PROMPT.strip()

        chat_message_list = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt,
            )
        ]

        sllm = llm.as_structured_llm(DocumentDetails)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = IdentifyPlanType(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        return result
    
    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")

    plan_prompt = find_plan_prompt("de626417-4871-4acc-899d-2c41fd148807")
    query = (
        f"{plan_prompt}\n\n"
        "Today's date:\n2025-Feb-27\n\n"
        "Project start ASAP"
    )
    print(f"Query: {query}")

    identify_plan_type = IdentifyPlanType.execute(llm, query)
    json_response = identify_plan_type.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))
