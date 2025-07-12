"""
This was generated with Cursor, possibly using Claude 3.5 Sonnet.
This is crap.

Narrow down potential levers to the vital few by identifying the most strategic levers and removing the rest (duplicates and less impactful levers).

https://en.wikipedia.org/wiki/Pareto_principle

This module analyzes lever lists to identify:
- Duplicate levers (near identical or similar strategic dimensions)
- Less impactful levers (levers that don't align with core project objectives)

The result is a cleaner, more focused list of essential strategic levers.

PROMPT> python -m planexe.strategic_variant_analysis.filter_levers_legacy1_claude
"""
import os
import json
import time
import logging
from math import ceil
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from planexe.assume.identify_purpose import IdentifyPurpose, PlanPurposeInfo, PlanPurpose

logger = logging.getLogger(__name__)

# The number of levers to keep. It may be less or greater than this number
# Ideally we don't want to throw away any strategic levers.
# There can be +20 levers and then it can be overwhelming to keep an overview.
# Thus only focus on the most important strategic levers.
PREFERRED_LEVER_COUNT = 5

class LeverImpact(str, Enum):
    """Enum to indicate the assessed impact of a lever for strategic decision-making."""
    critical = 'Critical' # Absolutely essential for strategic success, major outcome driver
    high = 'High'         # Very important for key strategic decisions and outcomes
    medium = 'Medium'     # Useful for context or less critical strategic dimensions
    low = 'Low'           # Minor relevance for strategic outcomes or needed much later

class LeverItem(BaseModel):
    id: int = Field(
        description="The ID of the lever being evaluated."
    )
    rationale: str = Field(
        description="The reason justifying the assigned impact rating, linked to the project plan's critical strategic goals, risks, or decision points."
    )
    impact_rating: LeverImpact = Field(
        description="The assessed impact level of the lever for strategic decision-making, based on the 80/20 principle."
    )

class LeverImpactAssessmentResult(BaseModel):
    """The result of assessing the impact of a list of levers."""
    lever_list: List[LeverItem] = Field(
        description="List of levers with their assessed impact rating for strategic decision-making."
    )
    summary: str = Field(
        description="A summary highlighting the critical and high impact levers identified as most vital for strategic success (80/20)."
    )

FILTER_LEVERS_TO_VITAL_FEW_SYSTEM_PROMPT = """
You are an expert AI assistant specializing in strategic lever prioritization, applying the 80/20 principle (Pareto principle). Your task is to analyze a list of potential strategic levers (from user input) against a provided project plan (also from user input). Evaluate each lever's **impact** on the **project success**, regardless of whether it's a business venture, personal goal, scientific research, technical implementation, or any other type of project.

**Goal:** Identify the vital few levers (the '20%') that will drive the most value (the '80%') for the project. This means focusing on levers essential for:
1.  **Core Project Success:** What makes this project achieve its fundamental objectives? (e.g., business profitability, personal fulfillment, scientific discovery, technical breakthrough)
2.  **Major Outcome Drivers:** Which levers most significantly affect the project's key success metrics? (e.g., cost, time, quality, risk, accuracy, performance, satisfaction, learning)
3.  **Critical Decision Points:** Which levers represent the most important choices that will shape the project's trajectory?
4.  **Resource Allocation Impact:** Which levers most affect how critical resources are deployed? (e.g., time, money, talent, energy, data, tools, relationships)

**Output Format:**
Respond with a JSON object matching the `LeverImpactAssessmentResult` schema. For each lever:
- Provide its original `id`.
- Assign an `impact_rating` using the `LeverImpact` enum ('Critical', 'High', 'Medium', 'Low').
- Provide a detailed `rationale` explaining *why* that specific impact rating was chosen. **The rationale MUST link the lever's strategic dimension directly to critical project goals, major risks, key decisions, essential outcomes, or strategic uncertainties mentioned in the provided project plan.**

**Impact Rating Definitions (Assign ONE per lever):**
- **Critical:** Absolutely essential for project success. The project cannot achieve its core objectives, major competitive/personal/technical advantage cannot be established, or a top-tier risk (per the plan) cannot be addressed without this lever. Represents a non-negotiable strategic dimension. (This is the core of the 80/20 focus). *Examples: Core technology choice for a spaceship, fundamental diet approach for weight loss, primary research methodology for microplastics study.*
- **High:** Very important for project success. Significantly affects major project outcomes, enables core strategic decisions, provides essential competitive/personal/technical positioning, or addresses a significant risk. *Examples: Manufacturing approach for spaceship components, exercise strategy for weight loss, data collection methods for research.*
- **Medium:** Useful for project context. Supports secondary objectives, provides background strategic options, or addresses lower-priority risks/tasks. Helpful but not strictly required for the *most critical* decisions/outcomes. *Examples: Supplier selection for spaceship parts, social support strategy for weight loss, auxiliary analysis techniques for research.*
- **Low:** Minor relevance for *project success*. Might be useful for tactical implementation, provides tangential information, or is superseded by higher-impact levers. *Examples: Minor optimization techniques, peripheral habit changes, optional research extensions.*

**Rationale Requirements (MANDATORY):**
- **MUST** justify the assigned `impact_rating`.
- **MUST** explicitly reference elements from the **user-provided project plan** (e.g., "Needed to address Risk #1 identified in the plan," "Provides the competitive advantage mentioned in the market analysis," "Required for the 'Cost Optimization' goal," "Essential for the 'Research Methodology' specified").
- **Consider Overlap:** If two levers control similar strategic dimensions, assign the highest rating to the most comprehensive or foundational one. Note the overlap in the rationale of the lower-rated lever (e.g., "High: Provides important strategic context, though some overlaps with ID [X]'s critical dimension."). Avoid assigning 'Critical' to multiple highly overlapping levers unless truly distinct strategic aspects are covered.

**Forbidden Rationales:** Single words or generic phrases without linkage to the plan.

**Final Output:**
Produce a single JSON object containing `lever_list` (with impact ratings and detailed, plan-linked rationales) and a `summary`.

The `summary` MUST provide a qualitative assessment based on the impact ratings you assigned:
1.  **Strategic Relevance Distribution:** Characterize the overall list. Were most levers low impact ('Low'/'Medium'), indicating the initial list was broad or unfocused strategically? Or were many levers assessed as 'High' or 'Critical', suggesting the list was generally relevant to project success?
2.  **Prioritization Clarity:** Comment on how easy it was to apply the 80/20 rule. Was there a clear distinction with only a few 'Critical'/'High' impact levers standing out? Or were there many levers clustered in the 'High'/'Medium' categories, making it difficult to isolate the truly vital few? **Do NOT simply list the levers in the summary.**

Strictly adhere to the schema and instructions, especially for the `rationale` and the new `summary` requirements.
"""

@dataclass
class FilterLeversToVitalFew:
    """
    Analyzes lever lists to identify duplicates and less impactful levers.
    """
    system_prompt: str
    user_prompt: str
    identified_levers_raw_json: list[dict]
    integer_id_to_lever_uuid: dict[int, str]
    response: dict
    assessment_result: LeverImpactAssessmentResult
    metadata: dict
    ids_to_keep: set[int]
    uuids_to_keep: set[str]
    filtered_levers_raw_json: list[dict]

    @staticmethod
    def process_levers_and_integer_ids(identified_levers_raw_json: list[dict]) -> tuple[list[dict], dict[int, str]]:
        """
        Prepare the levers for processing by the LLM.

        Reduce the number of fields in the levers to just the lever name and the lever description.
        Avoid using the uuid as the id, since it tends to confuse the LLM.
        Instead of uuid, use an integer id.
        """
        if not isinstance(identified_levers_raw_json, list):
            raise ValueError("identified_levers_raw_json is not a list.")

        # Only keep the 'lever_name' and 'description' from each lever and remove the rest.
        # Enumerate the levers with an integer id.
        process_levers = []
        integer_id_to_lever_uuid = {}
        for lever in identified_levers_raw_json:
            if 'lever_name' not in lever or 'description' not in lever or 'id' not in lever:
                logger.error(f"Lever is missing required keys: {lever}")
                continue

            lever_name = lever.get('lever_name', '')
            lever_description = lever.get('description', '')
            lever_id = lever.get('id', '')

            current_index = len(process_levers)

            name = f"{lever_name}\n{lever_description}"
            dict_item = {
                'id': current_index,
                'name': name
            }
            process_levers.append(dict_item)
            integer_id_to_lever_uuid[current_index] = lever_id

        return process_levers, integer_id_to_lever_uuid

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str, identified_levers_raw_json: list[dict], integer_id_to_lever_uuid: dict[int, str], identify_purpose_dict: Optional[dict]) -> 'FilterLeversToVitalFew':
        """
        Invoke LLM with the lever details to analyze.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        if identify_purpose_dict is not None and not isinstance(identify_purpose_dict, dict):
            raise ValueError("Invalid identify_purpose_dict.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        if identify_purpose_dict is None:
            logging.info("No identify_purpose_dict provided, identifying purpose.")
            identify_purpose = IdentifyPurpose.execute(llm, user_prompt)
            identify_purpose_dict = identify_purpose.to_dict()
        else:
            logging.info("identify_purpose_dict provided, using it.")

        # Parse the identify_purpose_dict
        logging.debug(f"IdentifyPurpose json {json.dumps(identify_purpose_dict, indent=2)}")
        try:
            purpose_info = PlanPurposeInfo(**identify_purpose_dict)
        except Exception as e:
            logging.error(f"Error parsing identify_purpose_dict: {e}")
            raise ValueError("Error parsing identify_purpose_dict.") from e

        # Use the unified system prompt for all project types
        logging.info(f"FilterLeversToVitalFew.execute: purpose: {purpose_info.purpose}")
        system_prompt = FILTER_LEVERS_TO_VITAL_FEW_SYSTEM_PROMPT

        system_prompt = system_prompt.strip()

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

        sllm = llm.as_structured_llm(LeverImpactAssessmentResult)
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

        assessment_result = chat_response.raw

        ids_to_keep = cls.extract_integer_ids_to_keep(assessment_result)
        uuids_to_keep_list = [integer_id_to_lever_uuid[integer_id] for integer_id in ids_to_keep]
        uuids_to_keep = set(uuids_to_keep_list)

        # remove the levers that are not in the uuids_to_keep
        filtered_levers_raw_json = [lever for lever in identified_levers_raw_json if lever['id'] in uuids_to_keep]

        logger.info(f"IDs to keep: {ids_to_keep}")
        logger.info(f"UUIDs to keep: {uuids_to_keep}")
        logger.info(f"Filtered levers raw json length: {len(filtered_levers_raw_json)}")

        if len(filtered_levers_raw_json) != len(ids_to_keep):
            logger.info(f"identified_levers_raw_json: {json.dumps(identified_levers_raw_json, indent=2)}")
            logger.error(f"Filtered levers raw json length ({len(filtered_levers_raw_json)}) does not match ids_to_keep length ({len(ids_to_keep)}).")
            raise ValueError("Filtered levers raw json length does not match ids_to_keep length.")
    
        result = FilterLeversToVitalFew(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            identified_levers_raw_json=identified_levers_raw_json,
            integer_id_to_lever_uuid=integer_id_to_lever_uuid,
            response=json_response,
            assessment_result=assessment_result,
            metadata=metadata,
            ids_to_keep=ids_to_keep,
            uuids_to_keep=uuids_to_keep,
            filtered_levers_raw_json=filtered_levers_raw_json
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

    def save_filtered_levers(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.filtered_levers_raw_json, indent=2))

    @staticmethod
    def extract_integer_ids_to_keep(result: LeverImpactAssessmentResult) -> set[int]:
        """
        Extract the most important levers from the result.
        """
        ids_to_critical = set()
        ids_to_high = set()
        ids_to_medium = set()
        ids_to_low = set()
        for item in result.lever_list:
            if item.impact_rating == LeverImpact.critical:
                ids_to_critical.add(item.id)
            elif item.impact_rating == LeverImpact.high:
                ids_to_high.add(item.id)
            elif item.impact_rating == LeverImpact.medium:
                ids_to_medium.add(item.id)
            elif item.impact_rating == LeverImpact.low:
                ids_to_low.add(item.id)
            else:
                logger.error(f"Invalid impact_rating value: {item.impact_rating}, lever_id: {item.id}. Removing the lever.")
        
        ids_to_keep = set()
        ids_to_keep.update(ids_to_critical)
        if len(ids_to_keep) < PREFERRED_LEVER_COUNT:
            ids_to_keep.update(ids_to_high)
        if len(ids_to_keep) < PREFERRED_LEVER_COUNT:
            ids_to_keep.update(ids_to_medium)
        if len(ids_to_keep) < PREFERRED_LEVER_COUNT:
            ids_to_keep.update(ids_to_low)

        if len(ids_to_keep) < PREFERRED_LEVER_COUNT:
            logger.info(f"Fewer levers to keep than the desired count. Only {len(ids_to_keep)} levers found.")

        return ids_to_keep

if __name__ == "__main__":
    from planexe.llm_factory import get_llm
    from planexe.plan.find_plan_prompt import find_plan_prompt

    plan_prompt = find_plan_prompt("19dc0718-3df7-48e3-b06d-e2c664ecc07d")

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("openrouter-paid-gemini-2.0-flash-001")

    # Load test data from file
    test_data_file = "planexe/strategic_variant_analysis/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt"
    
    with open(test_data_file, 'r') as f:
        test_data_content = f.read()
    
    # Extract the JSON part from the test data
    import re
    # Look for the JSON array that starts after "file: 'potential_levers.json':"
    json_match = re.search(r'file: \'potential_levers\.json\':\n(\[.*\])', test_data_content, re.DOTALL)
    if json_match:
        identified_levers_raw_json = json.loads(json_match.group(1))
    else:
        raise ValueError("Could not extract JSON from test data file")
    
    # Convert the lever format to match expected structure
    # The test data has 'name' field, but the code expects 'lever_name' and 'description'
    for lever in identified_levers_raw_json:
        if 'name' in lever:
            lever['lever_name'] = lever['name']
            lever['description'] = f"Options: {', '.join(lever.get('options', []))}. Consequences: {lever.get('consequences', '')}"

    process_levers, integer_id_to_lever_uuid = FilterLeversToVitalFew.process_levers_and_integer_ids(identified_levers_raw_json)

    print(f"integer_id_to_lever_uuid: {integer_id_to_lever_uuid}")

    query = (
        f"File 'plan.txt':\n{plan_prompt}\n\n"
        f"File 'levers.json':\n{process_levers}"
    )
    print(f"Query:\n{query}\n\n")

    result = FilterLeversToVitalFew.execute(llm, query, identified_levers_raw_json, integer_id_to_lever_uuid, identify_purpose_dict=None)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nIDs to keep:\n{result.ids_to_keep}")
    print(f"\n\nUUIDs to keep:\n{result.uuids_to_keep}")

    print(f"\n\nFiltered levers:")
    print(json.dumps(result.filtered_levers_raw_json, indent=2)) 