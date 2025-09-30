"""
One-pager that generates blockers from pillars assessment.

Based on ViabilityAssessor Step 2: Emit Blockers.

- The blockers summary derives from weak pillars (YELLOW, RED, GRAY).
- Purpose: Convert weaknesses into 3-5 actionable blockers with acceptance tests and artifacts.
- Helps prioritize fixes: Each blocker has verifiable tests, required artifacts, owner, and ROM estimate.
- Provides execution clarity: Bundles risks into crisp, testable items for Fix Packs.

PROMPT> python -u -m planexe.viability.blockers2 | tee output2.txt
"""
import os
import json
import time
import logging
from math import ceil
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists

logger = logging.getLogger(__name__)

class Blocker(BaseModel):
    id: str = Field(description="Unique ID like 'B1', 'B2', etc.")
    pillar: str = Field(description="The pillar name from PILLAR_ENUM.")
    title: str = Field(description="A concise, descriptive title for the blocker.")
    reason_codes: Optional[List[str]] = Field(default_factory=list, description="Subset of reason codes from the pillar's issues.")
    acceptance_tests: Optional[List[str]] = Field(default_factory=list, description="1-3 verifiable acceptance tests (e.g., '>=10% contingency approved').")
    artifacts_required: Optional[List[str]] = Field(default_factory=list, description="Required artifacts/deliverables (e.g., 'Budget_v2.pdf').")
    owner: Optional[str] = Field(default=None, description="Responsible role or team (e.g., 'PMO').")
    rom: Optional[Dict[str, Any]] = Field(default=None, description="ROM estimate: {'cost_band': 'LOW|MEDIUM|HIGH', 'eta_days': int}.")

class BlockersOutput(BaseModel):
    source_pillars: List[str] = Field(description="Array of pillar names that are YELLOW, RED, or GRAY.")
    blockers: List[Blocker] = Field(description="3-5 blockers derived from source_pillars.")

PILLAR_ENUM = ["HumanStability", "EconomicResilience", "EcologicalIntegrity", "Rights_Legality"]
STATUS_ENUM = ["GREEN", "YELLOW", "RED", "GRAY"]
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
COST_BAND_ENUM = ["LOW", "MEDIUM", "HIGH"]

BLOCKERS_SYSTEM_PROMPT = f"""
You are an expert risk assessor specializing in deriving actionable blockers from pillar assessments in viability plans. Your task is to generate a complete blockers output as a valid JSON object that strictly adheres to the schema below. Do not include any extra text, markdown formatting, or additional keys.

The JSON object must include exactly the following keys:

{{
  "source_pillars": ["HumanStability", "EconomicResilience"],  // Array of pillar names from PILLAR_ENUM that have status YELLOW, RED, or GRAY
  "blockers": [  // Array of 3-5 Blocker objects, only from source_pillars
    {{
      "id": "B1",
      "pillar": "EconomicResilience",
      "title": "Contingency too low",
      "reason_codes": ["CONTINGENCY_LOW"],
      "acceptance_tests": [">=10% contingency approved", "Monte Carlo risk workbook attached"],
      "artifacts_required": ["Budget_v2.pdf", "Risk_MC.xlsx"],
      "owner": "PMO",
      "rom": {{"cost_band": "LOW", "eta_days": 14}}
    }}
  ]
}}

Instructions:
- source_pillars: List only pillars from the input assessment where status is YELLOW, RED, or GRAY. Use exact names from PILLAR_ENUM: {', '.join(PILLAR_ENUM)}.
- blockers: Derive 3-5 blockers total (cap at 5) only from source_pillars. Distribute across pillars logically. For each:
  - id: Sequential like "B1", "B2", etc.
  - pillar: Match one from source_pillars.
  - title: Concise and descriptive (e.g., "Contingency too low").
  - reason_codes: Subset of 1-2 codes from the pillar's 'Issues' in the input. Use from REASON_CODE_ENUM if possible: {', '.join(REASON_CODE_ENUM)}; otherwise, use input terms.
  - acceptance_tests: 1-3 short, verifiable tests (e.g., ">=80% support in survey").
  - artifacts_required: 1-3 specific deliverables/files (e.g., "Plan_v1.pdf").
  - owner: A role/team (e.g., "PMO", "Engineering Lead").
  - rom: Always include {{"cost_band": one of {', '.join(COST_BAND_ENUM)}, "eta_days": realistic number like 14}}.
- Derivation: Base blockers on the pillar's status, score, Issues, and Evidence Needed. Focus on turning weaknesses into testable fixes.
- Guardrails: No blockers from GREEN pillars. Keep total <=5. Use professional, concise language.

Output Requirements:
- Your entire response must be a valid JSON object conforming exactly to the schema above.
- Do not include any extra text or formatting outside the JSON structure.

Remember: Your output must be valid JSON and nothing else.
"""

@dataclass
class Blockers:
    system_prompt: Optional[str]
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'Blockers':
        """
        Invoke LLM with pillars assessment text to derive blockers.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        system_prompt = BLOCKERS_SYSTEM_PROMPT.strip()
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

        sllm = llm.as_structured_llm(BlockersOutput)
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

        markdown = cls.convert_to_markdown(chat_response.raw)

        result = Blockers(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            markdown=markdown,
            metadata=metadata,
        )
        logger.debug("Blockers instance created successfully.")
        return result    

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> Dict[str, Any]:
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
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

    @staticmethod
    def convert_to_markdown(blockers_output: BlockersOutput) -> str:
        """
        Convert the raw blockers output to markdown.
        """
        rows = []
        rows.append("## Source Pillars")
        rows.append(f"- {', '.join(blockers_output.source_pillars)}")
        rows.append("")
        rows.append("## Blockers")
        for blocker in blockers_output.blockers:
            rows.append(f"### {blocker.id}: {blocker.title}")
            rows.append(f"**Pillar:** {blocker.pillar}")
            if blocker.reason_codes:
                rows.append(f"**Reason Codes:** {', '.join(blocker.reason_codes)}")
            if blocker.acceptance_tests:
                rows.append("**Acceptance Tests:**")
                for test in blocker.acceptance_tests:
                    rows.append(f"  - {test}")
            if blocker.artifacts_required:
                rows.append("**Artifacts Required:**")
                for artifact in blocker.artifacts_required:
                    rows.append(f"  - {artifact}")
            if blocker.owner:
                rows.append(f"**Owner:** {blocker.owner}")
            if blocker.rom:
                rows.append(f"**ROM:** {blocker.rom['cost_band']} cost, {blocker.rom['eta_days']} days")
            rows.append("")
        markdown = "\n".join(rows)
        markdown = fix_bullet_lists(markdown)
        return markdown

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)
    
if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    # Extracted Pillars Assessment from report
    pillars_text = """
Pillars Assessment

Summary

	GREEN: 0 pillars
	YELLOW: 2 pillars
	RED: 2 pillars
	GRAY: 0 pillars


Pillar Details

Human Stability

Status: RED (20)

Issues: GOVERNANCE_WEAK, STAKEHOLDER_CONFLICT, CHANGE_MGMT_GAPS

Evidence Needed:

	Social unrest mitigation plan v1
	Resident mental health support plan v2


Economic Resilience

Status: YELLOW (55)

Issues: CONTINGENCY_LOW, UNIT_ECON_UNKNOWN

Evidence Needed:

	Contingency budget v2
	Unit economics model v3 + sensitivity table


Ecological Integrity

Status: RED (20)

Issues: EIA_MISSING, BIODIVERSITY_RISK_UNSET, WASTE_MANAGEMENT_GAPS

Evidence Needed:

	Ecosystem risk mitigation plan v1
	Waste management plan v2


Rights & Legality

Status: YELLOW (55)

Issues: DPIA_GAPS, INFOSEC_GAPS, ETHICS_VAGUE

Evidence Needed:

	Data protection impact assessment v1
	Ethics review board charter v1
    """

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    query = pillars_text
    input_bytes_count = len(query.encode('utf-8'))
    print(f"Query: {query}")
    result = Blockers.execute(llm, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")

    output_bytes_count = len(result.markdown.encode('utf-8'))
    print(f"\n\nInput bytes count: {input_bytes_count}")
    print(f"Output bytes count: {output_bytes_count}")
    bytes_saved = input_bytes_count - output_bytes_count
    print(f"Bytes saved: {bytes_saved}")
    print(f"Percentage saved: {bytes_saved / input_bytes_count * 100:.2f}%")