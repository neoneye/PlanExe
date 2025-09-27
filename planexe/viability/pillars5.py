"""
Step 1: Pillar Assessment

This script is the first step in the 4-part ViabilityAssessor protocol.
It takes a plan synopsis as input and assesses it against four core pillars:
- HumanStability
- EconomicResilience
- EcologicalIntegrity
- Rights_Legality

The script uses a large language model (LLM) to analyze the plan and generates a
structured JSON output containing a score, color rating, reason codes, and
evidence to-do list for each pillar. This output serves as the foundational
input for the subsequent steps in the assessment pipeline (Blockers, Fix Packs,
and Overall Summary).

The primary goal is to establish an authoritative, evidence-gated scope for the
viability assessment, ensuring that risks and weaknesses are framed within these
four deterministic categories.

PROMPT> python -m planexe.viability.pillars5
"""
import os
import json
import time
import logging
from math import ceil
from typing import Optional, List, Literal, Dict
from enum import Enum
from dataclasses import dataclass

from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, conint
from llama_index.core.llms import ChatMessage, MessageRole

logger = logging.getLogger(__name__)

# --- Enums and Constants based on README.md ---

class PillarEnum(str, Enum):
    HUMAN_STABILITY = "HumanStability"
    ECONOMIC_RESILIENCE = "EconomicResilience"
    ECOLOGICAL_INTEGRITY = "EcologicalIntegrity"
    RIGHTS_LEGALITY = "Rights_Legality"

class ColorEnum(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    GRAY = "GRAY"

REASON_CODE_ENUM_VALUES = [
    "CONTINGENCY_LOW", "SINGLE_CUSTOMER", "ALT_COST_UNKNOWN", "DPIA_GAPS",
    "LICENSE_GAPS", "ABS_UNDEFINED", "PERMIT_COMPLEXITY", "LEGACY_IT",
    "INTEGRATION_RISK", "TALENT_UNKNOWN", "STAFF_AVERSION",
    "CLOUD_CARBON_UNKNOWN", "CLIMATE_UNQUANTIFIED", "WATER_STRESS",
    "BIOSECURITY_GAPS", "ETHICS_VAGUE"
]

# --- Pydantic Models for Structured Output (Step 1) ---

class PillarItem(BaseModel):
    """Represents the assessment of a single pillar."""
    pillar: PillarEnum = Field(description="The specific CAS pillar being assessed.")
    color: ColorEnum = Field(description="The assessed color rating for the pillar (GREEN, YELLOW, RED, GRAY).")
    score: Optional[conint(ge=0, le=100)] = Field(
        description="A numerical score (0-100) corresponding to the color. Must be in the valid range for the color. Null for GRAY."
    )
    reason_codes: List[str] = Field(
        description="A list of stable, short codes explaining the rating, drawn from the provided enum list."
    )
    evidence_todo: List[str] = Field(
        description="A list of specific, actionable items needed to gather evidence to improve the pillar's score. Must be empty if the color is GREEN."
    )

class RulesApplied(BaseModel):
    """Documents the rules used for the assessment."""
    color_to_score: Dict[str, Optional[List[int]]] = Field(description="The mapping of colors to score ranges.")
    evidence_gate: str = Field(description="The rule stating that a GREEN rating requires an empty 'evidence_todo' list.")

class PillarsOutput(BaseModel):
    """The root model for the JSON output of the pillar assessment step."""
    pillars: List[PillarItem] = Field(
        description="An array of assessment objects, one for each of the four CAS pillars.",
        min_items=4,
        max_items=4
    )
    rules_applied: RulesApplied = Field(description="The rules the assessment was based on.")

# --- System Prompt for the LLM (Step 1) ---

PILLARS_SYSTEM_PROMPT = f"""
You are a meticulous Viability Assessor. Your task is to analyze the provided plan synopsis and produce a viability assessment for the four core CAS pillars.
Your entire output must be a single, valid JSON object that strictly adheres to the schema provided below. Do not include any extra text, markdown, or explanations.

**JSON Schema:**
{{
  "pillars": [
    {{
      "pillar": "string", // Must be one of {list(PillarEnum.__members__.values())}
      "color": "string",  // Must be one of {list(ColorEnum.__members__.values())}
      "score": "integer | null", // 0-100, must match color band
      "reason_codes": ["string"], // Must be from REASON_CODE_ENUM
      "evidence_todo": ["string"] // List of actions
    }}
  ],
  "rules_applied": {{
    "color_to_score": {{ "GREEN": [70,100], "YELLOW": [40,69], "RED": [0,39], "GRAY": null }},
    "evidence_gate": "No GREEN unless evidence_todo is empty"
  }}
}}

**Instructions & Rules:**

1.  **Pillars:** You must assess exactly these four pillars: `HumanStability`, `EconomicResilience`, `EcologicalIntegrity`, `Rights_Legality`.
2.  **Enums:** Use only the following values for the specified fields:
    *   `pillar`: {list(PillarEnum.__members__.values())}
    *   `color`: {list(ColorEnum.__members__.values())}
    *   `reason_codes`: {REASON_CODE_ENUM_VALUES}
3.  **Color & Score:**
    *   Assign a `color` based on your assessment of the plan's strengths and weaknesses for that pillar.
    *   If `color` is `GRAY`, it means there is insufficient information to make an assessment. The `score` must be `null`.
    *   For `RED`, `YELLOW`, or `GREEN`, assign a `score` that falls within its corresponding range: `RED`: 0-39, `YELLOW`: 40-69, `GREEN`: 70-100.
4.  **Evidence Gating (CRITICAL RULE):** A pillar can **only** be rated `GREEN` if its `evidence_todo` list is empty. If there is anything that needs to be done to provide more evidence, the pillar cannot be GREEN.
5.  **Reason Codes:** For each pillar, select one or more relevant codes from the `reason_codes` enum list that justify your `color` rating.
6.  **Evidence To-Do:** List concrete, actionable items required to strengthen the pillar and potentially improve its score.
7.  **Rules Applied:** The `rules_applied` object in your output must be copied **exactly** as it appears in the schema above.

Analyze the following plan and generate the JSON output.
"""

@dataclass
class PillarAssessor:
    system_prompt: Optional[str]
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'PillarAssessor':
        """
        Invokes an LLM to perform Step 1 (Pillar Assessment) of the ViabilityAssessor protocol.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        system_prompt = PILLARS_SYSTEM_PROMPT.strip()
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

        sllm = llm.as_structured_llm(PillarsOutput)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(json.dumps(chat_response.raw.model_dump()).encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = PillarAssessor(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        logger.debug("PillarAssessor instance created successfully.")
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

    def save_json(self, file_path: str) -> None:
        """Saves the raw JSON output to a file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    # Using the detailed "Project Plan" section from 20250908_sia_mvp_report.html as input
    plan_synopsis = """
    Goal Statement: Build a Shared Intelligence Asset MVP for one regulator in one jurisdiction 
    (energy-market interventions only) with advisory use first and a Binding Use Charter considered 
    after measured decision-quality lift within 30 months.
    
    SMART Criteria: The project aims to develop a functional MVP for energy-market interventions, 
    measured by CAS generation, gate adherence, and KPIs. It is considered achievable within 30 months 
    and a CHF 15 million budget.
    
    Dependencies: Success relies on establishing five 'hard gates': G1 (CAS v0.1), G2 (Data Rights), 
    G3 (Sovereign Cloud Architecture), G4 (Model Validation), and G5 (Portal & Process).
    
    Resources Required: Sovereign cloud region, per-tenant KMS/HSM, legal expertise for data rights, 
    and an independent council (judiciary, civil society, scientists, auditors).
    
    Risk Assessment: Key risks include regulatory changes, technical challenges, financial constraints, 
    and security vulnerabilities. Mitigation involves legal counsel, expert teams, strict budget control, 
    and robust cybersecurity measures.
    
    Stakeholders: Primary stakeholders are the regulator and project team. Secondary stakeholders include 
    energy companies, consumer advocates, and the public.
    
    Regulatory Compliance: The project must comply with Swiss laws like FADP and StromVG, overseen by 
    the FDPIC and SFOE.
    """

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    query = plan_synopsis.strip()
    input_bytes_count = len(query.encode('utf-8'))
    print(f"--- Input Plan Synopsis (Bytes: {input_bytes_count}) ---\n{query}")
    
    result = PillarAssessor.execute(llm, query)

    print("\n--- JSON Response ---")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    output_bytes_count = len(json.dumps(json_response).encode('utf-8'))
    print(f"\n--- Stats ---")
    print(f"Input bytes:  {input_bytes_count}")
    print(f"Output bytes: {output_bytes_count}")
    
    # Example of saving the output
    # output_filename = "step1_pillars_output.json"
    # result.save_json(output_filename)
    # print(f"\nSaved output to {output_filename}")