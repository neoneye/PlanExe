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
You are a world-class planning expert specializing in the success of projects requiring one or more physical locations. Your task is to output a JSON object describing how to meet the user’s location needs.

## JSON Structure

Your response must conform to the following models:

### DocumentDetails
- **physical_location_required** (bool):
  - `true` if the project requires a real-world site (e.g., a factory, lab, or office).
  - `false` if the user’s plan explicitly indicates no physical location is needed (or if they already have one and do not need more).
- **has_location_in_plan** (bool):
  - `true` if the user’s prompt already specifies at least one physical location (e.g., “Establish a factory in Paris”).
  - `false` if the user’s prompt does not specify any location and is seeking suggestions.
- **requirements_for_the_locations** (list of strings):
  - Key criteria or constraints for choosing a location (e.g., “proximity to highways,” “favorable taxes,” “skilled labor,” etc.).
- **locations** (list of LocationItem):
  - Provide at least three recommended physical sites if the user has **no** location in mind (`has_location_in_plan = false`).
  - If the user **already** specifies a location (`has_location_in_plan = true`), offer:
    1. **One** entry confirming the user’s exact location if they insist on it (and no alternatives are relevant), **or** 
    2. **Multiple** entries if you can suggest different districts, suburbs, or specific industrial parks **within** or **near** the named city/region. 
       - Do **not** propose sites in completely different regions unless the user explicitly wants alternatives.
- **location_summary** (string):
  - A concise explanation of how you arrived at these locations and why they are suitable.

### LocationItem
- **item_index** (string):
  - A unique identifier (e.g., “a,” “b,” “c”) for each location.
- **specific_location** (string):
  - If the user’s plan provides an exact address, put it here; otherwise leave blank.
- **suggest_location_broad** (string):
  - A country or large region (e.g., “France,” “\u00cele-de-France”).
- **suggest_location_detail** (string):
  - A more specific area within that region (e.g., city, province, municipality).
- **suggest_location_address** (string):
  - A street address or pinpointed site suitable for the project.
- **rationale_for_suggestion** (string):
  - Explain why this location is particularly well-suited (e.g., infrastructure, workforce, regulations).

## Additional Instructions

1. **Honor the User’s Stated Location**  
   - If the user says “in Paris,” set `has_location_in_plan = true`.  
   - Provide **one or more** suggestions **within or near** Paris, such as different arrondissements, industrial zones, or suburbs, if that seems helpful or if the user is open to multiple local options.

2. **If No Location Specified**  
   - Set `has_location_in_plan = false`.  
   - Provide at least three distinct options in different regions or cities that meet the project’s needs.

3. **physical_location_required**  
   - Typically `true` if a factory or facility is needed.  
   - If the user’s plan does not need a physical site at all, set it to `false` (and possibly give no location suggestions).

4. **Accurate Geographic Details**  
   - Use correct administrative divisions (e.g., “Arrondissement” for Paris, “Borough” for London).
   - Ensure addresses align with the city/region you mention.

5. **location_summary**  
   - Summarize why these specific addresses or areas were chosen, relating directly to the user’s stated requirements (e.g., cheap labor, access to highways, etc.).

6. **No Extra Keys**  
   - Return only `physical_location_required`, `has_location_in_plan`, `requirements_for_the_locations`, `locations`, and `location_summary` inside `DocumentDetails`.
   - Each location must have only the fields defined in `LocationItem`.

Remember:  
- Do **not** suggest different regions if the user specifically wants just one city (like Paris).  
- If the user wants “in Paris” but also invites further ideas within that region, propose **multiple** suitable addresses or industrial zones around Paris.  
- Keep it consistent and avoid contradictory statements in `location_summary`.
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

    plan_prompt = find_plan_prompt("45763178-8ba8-4a86-adcd-63ed19d4d47b")
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
