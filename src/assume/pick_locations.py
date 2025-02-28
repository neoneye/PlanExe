"""
Pick suitable locations for the project plan. If the description already includes the location, then there is no need for this step.
If the location is not mentioned, then the expert should suggest suitable locations based on the project requirements.
There may be multiple locations, in case a bridge is to be built between two countries.

PROMPT> python -m src.assume.pick_locations
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
    location_required_for_plan: str = Field(
        description="Is the location required for in the plan, or can the plan be executed without a location."
    )
    missing_location_in_plan: str = Field(
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
You are a world-class planning expert specializing in the success of projects. Your task is to identify *multiple* suitable locations for the project described.

Accurate location information is critical for:
1) Assessing local regulatory frameworks,
2) Determining resource availability (e.g., land, energy, water),
3) Evaluating grid connectivity and other infrastructure needs,
4) Considering environmental impacts and local community acceptance,
5) Identifying appropriate currency and other financial considerations.

Your primary goal is to suggest **at least three** distinct and viable locations for this project. Each location must be represented as a separate `LocationItem` object within the `locations` list.

For each location, you must provide:

- **item_index**: A unique identifier or enumeration for the location.
- **specific_location**: A precise name or address if the plan already has one (otherwise, leave blank if the location is not pre-defined).
- **suggest_location_broad**: A broad region or country (e.g., “Denmark” or “Northern Denmark”).
- **suggest_location_detail**: A city, municipality, or state/province for narrowing down within the broad region.
- **suggest_location_address**: A specific address or geographic coordinate, if appropriate.
- **rationale_for_suggestion**: A concise explanation of why this location is particularly well-suited for the project, referencing any unique advantages (e.g., abundant sunlight, favorable regulations, existing infrastructure, strong municipal support, research and innovation, etc.).

When selecting each location, carefully consider:

1. **Regulatory Environment and Local Laws**  
   - Are there supportive policies, quick permitting processes, or special economic zones?

2. **Availability of Necessary Resources**  
   - Does the area have enough land, water, power, or other vital resources?  
   - Could brownfield or agricultural land be repurposed?

3. **Access to Infrastructure**  
   - How easy is it to connect to the grid?  
   - Are there major roads, ports, or rail lines for transporting materials and personnel?

4. **Proximity to Potential Customers, Partners, or Suppliers**  
   - Could you benefit from existing hubs of activity or large nearby markets?

5. **Environmental Considerations and Potential Impacts**  
   - Are there protected ecosystems or sensitive habitats?  
   - Will the local community be supportive?

Additionally, if you suggest municipalities in Denmark (or any other country), ensure **accurate regional designations** (e.g., Frederikshavn is in the Region of North Denmark, Herning in the Region of Central Denmark, etc.). If the plan’s description already includes a location, simply confirm and expand it (or provide additional alternatives if relevant). If the plan lacks a location, you must propose multiple well-reasoned site options across different regions.

Remember:

- Provide **at least three** `LocationItem` objects, each with a clear rationale for choosing that location.
- Your response must strictly adhere to the JSON structure defined for `DocumentDetails` and `LocationItem`. 
- For each suggested location, fill in **all** the fields: `item_index`, `specific_location`, `suggest_location_broad`, `suggest_location_detail`, `suggest_location_address`, and `rationale_for_suggestion`.
- Return a high-level summary in the `location_summary` field of the `DocumentDetails` object, describing your overall location strategy and key considerations.

Your final JSON output must not include any additional keys beyond those specified in `DocumentDetails`.
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

    plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")
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
