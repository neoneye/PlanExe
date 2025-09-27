"""
Step 1: Pillars Assessment - Establish the authoritative scope and evidence gates.

This module implements the first step of the ViabilityAssessor protocol:
- Scores the plan on four CAS pillars (HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality)
- Maps scores to traffic light colors (GREEN, YELLOW, RED, GRAY)
- Implements evidence gating (GREEN requires evidence_todo to be empty)
- Provides validation and auto-repair functionality

Based on the README specifications for Step 1 of the ViabilityAssessor protocol.

Key Features:
- Structured Pydantic models for type safety and validation
- Comprehensive enum definitions for pillars, colors, and reason codes
- Auto-repair validation that fixes common LLM output issues
- Evidence gating to prevent false GREEN assessments
- Markdown output for human-readable reports
- Follows the same patterns as executive_summary.py for consistency

PROMPT> python -m planexe.viability.pillars1
"""
import json
import time
import logging
from math import ceil
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists

logger = logging.getLogger(__name__)

class PillarEnum(str, Enum):
    """The four CAS pillars for viability assessment."""
    HUMAN_STABILITY = "HumanStability"
    ECONOMIC_RESILIENCE = "EconomicResilience"
    ECOLOGICAL_INTEGRITY = "EcologicalIntegrity"
    RIGHTS_LEGALITY = "Rights_Legality"

class ColorEnum(str, Enum):
    """Traffic light colors for pillar assessment."""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    GRAY = "GRAY"

class ReasonCodeEnum(str, Enum):
    """Small, stable set of reason codes for pillar issues."""
    # Budget/Finance
    CONTINGENCY_LOW = "CONTINGENCY_LOW"
    SINGLE_CUSTOMER = "SINGLE_CUSTOMER"
    ALT_COST_UNKNOWN = "ALT_COST_UNKNOWN"
    
    # Rights/Compliance
    DPIA_GAPS = "DPIA_GAPS"
    LICENSE_GAPS = "LICENSE_GAPS"
    ABS_UNDEFINED = "ABS_UNDEFINED"
    PERMIT_COMPLEXITY = "PERMIT_COMPLEXITY"
    
    # Tech/Integration
    LEGACY_IT = "LEGACY_IT"
    INTEGRATION_RISK = "INTEGRATION_RISK"
    
    # People/Adoption
    TALENT_UNKNOWN = "TALENT_UNKNOWN"
    STAFF_AVERSION = "STAFF_AVERSION"
    
    # Climate/Ecology
    CLOUD_CARBON_UNKNOWN = "CLOUD_CARBON_UNKNOWN"
    CLIMATE_UNQUANTIFIED = "CLIMATE_UNQUANTIFIED"
    WATER_STRESS = "WATER_STRESS"
    
    # Biosecurity
    BIOSECURITY_GAPS = "BIOSECURITY_GAPS"
    
    # Governance/Ethics
    ETHICS_VAGUE = "ETHICS_VAGUE"

# Color to score mapping from README
COLOR_TO_SCORE = {
    ColorEnum.GREEN: (70, 100),
    ColorEnum.YELLOW: (40, 69),
    ColorEnum.RED: (0, 39),
    ColorEnum.GRAY: None
}

def get_color_band_midpoint(color: ColorEnum) -> int:
    """Get the midpoint score for a color band."""
    band = COLOR_TO_SCORE.get(color)
    if band is None:  # GRAY
        return 50  # Default for unknown
    return (band[0] + band[1]) // 2

def validate_score_in_band(score: int, color: ColorEnum) -> bool:
    """Check if score falls within the color band."""
    band = COLOR_TO_SCORE.get(color)
    if band is None:  # GRAY
        return True  # Any score is valid for GRAY
    return band[0] <= score <= band[1]

class PillarItem(BaseModel):
    """Individual pillar assessment result."""
    pillar: PillarEnum = Field(description="The CAS pillar being assessed")
    color: ColorEnum = Field(description="Traffic light color based on score")
    score: Optional[int] = Field(None, description="Numeric score 0-100, must match color band")
    reason_codes: Optional[List[ReasonCodeEnum]] = Field(None, description="Specific issues identified")
    evidence_todo: Optional[List[str]] = Field(None, description="Evidence gathering tasks for GRAY pillars")

class RulesApplied(BaseModel):
    """Rules applied during pillar assessment."""
    color_to_score: Dict[str, Optional[List[int]]] = Field(
        default_factory=lambda: {
            "GREEN": [70, 100],
            "YELLOW": [40, 69], 
            "RED": [0, 39],
            "GRAY": None
        },
        description="Color to score band mapping"
    )
    evidence_gate: str = Field(
        default="No GREEN unless evidence_todo is empty",
        description="Evidence gating rule"
    )

class PillarsResult(BaseModel):
    """Complete pillars assessment result."""
    pillars: List[PillarItem] = Field(description="Assessment results for all four pillars")
    rules_applied: RulesApplied = Field(default_factory=RulesApplied, description="Rules used in assessment")

PILLARS_SYSTEM_PROMPT = """
You are an expert in viability assessment specializing in the four CAS pillars framework. Your task is to assess a plan against four critical pillars and output a valid JSON object that strictly adheres to the schema below.

The four CAS pillars are:
- HumanStability: People, teams, stakeholder buy-in, organizational readiness
- EconomicResilience: Financial viability, budget, contingency, market risks
- EcologicalIntegrity: Environmental impact, sustainability, climate considerations
- Rights_Legality: Legal compliance, data protection, permits, ethical considerations

For each pillar, you must:
1. Assign a color: GREEN (70-100), YELLOW (40-69), RED (0-39), or GRAY (unknown/insufficient info)
2. Provide a numeric score that matches the color band (required except for GRAY)
3. Identify specific reason_codes from the predefined list if issues exist
4. List evidence_todo items for GRAY pillars or when evidence is insufficient

CRITICAL RULES:
- GREEN requires evidence_todo to be empty (no outstanding evidence gathering)
- If evidence is incomplete, use YELLOW or GRAY, not GREEN
- GRAY pillars must have evidence_todo items
- Score must fall within the color band ranges
- Use only the predefined reason_codes and pillars

Output JSON only with exactly this structure:

{
  "pillars": [
    {
      "pillar": "HumanStability|EconomicResilience|EcologicalIntegrity|Rights_Legality",
      "color": "GREEN|YELLOW|RED|GRAY",
      "score": 85,
      "reason_codes": ["REASON_CODE_1", "REASON_CODE_2"],
      "evidence_todo": ["Evidence task 1", "Evidence task 2"]
    }
  ],
  "rules_applied": {
    "color_to_score": {"GREEN":[70,100], "YELLOW":[40,69], "RED":[0,39], "GRAY":null},
    "evidence_gate": "No GREEN unless evidence_todo is empty"
  }
}

Remember: Your output must be valid JSON and nothing else.
"""

@dataclass
class PillarsAssessment:
    """Container for pillars assessment results."""
    system_prompt: Optional[str]
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'PillarsAssessment':
        """
        Execute pillars assessment using the LLM.
        
        Args:
            llm: LLM instance for assessment
            user_prompt: Plan text to assess
            
        Returns:
            PillarsAssessment with results
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

        sllm = llm.as_structured_llm(PillarsResult)
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

        # Validate and auto-repair the response
        validated_response = cls._validate_and_repair(chat_response.raw.model_dump())

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        markdown = cls.convert_to_markdown(validated_response)

        result = PillarsAssessment(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=validated_response,
            markdown=markdown,
            metadata=metadata,
        )
        logger.debug("PillarsAssessment instance created successfully.")
        return result

    @staticmethod
    def _validate_and_repair(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and auto-repair pillar assessment data.
        
        Implements the validation rules from README:
        - Enum checks: drop unknown fields; coerce invalid enum values to defaults
        - Color/score sync: enforce color_to_score bands; if score missing, set to band midpoint
        - Evidence gate: if color="GREEN" and evidence_todo not empty → downgrade to YELLOW
        - Defaults: ensure all required fields are present
        """
        if "pillars" not in data:
            data["pillars"] = []
        
        validated_pillars = []
        for pillar_data in data["pillars"]:
            # Validate pillar enum
            try:
                pillar = PillarEnum(pillar_data.get("pillar", "Rights_Legality"))
            except ValueError:
                pillar = PillarEnum.RIGHTS_LEGALITY
                pillar_data["pillar"] = pillar.value

            # Validate color enum
            try:
                color = ColorEnum(pillar_data.get("color", "GRAY"))
            except ValueError:
                color = ColorEnum.GRAY
                pillar_data["color"] = color.value

            # Evidence gating: GREEN requires evidence_todo to be empty
            evidence_todo = pillar_data.get("evidence_todo", [])
            if color == ColorEnum.GREEN and evidence_todo:
                color = ColorEnum.YELLOW
                pillar_data["color"] = color.value

            # Validate and fix score
            score = pillar_data.get("score")
            if score is not None:
                if not validate_score_in_band(score, color):
                    score = get_color_band_midpoint(color)
                    pillar_data["score"] = score
            else:
                # Set score to band midpoint if missing
                score = get_color_band_midpoint(color)
                pillar_data["score"] = score

            # Validate reason_codes
            reason_codes = pillar_data.get("reason_codes", [])
            if reason_codes:
                validated_reason_codes = []
                for code in reason_codes:
                    try:
                        validated_reason_codes.append(ReasonCodeEnum(code).value)
                    except ValueError:
                        # Skip invalid reason codes
                        continue
                pillar_data["reason_codes"] = validated_reason_codes

            # Ensure evidence_todo exists for GRAY pillars
            if color == ColorEnum.GRAY and not evidence_todo:
                pillar_data["evidence_todo"] = ["Gather evidence for assessment"]

            validated_pillars.append(pillar_data)

        data["pillars"] = validated_pillars
        
        # Ensure rules_applied is present
        if "rules_applied" not in data:
            data["rules_applied"] = {
                "color_to_score": {
                    "GREEN": [70, 100],
                    "YELLOW": [40, 69],
                    "RED": [0, 39],
                    "GRAY": None
                },
                "evidence_gate": "No GREEN unless evidence_todo is empty"
            }

        return data

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        """Convert to dictionary representation."""
        d = self.response.copy()
        d['markdown'] = self.markdown
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        """Save raw JSON response to file."""
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

    @staticmethod
    def convert_to_markdown(data: Dict[str, Any]) -> str:
        """Convert pillar assessment to markdown format."""
        rows = []
        rows.append("# Pillars Assessment")
        rows.append("")
        
        # Add summary
        pillars = data.get("pillars", [])
        color_counts = {"GREEN": 0, "YELLOW": 0, "RED": 0, "GRAY": 0}
        for pillar in pillars:
            color = pillar.get("color", "GRAY")
            if color in color_counts:
                color_counts[color] += 1
        
        rows.append("## Summary")
        rows.append(f"- **GREEN**: {color_counts['GREEN']} pillars")
        rows.append(f"- **YELLOW**: {color_counts['YELLOW']} pillars")
        rows.append(f"- **RED**: {color_counts['RED']} pillars")
        rows.append(f"- **GRAY**: {color_counts['GRAY']} pillars")
        rows.append("")
        
        # Add individual pillar assessments
        rows.append("## Pillar Details")
        for pillar in pillars:
            pillar_name = pillar.get("pillar", "Unknown")
            color = pillar.get("color", "GRAY")
            score = pillar.get("score", "N/A")
            reason_codes = pillar.get("reason_codes", [])
            evidence_todo = pillar.get("evidence_todo", [])
            
            rows.append(f"### {pillar_name}")
            rows.append(f"**Status**: {color} ({score})")
            
            if reason_codes:
                rows.append(f"**Issues**: {', '.join(reason_codes)}")
            
            if evidence_todo:
                rows.append("**Evidence Needed**:")
                for task in evidence_todo:
                    rows.append(f"- {task}")
            
            rows.append("")
        
        # Add rules applied
        rules = data.get("rules_applied", {})
        if rules:
            rows.append("## Assessment Rules")
            rows.append(f"- **Evidence Gate**: {rules.get('evidence_gate', 'N/A')}")
            rows.append("")
        
        markdown = "\n".join(rows)
        markdown = fix_bullet_lists(markdown)
        return markdown

    def save_markdown(self, output_file_path: str):
        """Save markdown representation to file."""
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    sample_plan = """
    Project: Sustainable Data Center Migration
    
    We plan to migrate our legacy data center infrastructure to a cloud-based solution
    with renewable energy sources. The project involves moving 50+ servers, updating
    security protocols, and ensuring compliance with new data protection regulations.
    
    Budget: $2M allocated, with 5% contingency
    Timeline: 12 months
    Team: 15 engineers, 3 compliance specialists
    
    Risks: Legacy system integration, data sovereignty requirements, staff training needs
    """
    
    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    print(f"Assessing plan with {model_name}...")
    result = PillarsAssessment.execute(llm, sample_plan)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
