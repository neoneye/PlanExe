"""
Pick suitable locations for the project plan. If the description already includes the location, then there is no need for this step.
If the location is not mentioned, then the expert should suggest suitable locations based on the project requirements.
There may be multiple locations, in case a bridge is to be built between two countries.

PROMPT> python -m src.assume.physical_locations
"""
import os
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from src.format_json_for_use_in_query import format_json_for_use_in_query

logger = logging.getLogger(__name__)

class LocationItem(BaseModel):
    item_index: int = Field(
        description="Enumeration of the locations, starting from 1."
    )
    specific_location: str = Field(
        description="If the plan has a specific location, provide the location. Otherwise leave it empty."
    )
    suggest_location_broad: str = Field(
        description="Suggest a broad location for the project, such as a country or region."
    )
    suggest_location_detail: str = Field(
        description="Narrow down the location even more, such as a city name."
    )
    suggest_location_address: str = Field(
        description="Suggest a specific address, that is suitable for the project."
    )
    rationale_for_suggestion: str = Field(
        description="Explain why this particular location is suggested."
    )

class DocumentDetails(BaseModel):
    physical_location_required: bool = Field(
        description="Is one or more physical locations required for in the plan, or can the plan be executed without a location."
    )
    has_location_in_plan: bool = Field(
        description="Is the location unspecified in the plan."
    )
    requirements_for_the_locations: list[str] = Field(
        description="List of requirements for well suited locations."
    )
    locations: list[LocationItem] = Field(
        description="A list of project locations."
    )
    location_summary: str = Field(
        description="Providing a high level context."
    )

PICK_LOCATIONS_SYSTEM_PROMPT = """
You are a world-class planning expert specializing in real-world physical locations. Your goal is to generate a JSON response that follows the `DocumentDetails` and `LocationItem` models precisely. 

Use the following guidelines:

## JSON Models

### DocumentDetails
- **physical_location_required** (bool):
  - `true` if the user’s plan requires acquiring or using a new physical site (e.g., construction, large event, daily commute between addresses).
  - `false` if no physical site is involved or no new location needs to be set up (e.g., a digital task, or the user already has a location that does not need further elaboration).

- **has_location_in_plan** (bool):
  - `true` if the user’s prompt already provides or implies a physical location (e.g., “my home,” “my office,” “in Paris”).
  - `false` if the user’s prompt does not specify any location, and you need to suggest one or more.

- **requirements_for_the_locations** (list of strings):
  - Key criteria or constraints relevant to location selection (e.g., “cheap labor,” “near highways,” “environmentally protected area”).

- **locations** (list of LocationItem):
  - A list of recommended or confirmed physical sites. 
  - If the user’s prompt does not require any new location, this list can be **empty** (i.e., `[]`). 
  - If the user does require a new site (and has no location in mind), provide **at least three** well-reasoned suggestions, each as a `LocationItem`. 
  - If the user’s prompt already includes a specific location but does not need other suggestions, you may list just that location or clarify it in one `LocationItem`.

- **location_summary** (string):
  - A concise explanation of why the listed sites (if any) are relevant, or—if no location is provided—why no location is necessary (e.g., “All tasks can be done with the user’s current setup; no new site required.”).

### LocationItem
- **item_index** (string):
  - A unique integer (e.g., 1, 2, 3) for each location.
- **specific_location** (string):
  - If the user’s plan includes an exact address or site name, place it here. Otherwise leave blank.
- **suggest_location_broad** (string):
  - A country or wide region (e.g., “USA,” “Region of North Denmark”).
- **suggest_location_detail** (string):
  - A more specific subdivision (city, district).
- **suggest_location_address** (string):
  - A precise address or coordinate, if relevant.
- **rationale_for_suggestion** (string):
  - Why this location suits the plan (e.g., “near raw materials,” “close to highways,” “existing infrastructure”).

## Additional Instructions

1. **When No New Physical Site Is Needed**  
   - If `physical_location_required = false` and there is no need to suggest an address, **do not** create an empty placeholder in `locations`.  
   - Instead, set `"locations": []` and add a short note in `location_summary` explaining that no new physical site is required.

2. **When the User Already Has a Location**  
   - If `has_location_in_plan = true` and the user explicitly provided a place (e.g., “my home,” “my shop”), you can either:
     - Use a single `LocationItem` to confirm or refine that address, **or**  
     - Provide multiple location items if the user is open to alternatives or further detail within the same area.  

3. **When the User Needs Suggestions**  
   - If `physical_location_required = true` and `has_location_in_plan = false`, propose **at least three** distinct sites that satisfy the user’s requirements (unless the user’s plan logically needs only one or two, such as bridging two countries).

4. **location_summary** Consistency  
   - Always provide a summary that matches the `locations` array. 
   - If no location is included, explain **why** (e.g., “This task is purely online and needs no physical space.”). 
   - If multiple locations are provided, summarize how each meets the user’s needs.

5. **No Extra Fields**  
   - Return **only** the fields in `DocumentDetails` and, within `locations`, only those in `LocationItem`. 
   - Do **not** add any extra keys outside the schema.

---

Example scenarios:

- **Purely Digital / No Location**  
  {
    "physical_location_required": false,
    "has_location_in_plan": false,
    "requirements_for_the_locations": [],
    "locations": [],
    "location_summary": "No physical site is required for this project, so no location suggestions are needed."
  }
"""

@dataclass
class PickLocations:
    """
    Take a look at the vague plan description and suggest locations.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'PickLocations':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = PICK_LOCATIONS_SYSTEM_PROMPT.strip()

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

        result = PickLocations(
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

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")

    plan_prompt = find_plan_prompt("d3e10877-446f-4eb0-8027-864e923973b0")
    query = (
        f"{plan_prompt}\n\n"
        "Today's date:\n2025-Feb-27\n\n"
        "Project start ASAP"
    )
    print(f"Query: {query}")

    pick_locations = PickLocations.execute(llm, query)
    json_response = pick_locations.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))
