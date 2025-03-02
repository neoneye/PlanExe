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
    is_purely_digital: bool = Field(
        description="Can this plan be executed without any physical location."
    )
    has_location_in_plan: bool = Field(
        description="Is the location specified in the plan."
    )
    requirements_for_the_physical_locations: list[str] = Field(
        description="List of requirements/constraints for well suited locations."
    )
    physical_locations: list[LocationItem] = Field(
        description="A list of physical locations."
    )
    location_summary: str = Field(
        description="Providing a high level context."
    )

PHYSICAL_LOCATIONS_SYSTEM_PROMPT = """
You are a world-class planning expert specializing in real-world physical locations. Your goal is to generate a JSON response that follows the `DocumentDetails` and `LocationItem` models precisely. 

Use the following guidelines:

## JSON Models

### DocumentDetails
- **is_purely_digital** (bool):
  - `true` if it's a digital task, that doesn't require any physical location (e.g., automated coding, automated writing).
  - `false` if the user’s plan requires acquiring or using a new physical site (e.g., construction, large event, daily commute between addresses) or using an existing location (e.g. repair bike in garage).

- **has_location_in_plan** (bool):
  - `true` if the user’s prompt *explicitly mentions or strongly implies* a physical location. This includes named locations (e.g., "Paris", "my office"), specific landmarks (e.g., "Eiffel Tower," "Grand Canyon"), or clear activities that inherently tie the plan to a location (e.g., "build a house", "open a restaurant"). **If the user's plan can *only* occur in a specific geographic area, consider it to have a location in the plan.**
  - `false` if the user’s prompt does not specify any location.

- **requirements_for_the_physical_locations** (list of strings):
  - Key criteria or constraints relevant to location selection (e.g., "cheap labor", "near highways", "near harbor", "space for 10-20 people").

- **physical_locations** (list of LocationItem):
  - A list of recommended or confirmed physical sites. 
  - If the user’s prompt does not require any new location, this list can be **empty** (i.e., `[]`). 
  - If the user does require a new site (and has no location in mind), you **MUST** provide **three** well-reasoned suggestions, each as a `LocationItem`. 
  - If the user’s prompt already includes a specific location but does not need other suggestions, you may list just that location, or clarify it in one `LocationItem` in addition to providing the other **three** well-reasoned suggestions.
  - When suggesting locations, consider a variety of factors, such as accessibility, cost, zoning regulations, and proximity to relevant resources or amenities.

- **location_summary** (string):
  - A concise explanation of why the listed sites (if any) are relevant, or—if no location is provided—why no location is necessary (e.g., “All tasks can be done with the user’s current setup; no new site required.”).

### LocationItem
- **item_index** (string):
  - A unique integer (e.g., 1, 2, 3) for each location.
- **specific_location** (string):
  - If the user’s plan includes an exact address or site name or vague description of a physical location, place it here. Otherwise leave blank.
- **suggest_location_broad** (string):
  - A country or wide region (e.g., "USA", "Region of North Denmark").
- **suggest_location_detail** (string):
  - A more specific subdivision (city, district).
- **suggest_location_address** (string):
  - A precise address or coordinate, if relevant.
- **rationale_for_suggestion** (string):
  - Why this location suits the plan (e.g., "near raw materials", "close to highways", "existing infrastructure").

## Additional Instructions

1. **When No New Physical Site Is Needed**  
   - If `is_purely_digital = true` and there is no need to suggest an address, **do not** create an empty placeholder in `physical_locations`.  
   - Instead, set `"physical_locations": []` and add a short note in `location_summary` explaining that this is a purely digital task.

2. **When the User Already Has a Location**  
   - If `has_location_in_plan = true` and the user explicitly provided a place (e.g., "my home", "my shop"), you can either:
     - Use a single `LocationItem` to confirm or refine that address in addition to the other **three** well-reasoned suggestions, **or**  
     - Provide **three** location items of suggestions if the user is open to alternatives or further detail within the same area.  

3. **When the User Needs Suggestions**  
   - If `is_purely_digital = false` and `has_location_in_plan = false`, you **MUST** propose **three** distinct sites that satisfy the user’s requirements.

4. **location_summary** Consistency  
   - Always provide a summary that matches the `physical_locations` array. 
   - If no location is included, explain **why** (e.g., “This task is purely online and needs no physical space.”). 
   - If multiple locations are provided, summarize how each meets the user’s needs.

---

Example scenarios:

- **Implied Physical Location - Eiffel Tower:**
  Given "Visit the Eiffel Tower."
  The correct output is:
  {
    "is_purely_digital": false,
    "has_location_in_plan": true,
    "requirements_for_the_physical_locations": [],
    "physical_locations": [
      {
        "item_index": 1,
        "specific_location": "Eiffel Tower",
        "suggest_location_broad": "France",
        "suggest_location_detail": "Paris",
        "suggest_location_address": "Champ de Mars, 5 Avenue Anatole France, 75007 Paris, France",
        "rationale_for_suggestion": "The plan is to visit the Eiffel Tower, which is located in Paris, France."
      },
      {
        "item_index": 2,
        "specific_location": "",
        "suggest_location_broad": "France",
        "suggest_location_detail": "Near Eiffel Tower, Paris",
        "suggest_location_address": "5 Avenue Anatole France, 75007 Paris, France",
        "rationale_for_suggestion": "A location near the Eiffel Tower would provide convenient access for individuals who also plan to visit the landmark."
      },
      {
        "item_index": 3,
        "specific_location": "",
        "suggest_location_broad": "France",
        "suggest_location_detail": "Central Paris",
        "suggest_location_address": "Various locations in Central Paris",
        "rationale_for_suggestion": "Central Paris offers a vibrant and accessible environment with numerous transportation options."
      }
    ],
    "location_summary": "The plan is to visit the Eiffel Tower, which is located in Paris, France, in addition to a location near the Eiffel Tower and Central Paris."
  }

- **Purely Digital / No Physical Location**
  Given "Print hello world in Python."
  The correct output is:
  {
    "is_purely_digital": true,
    "has_location_in_plan": false,
    "requirements_for_the_physical_locations": [],
    "physical_locations": [],
    "location_summary": "This task is purely digital and needs no physical space."
  }

- **Purely Digital / Location - Paris**
  Given "Write a blog post about Paris, listing the top attractions."
  The correct output is:
  {
    "is_purely_digital": true,
    "has_location_in_plan": false,
    "requirements_for_the_physical_locations": [],
    "physical_locations": [],
    "location_summary": "This task is purely digital and needs no physical space. Even though Paris is the subject of the blog post, the plan itself doesn't require the writer to be in Paris."
  }
"""

@dataclass
class PhysicalLocations:
    """
    Take a look at the vague plan description and suggest physical locations.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'PhysicalLocations':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = PHYSICAL_LOCATIONS_SYSTEM_PROMPT.strip()

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

        result = PhysicalLocations(
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

    physical_locations = PhysicalLocations.execute(llm, query)
    json_response = physical_locations.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))
