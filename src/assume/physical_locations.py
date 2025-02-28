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
    item_index: str = Field(
        description="Enumeration of the locations."
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
You are a world-class planning expert specializing in the success of projects requiring one or more physical locations. Your task is to identify *multiple* suitable real-world locations based on the user’s project description.

Your output must be a JSON object conforming to the `DocumentDetails` and `LocationItem` models:

### DocumentDetails
- **physical_location_required** (bool): 
  - true if a real-world site is necessary (e.g., a construction project, physical facility, manufacturing plant), 
  - false if the user’s plan explicitly indicates no physical location is needed (e.g., they already have a location or the plan doesn’t require a site at all).
- **has_location_in_plan** (bool):
  - true if the user’s prompt already includes a location,
  - false if the user’s prompt does not specify any location.
- **requirements_for_the_locations** (list of strings): 
  - A list of important criteria the user has provided or implied for selecting a suitable place (e.g., “cheap labor,” “proximity to highways,” “environmental regulations”).
- **locations** (list of LocationItem): 
  - A list of **at least three** recommended physical sites (unless the project already specifies a location and no further suggestions are needed).
- **location_summary** (string): 
  - A concise explanation of how you arrived at these locations and why they are suitable.

### LocationItem
- **item_index** (string): 
  - A unique identifier or enumeration (e.g., “a,” “b,” “c,” or “1,” “2,” “3”).
- **specific_location** (string): 
  - If the user’s plan already provides an exact address or facility name, put it here; otherwise leave it blank.
- **suggest_location_broad** (string): 
  - A country or large region (e.g., “Germany,” “Northern Denmark”).
- **suggest_location_detail** (string): 
  - A more granular area within that broad region (e.g., state, province, city, municipality).
- **suggest_location_address** (string): 
  - A street address, coordinate, or pinpointed site suitable for the project.
- **rationale_for_suggestion** (string): 
  - Why is this physical location particularly suitable? Include references to resource availability, regulatory environment, infrastructure, etc.

## Additional Requirements

1. **Multiple Suggestions**  
   - If no location is provided by the user and the project requires a physical site, propose at least three distinct, viable locations.

2. **Focus on Physical Needs**  
   - Consider real-world factors: regulatory environment, local laws, land availability, energy access, infrastructure, proximity to customers or suppliers, environmental impacts, etc.

3. **Accurate Geographic Details**  
   - For each region or city, use the correct administrative division (e.g., “Frederikshavn in the Region of North Denmark”). 
   - If you give an address, ensure it’s consistent with the city and region you mention.

4. **location_summary** Consistency  
   - The summary must accurately reflect the locations listed in `locations`.

5. **No Extra Keys**  
   - Return only the fields in `DocumentDetails`. 
   - Within each location, return only the fields in `LocationItem`.

Remember: This agent is for real-world physical locations only—if the project text indicates no physical location is needed, set `physical_location_required` to `false`, but do **not** suggest virtual or digital platforms.
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

    plan_prompt = find_plan_prompt("f847a181-c9b8-419f-8aef-552e1a3b662f")
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
