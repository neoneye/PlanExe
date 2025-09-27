"""
One-pager that summarizes the plan viability via CAS pillars extraction.

Based on ViabilityAssessor protocol from README.md.

- Step 1: Emit Pillars (scope and evidence gates).
- Outputs JSON with pillars array, using enums for pillars, colors, reason_codes.
- Validator auto-repair applied post-LLM.
- Similar structure to viability_desired_output1.json, but focused on pillars for now.

PROMPT> python -m planexe.viability.pillars6
"""
import os
import json
import time
import logging
from math import ceil
from typing import Optional, List, Dict
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, field_validator
from llama_index.core.llms import ChatMessage, MessageRole
from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists

logger = logging.getLogger(__name__)

# Constants & Enums from README.md
PILLAR_ENUM = ["HumanStability", "EconomicResilience", "EcologicalIntegrity", "Rights_Legality"]
COLOR_ENUM = ["GREEN", "YELLOW", "RED", "GRAY"]
REASON_CODE_ENUM = [
    # Budget/Finance
    "CONTINGENCY_LOW", "SINGLE_CUSTOMER", "ALT_COST_UNKNOWN",
    # Rights/Compliance
    "DPIA_GAPS", "LICENSE_GAPS", "ABS_UNDEFINED", "PERMIT_COMPLEXITY",
    # Tech/Integration
    "LEGACY_IT", "INTEGRATION_RISK",
    # People/Adoption
    "TALENT_UNKNOWN", "STAFF_AVERSION",
    # Climate/Ecology
    "CLOUD_CARBON_UNKNOWN", "CLIMATE_UNQUANTIFIED", "WATER_STRESS",
    # Biosecurity
    "BIOSECURITY_GAPS",
    # Governance/Ethics
    "ETHICS_VAGUE"
]

class PillarItem(BaseModel):
    pillar: str = Field(description="Must be one of: " + ", ".join(PILLAR_ENUM))
    color: str = Field(description="Must be one of: " + ", ".join(COLOR_ENUM))
    score: Optional[int] = Field(ge=0, le=100, description="Score 0-100, aligned to color band.")
    reason_codes: Optional[List[str]] = Field(default=[], description="Subset of: " + ", ".join(REASON_CODE_ENUM))
    evidence_todo: Optional[List[str]] = Field(default=[], description="List of evidence items needed for GREEN.")

    @field_validator('pillar')
    @classmethod
    def validate_pillar(cls, v):
        if v not in PILLAR_ENUM:
            raise ValueError(f"Pillar must be one of {PILLAR_ENUM}")
        return v

    @field_validator('color')
    @classmethod
    def validate_color(cls, v):
        if v not in COLOR_ENUM:
            raise ValueError(f"Color must be one of {COLOR_ENUM}")
        return v

    @field_validator('reason_codes')
    @classmethod
    def validate_reason_codes(cls, v):
        invalid = [code for code in v if code not in REASON_CODE_ENUM]
        if invalid:
            raise ValueError(f"Invalid reason_codes: {invalid}. Must be subset of {REASON_CODE_ENUM}")
        return v

class PillarsOutput(BaseModel):
    pillars: List[PillarItem] = Field(description="Exactly 4 pillars, one per enum value.")

    @field_validator('pillars')
    @classmethod
    def validate_pillars(cls, v):
        if len(v) != 4:
            raise ValueError("Must have exactly 4 pillars.")
        pillars_set = {item.pillar for item in v}
        if set(PILLAR_ENUM) != pillars_set:
            raise ValueError(f"Must cover exactly {PILLAR_ENUM}")
        return v

PILLARS_SYSTEM_PROMPT = """
You are an expert viability assessor. Analyze the provided plan text and score it across the four CAS pillars: HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality.

Output ONLY a valid JSON object matching this exact schema:
{
  "pillars": [
    {
      "pillar": "HumanStability",
      "color": "YELLOW",
      "score": 60,
      "reason_codes": ["STAFF_AVERSION"],
      "evidence_todo": ["Stakeholder survey baseline"]
    },
    // ... one for each pillar
  ]
}

Rules:
- Emit exactly 4 pillars, one for each: HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality.
- Color: GREEN (strong, evidence complete), YELLOW (gaps, mitigable), RED (major flaws), GRAY (insufficient info).
- Score: 0-100; GREEN 70-100, YELLOW 40-69, RED 0-39, GRAY null.
- reason_codes: 0-3 from this exact list only: CONTINGENCY_LOW, SINGLE_CUSTOMER, ALT_COST_UNKNOWN, DPIA_GAPS, LICENSE_GAPS, ABS_UNDEFINED, PERMIT_COMPLEXITY, LEGACY_IT, INTEGRATION_RISK, TALENT_UNKNOWN, STAFF_AVERSION, CLOUD_CARBON_UNKNOWN, CLIMATE_UNQUANTIFIED, WATER_STRESS, BIOSECURITY_GAPS, ETHICS_VAGUE. Subset relevant to pillar.
- evidence_todo: 1-3 specific items needed to upgrade to GREEN. Empty for GREEN.
- GREEN requires evidence_todo empty.
- Be concise; base on plan evidence. No extra text.
"""

@dataclass
class PillarsExtraction:
    system_prompt: Optional[str]
    user_prompt: str
    response: Dict
    markdown: str
    metadata: dict

    COLOR_TO_SCORE_BAND = {
        "GREEN": (70, 100),
        "YELLOW": (40, 69),
        "RED": (0, 39),
        "GRAY": None
    }
    BAND_MIDPOINTS = {"GREEN": 85, "YELLOW": 55, "RED": 20}

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str, metadata: Optional[Dict] = None) -> 'PillarsExtraction':
        """
        Invoke LLM to extract pillars from plan text.
        Apply validation & auto-repair.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        system_prompt = PILLARS_SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        sllm = llm.as_structured_llm(PillarsOutput)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        # Parse and validate
        try:
            parsed = PillarsOutput.model_validate_json(chat_response.message.content)
        except Exception as e:
            logger.warning(f"LLM output invalid; attempting auto-repair: {e}")
            parsed = cls._auto_repair_llm_output(chat_response.message.content)

        # Apply evidence gate and score sync
        pillars = cls._validate_and_repair_pillars(parsed.pillars)

        repaired_output = PillarsOutput(pillars=pillars)
        json_response = repaired_output.model_dump()

        meta = metadata or {}
        meta.update({
            "llm_classname": llm.class_name(),
            "duration": duration,
            "response_byte_count": response_byte_count,
        })

        markdown = cls.convert_to_markdown(repaired_output)

        result = PillarsExtraction(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            markdown=markdown,
            metadata=meta,
        )
        logger.debug("PillarsExtraction instance created successfully.")
        return result

    @staticmethod
    def _auto_repair_llm_output(raw_content: str) -> PillarsOutput:
        """Basic repair: parse if possible, else default to GRAY pillars."""
        try:
            data = json.loads(raw_content)
            pillars_data = data.get("pillars", [])
            pillars = []
            for p in pillars_data:
                pillar = p.get("pillar", "Rights_Legality")
                if pillar not in PILLAR_ENUM:
                    pillar = "Rights_Legality"
                color = p.get("color", "GRAY")
                if color not in COLOR_ENUM:
                    color = "GRAY"
                pillars.append({
                    "pillar": pillar,
                    "color": color,
                    "score": None,
                    "reason_codes": [],
                    "evidence_todo": []
                })
            # Fill missing pillars
            for enum_p in PILLAR_ENUM:
                if not any(pi["pillar"] == enum_p for pi in pillars):
                    pillars.append({
                        "pillar": enum_p,
                        "color": "GRAY",
                        "score": None,
                        "reason_codes": [],
                        "evidence_todo": []
                    })
            return PillarsOutput(pillars=pillars[:4])
        except:
            # Fallback: all GRAY
            pillars = [{"pillar": p, "color": "GRAY", "score": None, "reason_codes": [], "evidence_todo": []} for p in PILLAR_ENUM]
            return PillarsOutput(pillars=pillars)

    @classmethod
    def _validate_and_repair_pillars(cls, pillars: List[PillarItem]) -> List[PillarItem]:
        """Apply README validation: evidence gate, score sync."""
        repaired = []
        for p in pillars:
            item = p.model_copy()
            # Evidence gate
            if item.color == "GREEN" and item.evidence_todo:
                item.color = "YELLOW"
                logger.debug(f"Downgraded {item.pillar} to YELLOW due to non-empty evidence_todo.")
            # Score sync
            band = cls.COLOR_TO_SCORE_BAND.get(item.color)
            if band is None:  # GRAY
                item.score = None
            elif item.score is None or not (band[0] <= item.score <= band[1]):
                item.score = cls.BAND_MIDPOINTS.get(item.color, 50)
                logger.debug(f"Set score for {item.pillar} to midpoint {item.score}.")
            repaired.append(item)
        return repaired

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        d['markdown'] = self.markdown
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        # Mimic desired output structure
        output = {
            "metadata": self.metadata.get("plan_metadata", {}),
            "viability_summary": {},  # Placeholder; extend for full protocol
            "pillars": d.get("pillars", []),
            "blockers": [],  # Placeholder
            "fix_packs": [],  # Placeholder
            "overall": {}  # Placeholder
        }
        return output

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

    @staticmethod
    def convert_to_markdown(output: PillarsOutput) -> str:
        """
        Convert to markdown table/summary.
        """
        rows = ["## Viability Pillars Assessment\n"]
        rows.append("| Pillar | Color | Score | Reason Codes | Evidence ToDo |\n")
        rows.append("|--------|-------|-------|--------------|---------------|\n")
        for p in output.pillars:
            reasons = ", ".join(p.reason_codes) if p.reason_codes else "None"
            todos = ", ".join(p.evidence_todo) if p.evidence_todo else "Complete"
            rows.append(f"| {p.pillar} | {p.color} | {p.score or 'N/A'} | {reasons} | {todos} |\n")
        markdown = "".join(rows)
        return fix_bullet_lists(markdown)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)
    
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

    # Optional metadata like in desired output
    plan_meta = {
        "plan_title": "SIA MVP",
        "assessed_at": "2025-09-27T12:00:00Z",
        "config_version": "0.3.4",
        "pillars_schema": {"primary": "CAS"},
        "horizon_years": 2.5,  # 30 months
        "budget_usd": 15000000  # CHF 15M approx USD
    }

    query = plan_synopsis
    input_bytes_count = len(query.encode('utf-8'))
    print(f"Query: {query[:200]}...")  # Truncated for print
    result = PillarsExtraction.execute(llm, query, {"plan_metadata": plan_meta})

    print("\nResponse (Pillars):")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")

    output_bytes_count = len(result.markdown.encode('utf-8'))
    print(f"\n\nInput bytes count: {input_bytes_count}")
    print(f"Output bytes count: {output_bytes_count}")
    bytes_saved = input_bytes_count - output_bytes_count
    print(f"Bytes saved: {bytes_saved}")
    print(f"Percentage saved: {bytes_saved / input_bytes_count * 100:.2f}%")