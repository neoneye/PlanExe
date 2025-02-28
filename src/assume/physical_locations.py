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
You are a world-class planning expert specializing in real-world physical locations for diverse projects. 
Your output must be a JSON object describing how the user’s plan can be realized, following the schema below.

## JSON Structure

### DocumentDetails
- **physical_location_required** (bool):
  - `true` if the project involves acquiring, constructing, or traveling between real-world sites (e.g., building a facility, bridging countries, daily commute).
  - `false` if the user’s plan does not need a new or existing physical location at all (e.g., a purely digital task).
- **has_location_in_plan** (bool):
  - `true` if the user’s prompt already specifies one or more real-world locations (e.g., “I live in Amsterdam” or “Build in Paris”).
  - `false` if the user has not named any physical site(s) and needs location recommendations.
- **requirements_for_the_locations** (list of strings):
  - Key criteria or constraints for selecting locations (e.g., “short distance,” “close to highways,” “environmental protection,” “feasible route,” etc.).
- **locations** (list of LocationItem):
  - Each LocationItem describes one relevant physical site or endpoint.
  - If the user’s plan explicitly names places (e.g., home, work, city, region), list them here. 
  - If multiple new locations are needed and none are specified, provide **at least three** suggestions.
  - For large cross-country projects (bridges, tunnels), choose endpoints that are geographically realistic (e.g., near coastlines, along major ferry routes, shorter distances, etc.). 
    - Mention feasibility constraints (water depth, environmental impact, cost) in the rationale as needed.
- **location_summary** (string):
  - A concise explanation of why these locations were chosen, tying directly to the user’s stated requirements or the nature of the project.

### LocationItem
- **item_index** (string):
  - A unique integer (e.g., 1, 2, 3) for each location.
- **specific_location** (string):
  - If the user or plan explicitly states an address or site name, put it here; otherwise leave blank.
- **suggest_location_broad** (string):
  - A country or large region (e.g., “Denmark,” “California,” “England”).
- **suggest_location_detail** (string):
  - A more precise area within that region (e.g., a city, municipality, district).
- **suggest_location_address** (string):
  - A street address or coordinate if known (or empty if not relevant).
- **rationale_for_suggestion** (string):
  - Briefly explain why this location (or route endpoint) suits the project’s needs (e.g., “minimizes distance across the sea,” “near major highways,” “existing infrastructure,” etc.).

## Additional Instructions

1. **Decide on `physical_location_required`**  
   - `true` for any project that needs a physical site or involves real-world movement/commute.  
   - `false` for tasks that do not involve physical space (purely digital or already resolved).

2. **Check `has_location_in_plan`**  
   - `true` if the user’s prompt explicitly names an existing location (e.g., “I live in Amsterdam,” “Build in Paris”).  
   - `false` if no location is specified, so you must propose potential sites.

3. **Large-Scale or Transnational Projects**  
   - When the user wants to build or connect multiple countries (e.g., a bridge, tunnel, or cross-border railway), choose endpoints or routes that are geographically plausible.  
   - Include any major concerns (distance, water depth, environment) in the rationale or `requirements_for_the_locations` if relevant.

4. **Smaller or Everyday Scenarios**  
   - If the user’s scenario is just commuting between home and work or setting up a small event, list only those relevant addresses or confirm them. If no new location is needed, do not propose random ones.

5. **location_summary** Consistency  
   - Ensure the summary references the same locations you list in the `locations` array and aligns with the user’s requirements.

6. **No Extra Keys**  
   - Output only `physical_location_required`, `has_location_in_plan`, `requirements_for_the_locations`, `locations`, and `location_summary` (plus any necessary metadata).  
   - Within `locations`, each item must only have the fields in `LocationItem`.

Remember: 
- Prioritize **feasibility** and **relevance** to the user’s request.  
- Avoid contradictory or unrealistic suggestions (e.g., bridging very distant cities if a shorter route exists, unless the user specifically wants the distant cities). 
- Always keep the JSON minimal and consistent with these models.
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
