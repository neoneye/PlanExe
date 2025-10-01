"""
Implements Step 2 of the ViabilityAssessor protocol: Blocker Generation.

Revisions addressing spec alignment:
- Each blocker includes 'pillar' field (per interface and note to add inside BlockerItem).
- ROM: Retained as optional per interface; defaults in guardrails.
- Derivation: Non-GREEN only; reason_codes subsets; ties to evidence_todo.
- Actionability: Verifiable tests/artifacts; realistic fields.
- Guardrails: Enums, limits, sequential IDs, defaults.
- Output: JSON + Markdown.
- Input: JSON str/dict; full non-GREEN coverage.

PROMPT> python -u -m planexe.viability.legacy_blockers5 | tee output5.txt
"""
import os
import json
import time
import logging
from math import ceil
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, conlist
from llama_index.core.llms import ChatMessage, MessageRole

# Assuming planexe.markdown_util.fix_bullet_lists is available; fallback if not
try:
    from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists
except ImportError:
    def fix_bullet_lists(md: str) -> str:
        return md  # No-op fallback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Enums from README.md ---

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

REASON_CODE_ENUM = [
    "CONTINGENCY_LOW", "SINGLE_CUSTOMER", "ALT_COST_UNKNOWN",
    "DPIA_GAPS", "LICENSE_GAPS", "ABS_UNDEFINED", "PERMIT_COMPLEXITY",
    "LEGACY_IT", "INTEGRATION_RISK",
    "TALENT_UNKNOWN", "STAFF_AVERSION",
    "CLOUD_CARBON_UNKNOWN", "CLIMATE_UNQUANTIFIED", "WATER_STRESS",
    "BIOSECURITY_GAPS",
    "ETHICS_VAGUE", "GOVERNANCE_WEAK", "STAKEHOLDER_CONFLICT", "CHANGE_MGMT_GAPS",
    "EIA_MISSING", "BIODIVERSITY_RISK_UNSET", "WASTE_MANAGEMENT_GAPS",
    "INFOSEC_GAPS"
]  # Extended with observed codes for robustness

# --- Pydantic Models ---

class PillarItem(BaseModel):
    pillar: str = Field(description="The pillar name (HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality)")
    status: str = Field(description="The status (GREEN, YELLOW, RED, GRAY)")
    score: Optional[int] = Field(description="Score from 0-100")
    reason_codes: List[str] = Field(description="List of reason codes explaining the status")
    evidence_todo: List[str] = Field(description="List of evidence items that need to be collected")

class PillarsInput(BaseModel):
    pillars: List[PillarItem]

class ROM(BaseModel):
    cost_band: str = Field(description="Cost band (LOW, MEDIUM, HIGH)")
    eta_days: int = Field(description="Estimated days to complete")

class Blocker(BaseModel):
    id: str = Field(description="Sequential ID like B1, B2, etc.")
    pillar: str = Field(description="The pillar name this blocker addresses")
    title: str = Field(description="Concise title summarizing the blocker")
    reason_codes: List[str] = Field(description="1-2 reason codes from the pillar's reason_codes")
    acceptance_tests: List[str] = Field(description="1-3 verifiable acceptance criteria")
    artifacts_required: List[str] = Field(description="1-2 specific files or documents needed")
    owner: str = Field(description="Role or team responsible for this blocker")
    rom: Optional[ROM] = Field(description="Optional rough order of magnitude estimate")

class BlockersOutput(BaseModel):
    blockers: List[Blocker] = Field(description="List of blockers derived from non-GREEN pillars")

# --- LLM System Prompt ---

BLOCKER_GENERATION_SYSTEM_PROMPT = f"""
You are a meticulous project risk analyst. Convert weak pillars (non-GREEN status) into up to 5 actionable blockers.

Rules:
1. Output ONLY {{"blockers": [...]}}; each blocker from non-GREEN pillars.
2. blockers: Derive logically; cap at 5. For each:
   - id: Sequential "B1", "B2", etc. (must match pattern ^B\\d+$)
   - pillar: Exact name from input (must be one of: HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality)
   - title: Concise summary of the issue (max 100 characters)
   - reason_codes: 1-2 subset from pillar's reason_codes (prefer: {', '.join(REASON_CODE_ENUM)})
   - acceptance_tests: 1-3 verifiable conditions (e.g., "Contingency ≥15% of budget"; tie to evidence_todo)
   - artifacts_required: 1-2 specific files (e.g., "Mitigation_Plan_v1.pdf"; mirror evidence_todo)
   - owner: Realistic role/team (e.g., "PMO", "Legal", "Finance"; max 50 characters)
   - rom: Optional; if included, cost_band must be one of: LOW, MEDIUM, HIGH; eta_days must be 7-120
3. If no non-GREEN pillars: Empty blockers array.
4. Valid JSON only; no extras.

Schema example:
{{
  "blockers": [
    {{
      "id": "B1",
      "pillar": "HumanStability",
      "title": "Stakeholder conflict unresolved",
      "reason_codes": ["STAKEHOLDER_CONFLICT"],
      "acceptance_tests": [">=80% stakeholder approval in survey"],
      "artifacts_required": ["Survey_Baseline_v1.pdf"],
      "owner": "PMO",
      "rom": {{"cost_band": "MEDIUM", "eta_days": 30}}
    }}
  ]
}}
"""

# --- Main Logic ---

@dataclass
class BlockerGenerationResult:
    system_prompt: str
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: Dict[str, Any]

    def to_dict(self, include_metadata: bool = True, include_system_prompt: bool = True, include_user_prompt: bool = True) -> Dict[str, Any]:
        d = {"response": self.response, "markdown": self.markdown}
        if include_metadata:
            d["metadata"] = self.metadata
        if include_system_prompt:
            d["system_prompt"] = self.system_prompt
        if include_user_prompt:
            d["user_prompt"] = self.user_prompt
        return d

    def save_json(self, file_path: str, include_full_context: bool = False) -> None:
        data = self.to_dict() if include_full_context else self.response
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved to {file_path}")

    def save_markdown(self, file_path: str) -> None:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.markdown)
        logger.info(f"Saved Markdown to {file_path}")

    @staticmethod
    def convert_to_markdown(output: BlockersOutput, source_pillars: List[str]) -> str:
        if not output.blockers:
            return f"## Source Pillars\n\n- {', '.join(source_pillars) if source_pillars else 'None'}\n\n## Blockers\n\n- None identified"

        md = [f"## Source Pillars", f"- {', '.join(source_pillars)}", "", "## Blockers"]
        for blocker in output.blockers:
            md.extend([
                f"### {blocker.id}: {blocker.title}",
                f"**Pillar:** {blocker.pillar}",
                f"**Reason Codes:** {', '.join(blocker.reason_codes)}" if blocker.reason_codes else "",
                "**Acceptance Tests:**",
            ])
            for test in blocker.acceptance_tests:
                md.append(f"  - {test}")
            md.extend([
                "**Artifacts Required:**",
            ])
            for artifact in blocker.artifacts_required:
                md.append(f"  - {artifact}")
            md.extend([
                f"**Owner:** {blocker.owner}",
            ])
            if blocker.rom:
                md.append(f"**ROM:** {blocker.rom.cost_band} cost, {blocker.rom.eta_days} days")
            md.append("")
        result = "\n".join(filter(None, md))  # Remove empty lines
        return fix_bullet_lists(result)

def enforce_guardrails(raw_output: BlockersOutput, pillars_input: PillarsInput) -> tuple[BlockersOutput, List[str]]:
    """Post-LLM sanitization: Basic validation and cleanup."""
    non_green_pillars = [p for p in pillars_input.pillars if p.status != "GREEN"]
    source_pillars_set = {p.pillar for p in non_green_pillars}
    source_pillars_list = sorted(list(source_pillars_set))
    
    # Sanitize blockers
    sanitized_blockers = []
    pillar_codes = {p.pillar: set(p.reason_codes) for p in non_green_pillars}
    
    for blocker in raw_output.blockers[:5]:  # Cap at 5
        if blocker.pillar not in source_pillars_set:
            continue
        data = blocker.model_dump()
        
        # ID sequential
        data["id"] = f"B{len(sanitized_blockers) + 1}"
        
        # Reason codes subset (non-empty if possible)
        data["reason_codes"] = [rc for rc in data["reason_codes"] if rc in pillar_codes[blocker.pillar]]
        if not data["reason_codes"] and pillar_codes[blocker.pillar]:
            data["reason_codes"] = [next(iter(pillar_codes[blocker.pillar]))]
        
        # Trim lists
        data["acceptance_tests"] = data["acceptance_tests"][:3]
        data["artifacts_required"] = data["artifacts_required"][:2]
        
        # ROM: Optional, basic validation
        if "rom" in data and data["rom"]:
            rom_data = data["rom"]
            if rom_data["cost_band"] not in ["LOW", "MEDIUM", "HIGH"]:
                rom_data["cost_band"] = "LOW"
            if not isinstance(rom_data["eta_days"], int) or rom_data["eta_days"] < 0:
                rom_data["eta_days"] = 14
            data["rom"] = ROM(**rom_data).model_dump()
        else:
            data["rom"] = None
        
        sanitized_blockers.append(Blocker(**data))
    
    return BlockersOutput(blockers=sanitized_blockers), source_pillars_list

class BlockerGenerator:
    @classmethod
    def execute(cls, llm: LLM, pillars_json: Any) -> BlockerGenerationResult:
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")

        # Parse input
        if isinstance(pillars_json, str):
            pillars_data = json.loads(pillars_json)
        else:
            pillars_data = pillars_json
        validated_input = PillarsInput.model_validate(pillars_data)
        
        non_green_pillars = [p for p in validated_input.pillars if p.status != StatusEnum.GREEN]
        if not non_green_pillars:
            empty = BlockersOutput(blockers=[]).model_dump()
            source_pillars = []
            return BlockerGenerationResult(
                system_prompt=BLOCKER_GENERATION_SYSTEM_PROMPT.strip(),
                user_prompt='{"pillars": []}',
                response=empty,
                markdown=BlockerGenerationResult.convert_to_markdown(BlockersOutput.model_validate(empty), source_pillars),
                metadata={"status": "No non-GREEN pillars."}
            )
        
        llm_input = {"pillars": [p.model_dump(mode='json') for p in non_green_pillars]}
        user_prompt = json.dumps(llm_input, indent=2)
        
        # LLM call
        system_prompt = BLOCKER_GENERATION_SYSTEM_PROMPT.strip()
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]
        
        sllm = llm.as_structured_llm(BlockersOutput)
        start_time = time.perf_counter()
        chat_response = sllm.chat(messages)
        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        
        # Guardrails
        raw_output = chat_response.raw
        sanitized_output, derived_source_pillars = enforce_guardrails(raw_output, validated_input)
        
        response_byte_count = len(json.dumps(sanitized_output.model_dump()).encode('utf-8'))
        metadata = {
            **dict(llm.metadata),
            "llm_classname": llm.__class__.__name__,
            "duration": duration,
            "response_byte_count": response_byte_count
        }
        
        markdown = BlockerGenerationResult.convert_to_markdown(sanitized_output, derived_source_pillars)
        
        return BlockerGenerationResult(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=sanitized_output.model_dump(),
            markdown=markdown,
            metadata=metadata,
        )

if __name__ == "__main__":
    from planexe.llm_factory import get_llm  # Assuming available

    # Full example input from blockers1.py
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

    result = BlockerGenerator.execute(llm, input_json_str)

    output_bytes_count = len(json.dumps(result.response).encode('utf-8'))
    print(f"\n--- Output (Generated Blockers) ---\nByte Count: {output_bytes_count}\n")
    print(json.dumps(result.response, indent=2))

    print(f"\n--- Markdown ---\n{result.markdown}")

    # Optional saves
    # result.save_json("blockers_output.json")
    # result.save_markdown("blockers_output.md")
