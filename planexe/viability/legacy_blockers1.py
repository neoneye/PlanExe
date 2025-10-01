"""
Implements Step 2 of the ViabilityAssessor protocol: Blocker Generation.

This script takes the JSON output from Step 1 (Pillars Assessment) and uses an LLM
to generate a list of actionable blockers for all pillars that are not in a 'GREEN' state.
The output is a structured JSON object containing a list of blockers, each with
acceptance tests, required artifacts, an owner, and a Rough Order of Magnitude (ROM) estimate.

PROMPT> python -u -m planexe.viability.legacy_blockers1 | tee output1.txt
"""
import os
import json
import time
import logging
from math import ceil
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, conlist
from llama_index.core.llms import ChatMessage, MessageRole

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Enums and Schemas from README.md ---

class PillarEnum(str, Enum):
    HumanStability = "HumanStability"
    EconomicResilience = "EconomicResilience"
    EcologicalIntegrity = "EcologicalIntegrity"
    Rights_Legality = "Rights_Legality"

class StatusEnum(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    GRAY = "GRAY"

class CostBandEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

# --- Pydantic Models for Input and Output ---

# Step 1: Input Schema (Pillars)
class PillarItem(BaseModel):
    pillar: PillarEnum
    status: StatusEnum
    score: Optional[int]
    reason_codes: List[str] = Field(description="List of issues or reason codes for the pillar's status.")
    evidence_todo: List[str]

class PillarsInput(BaseModel):
    pillars: List[PillarItem]

# Step 2: Output Schema (Blockers)
class ROM(BaseModel):
    cost_band: CostBandEnum
    eta_days: int

class Blocker(BaseModel):
    id: str = Field(description="A unique identifier for the blocker, e.g., 'B1', 'B2'.")
    pillar: PillarEnum = Field(description="The source pillar this blocker is derived from.")
    title: str = Field(description="A concise, descriptive title for the blocker.")
    reason_codes: List[str] = Field(description="A subset of reason codes from the source pillar that this blocker addresses.")
    acceptance_tests: conlist(str, min_length=1, max_length=3) = Field(description="A list of 1-3 specific, verifiable conditions that must be met to resolve the blocker.")
    artifacts_required: conlist(str, min_length=1, max_length=2) = Field(description="A list of 1-2 concrete documents or deliverables required to prove completion.")
    owner: str = Field(description="The role or team responsible for resolving the blocker (e.g., 'PMO', 'Legal', 'Engineering Lead').")
    rom: ROM = Field(description="A Rough Order of Magnitude estimate for cost and time to resolve.")

class BlockersOutput(BaseModel):
    source_pillars: List[PillarEnum] = Field(description="A list of the pillar names that generated blockers.")
    blockers: conlist(Blocker, max_length=5) = Field(description="A list of 3-5 actionable blockers derived from non-GREEN pillars.")

# --- LLM System Prompt ---

BLOCKER_GENERATION_SYSTEM_PROMPT = """
You are a meticulous project risk analyst. Your task is to convert a list of weak project pillars into a concise, actionable set of blockers.
Given a JSON input containing a list of project pillars, you will generate a JSON object of blockers.

Follow these rules precisely:
1.  **Derivation:** Generate blockers ONLY from pillars where the status is 'RED', 'YELLOW', or 'GRAY'. Ignore 'GREEN' pillars completely.
2.  **Quantity:** Create a maximum of 5 blockers in total across all weak pillars. Focus on the most critical issues.
3.  **Schema Adherence:** Your entire output must be a single, valid JSON object that strictly conforms to the provided `BlockersOutput` schema. Do not add any extra text, markdown, or comments.
4.  **Content Generation Rules for each Blocker:**
    - `id`: Assign a sequential ID, starting with "B1".
    - `pillar`: Must be one of the non-GREEN source pillars.
    - `title`: A short, clear title summarizing the problem.
    - `reason_codes`: Must be a subset of the `reason_codes` from the source pillar.
    - `acceptance_tests`: Write 1-3 crisp, verifiable pass/fail conditions. Example: "Contingency budget increased to ≥15% of total project cost."
    - `artifacts_required`: Name 1-2 specific files or documents that would prove the acceptance tests are met. Example: "Budget_v2.xlsx", "Risk_Register_Updated.pdf".
    - `owner`: Assign a plausible team or role, like "PMO", "Legal", "Engineering Lead", or "Finance".
    - `rom`: Provide a realistic Rough Order of Magnitude estimate for cost and time.
"""

# --- Main Application Logic ---

@dataclass
class BlockerGenerationResult:
    system_prompt: str
    user_prompt: str  # The JSON of non-green pillars sent to the LLM
    response: dict    # The parsed JSON output from the LLM
    metadata: dict

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        """Converts the result to a dictionary for inspection."""
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_json(self, file_path: str, include_full_context=False) -> None:
        """Saves the output to a JSON file."""
        data_to_save = self.response
        if include_full_context:
            data_to_save = self.to_dict()

        with open(file_path, 'w', encoding='utf-f') as f:
            json.dump(data_to_save, f, indent=2)
        logger.info(f"Blocker data saved to {file_path}")

class BlockerGenerator:
    @classmethod
    def execute(cls, llm: LLM, pillars_json: str) -> 'BlockerGenerationResult':
        """
        Takes the JSON from Step 1 (Pillars) and generates the JSON for Step 2 (Blockers).
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")

        # 1. Parse and filter input from Step 1
        try:
            pillars_data = json.loads(pillars_json)
            validated_input = PillarsInput.model_validate(pillars_data)

            non_green_pillars = [
                p for p in validated_input.pillars if p.status != StatusEnum.GREEN
            ]

            if not non_green_pillars:
                logger.info("No non-GREEN pillars found. No blockers to generate.")
                return BlockerGenerationResult(
                    system_prompt=BLOCKER_GENERATION_SYSTEM_PROMPT.strip(),
                    user_prompt=json.dumps({"pillars": []}),
                    response=BlockersOutput(source_pillars=[], blockers=[]).model_dump(),
                    metadata={"status": "No non-GREEN pillars provided."}
                )

            llm_input_data = {"pillars": [p.model_dump(mode='json') for p in non_green_pillars]}
            user_prompt = json.dumps(llm_input_data, indent=2)

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse or validate input pillars JSON: {e}", exc_info=True)
            raise ValueError("Invalid input JSON for pillars.") from e

        # 2. Prepare and execute LLM call
        system_prompt = BLOCKER_GENERATION_SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        sllm = llm.as_structured_llm(BlockersOutput)
        start_time = time.perf_counter()

        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(json.dumps(chat_response.raw.model_dump()).encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        # 3. Package and return results
        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = BlockerGenerationResult(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=chat_response.raw.model_dump(),
            metadata=metadata,
        )
        logger.debug("BlockerGenerationResult instance created successfully.")
        return result

if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    # This input is derived from the "Pillars Assessment" section of the report.
    PILLARS_ASSESSMENT_INPUT = {
      "pillars": [
        {
          "pillar": "HumanStability",
          "status": "RED",
          "score": 20,
          "reason_codes": ["GOVERNANCE_WEAK", "STAKEHOLDER_CONFLICT", "CHANGE_MGMT_GAPS"],
          "evidence_todo": ["Social unrest mitigation plan v1", "Resident mental health support plan v2"]
        },
        {
          "pillar": "EconomicResilience",
          "status": "YELLOW",
          "score": 55,
          "reason_codes": ["CONTINGENCY_LOW", "UNIT_ECON_UNKNOWN"],
          "evidence_todo": ["Contingency budget v2", "Unit economics model v3 + sensitivity table"]
        },
        {
          "pillar": "EcologicalIntegrity",
          "status": "RED",
          "score": 20,
          "reason_codes": ["EIA_MISSING", "BIODIVERSITY_RISK_UNSET", "WASTE_MANAGEMENT_GAPS"],
          "evidence_todo": ["Ecosystem risk mitigation plan v1", "Waste management plan v2"]
        },
        {
          "pillar": "Rights_Legality",
          "status": "YELLOW",
          "score": 55,
          "reason_codes": ["DPIA_GAPS", "INFOSEC_GAPS", "ETHICS_VAGUE"],
          "evidence_todo": ["Data protection impact assessment v1", "Ethics review board charter v1"]
        }
      ]
    }

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    input_json_str = json.dumps(PILLARS_ASSESSMENT_INPUT)
    input_bytes_count = len(input_json_str.encode('utf-8'))
    print(f"--- Input (Pillars Assessment) ---\nByte Count: {input_bytes_count}\n")
    print(json.dumps(PILLARS_ASSESSMENT_INPUT, indent=2))

    # Generate Blockers
    result = BlockerGenerator.execute(llm, input_json_str)

    output_bytes_count = len(json.dumps(result.response).encode('utf-8'))
    print(f"\n--- Output (Generated Blockers) ---\nByte Count: {output_bytes_count}\n")
    print(json.dumps(result.response, indent=2))

    # Optionally save the output to a file
    # result.save_json("blockers_output.json")