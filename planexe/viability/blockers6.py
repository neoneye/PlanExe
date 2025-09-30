"""
Emit Blockers (ViabilityAssessor Step 2).

PROMPT> python -u -m planexe.viability.blockers6 | tee output6.txt
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from math import ceil
from typing import Any, Dict, List, Optional, Sequence

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, ValidationError, conlist

from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists

# --- Configuration and Constants ---
logger = logging.getLogger(__name__)

PILLAR_ENUM: Sequence[str] = (
    "HumanStability",
    "EconomicResilience",
    "EcologicalIntegrity",
    "Rights_Legality",
)
STATUS_ENUM: Sequence[str] = ("GREEN", "YELLOW", "RED", "GRAY")
NON_GREEN_STATUSES = {status for status in STATUS_ENUM if status != "GREEN"}


# --- Pydantic Schemas for Input and Output ---

class PillarItem(BaseModel):
    """Represents a single pillar from the Step 1 assessment."""
    pillar: str
    status: str
    score: Optional[int] = None
    reason_codes: List[str] = Field(default_factory=list)
    evidence_todo: List[str] = Field(default_factory=list)

class PillarsPayload(BaseModel):
    """Represents the full input from Step 1."""
    pillars: List[PillarItem]

class BlockerItem(BaseModel):
    """Represents a single, actionable blocker."""
    id: str
    pillar: str
    title: str
    reason_codes: List[str] = Field(default_factory=list)
    acceptance_tests: conlist(str, min_length=1, max_length=3)
    artifacts_required: conlist(str, min_length=1, max_length=3)
    owner: Optional[str] = None

class BlockersPayload(BaseModel):
    """Represents the final, compliant output for Step 2."""
    blockers: conlist(BlockerItem, max_length=5)


# --- System Prompt Engineered for Quality and Compliance ---

BLOCKERS_SYSTEM_PROMPT = f"""
You are a meticulous viability risk analyst creating Step 2 blockers. Your entire response must be a single, valid JSON object with only a `blockers` key. Strictly adhere to this schema:
{{
  "blockers": [
    {{
      "id": "B1",
      "pillar": "HumanStability",
      "title": "Concise, actionable title",
      "reason_codes": ["STAKEHOLDER_CONFLICT"],
      "acceptance_tests": ["Specific, verifiable test (e.g., '>=80% support in survey')"],
      "artifacts_required": ["Concrete artifact name (e.g., 'Stakeholder_Survey_v1.pdf')"],
      "owner": "Responsible Role or Team"
    }}
  ]
}}
Rules:
1.  **Source:** Derive blockers ONLY from input pillars with status RED, YELLOW, or GRAY.
2.  **Quantity:** Create a maximum of 5 blockers total. Focus on the highest-leverage fixes.
3.  **Traceability:** `reason_codes` must be a non-empty subset of the source pillar's `reason_codes`. This is mandatory.
4.  **Actionability:**
    - `acceptance_tests`: Write 1-3 crisp, measurable, pass/fail conditions.
    - `artifacts_required`: Name 1-3 specific deliverables that prove the tests are met.
5.  **Schema:**
    - Use sequential IDs (B1, B2...).
    - `pillar` must be one of {{{', '.join(PILLAR_ENUM)}}}.
6.  **Edge Case:** If no non-green pillars are provided, return an empty `blockers` array.
7.  **Output JSON only.** No extra text or markdown.
"""


# --- Main Application Logic ---

@dataclass
class BlockerAssessment:
    system_prompt: str
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm: LLM, pillars_payload: Any) -> "BlockerAssessment":
        """
        Orchestrates the generation of blockers from a pillars assessment.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")

        validated_pillars = _load_pillars_payload(pillars_payload)
        non_green_pillars = [p for p in validated_pillars.pillars if p.status in NON_GREEN_STATUSES]

        if not non_green_pillars:
            empty_output = BlockersPayload(blockers=[]).model_dump()
            metadata = {**dict(llm.metadata), "llm_classname": llm.class_name(), "duration": 0, "response_byte_count": 0}
            return cls(
                system_prompt=BLOCKERS_SYSTEM_PROMPT.strip(),
                user_prompt=json.dumps({"pillars": []}, indent=2),
                response=empty_output,
                markdown=cls.convert_to_markdown(BlockersPayload.model_validate(empty_output)),
                metadata=metadata,
            )

        user_prompt = json.dumps(_build_user_payload(non_green_pillars), indent=2)
        system_prompt = BLOCKERS_SYSTEM_PROMPT.strip()
        chat_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        sllm = llm.as_structured_llm(BlockersPayload)
        start_time = time.perf_counter()
        chat_response = sllm.chat(chat_messages)
        duration = int(ceil(time.perf_counter() - start_time))

        sanitized_output = _enforce_guardrails(chat_response.raw, non_green_pillars)

        metadata = {
            **dict(llm.metadata),
            "llm_classname": llm.class_name(),
            "duration": duration,
            "response_byte_count": len(json.dumps(sanitized_output.model_dump()).encode("utf-8")),
        }
        markdown = cls.convert_to_markdown(sanitized_output)

        return cls(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=sanitized_output.model_dump(),
            markdown=markdown,
            metadata=metadata,
        )

    @staticmethod
    def convert_to_markdown(blockers_output: BlockersPayload) -> str:
        """Converts the structured blocker output to human-readable markdown."""
        if not blockers_output.blockers:
            return "## Blockers\n\n- None identified (All pillars are GREEN)."

        rows: List[str] = ["## Blockers"]
        for blocker in blockers_output.blockers:
            rows.append(f"### {blocker.id}: {blocker.title}")
            rows.append(f"**Pillar:** {blocker.pillar}")
            if blocker.reason_codes:
                rows.append(f"**Reason Codes:** {', '.join(blocker.reason_codes)}")
            if blocker.acceptance_tests:
                rows.append("**Acceptance Tests:**")
                for test in blocker.acceptance_tests:
                    rows.append(f"- {test}")
            if blocker.artifacts_required:
                rows.append("**Artifacts Required:**")
                for artifact in blocker.artifacts_required:
                    rows.append(f"- {artifact}")
            if blocker.owner:
                rows.append(f"**Owner:** {blocker.owner}")
            rows.append("")
        markdown = "\n".join(rows).strip()
        return fix_bullet_lists(markdown)

    def to_dict(self, **kwargs: bool) -> Dict[str, Any]:
        """Serializes the assessment result to a dictionary."""
        d = {"response": self.response, "markdown": self.markdown}
        if kwargs.get("include_metadata", True): d["metadata"] = self.metadata
        if kwargs.get("include_system_prompt", True): d["system_prompt"] = self.system_prompt
        if kwargs.get("include_user_prompt", True): d["user_prompt"] = self.user_prompt
        return d


# --- Helper and Guardrail Functions ---

def _load_pillars_payload(pillars_payload: Any) -> PillarsPayload:
    if isinstance(pillars_payload, str):
        try:
            raw = json.loads(pillars_payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid pillars JSON supplied.") from exc
    elif isinstance(pillars_payload, dict):
        raw = pillars_payload
    else:
        raise TypeError("pillars_payload must be a JSON string or a dictionary.")

    try:
        return PillarsPayload.model_validate(raw)
    except ValidationError as exc:
        raise ValueError("Pillars payload failed Pydantic validation.") from exc

def _build_user_payload(pillars: Sequence[PillarItem]) -> Dict[str, Any]:
    return {"pillars": [p.model_dump() for p in pillars]}

def _enforce_guardrails(output: BlockersPayload, source_pillars: Sequence[PillarItem]) -> BlockersPayload:
    allowed_pillars = {p.pillar: p for p in source_pillars}
    sanitized_blockers: List[Dict[str, Any]] = []

    for candidate in output.blockers:
        if candidate.pillar not in allowed_pillars:
            continue

        pillar_reason_codes = set(allowed_pillars[candidate.pillar].reason_codes)
        candidate_reason_codes = [code for code in candidate.reason_codes if code in pillar_reason_codes]
        if not candidate_reason_codes:
            continue

        blocker_data = candidate.model_dump(exclude_unset=True)
        blocker_data["reason_codes"] = candidate_reason_codes

        valid_tests = [t.strip() for t in candidate.acceptance_tests if t.strip()][:3]
        if not valid_tests: continue
        blocker_data["acceptance_tests"] = valid_tests

        valid_artifacts = [a.strip() for a in candidate.artifacts_required if a.strip()][:3]
        if not valid_artifacts: continue
        blocker_data["artifacts_required"] = valid_artifacts
        
        sanitized_blockers.append(blocker_data)
        if len(sanitized_blockers) >= 5:
            break

    pillar_order = {name: i for i, name in enumerate(PILLAR_ENUM)}
    sanitized_blockers.sort(key=lambda b: pillar_order.get(b["pillar"], 99))
    for i, blocker in enumerate(sanitized_blockers, 1):
        blocker["id"] = f"B{i}"

    return BlockersPayload.model_validate({"blockers": sanitized_blockers})

if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    example_input = {
        "pillars": [
            {
                "pillar": "HumanStability", "status": "RED", "score": 20,
                "reason_codes": ["GOVERNANCE_WEAK", "STAKEHOLDER_CONFLICT"],
                "evidence_todo": ["Social unrest mitigation plan v1"],
            },
            {
                "pillar": "EconomicResilience", "status": "YELLOW", "score": 55,
                "reason_codes": ["CONTINGENCY_LOW", "UNIT_ECON_UNKNOWN"],
                "evidence_todo": ["Contingency budget v2"],
            },
            {
                "pillar": "Rights_Legality", "status": "YELLOW", "score": 55,
                "reason_codes": ["DPIA_GAPS", "ETHICS_VAGUE"],
                "evidence_todo": ["Data protection impact assessment v1"],
            },
        ]
    }

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)
    
    assessment = BlockerAssessment.execute(llm, example_input)

    print("--- Output ---")
    print(json.dumps(assessment.response, indent=2))