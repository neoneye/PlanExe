"""
Emit Blockers (ViabilityAssessor Step 2).

Transforms weak pillars from Step 1 into ≤5 concrete blockers with
acceptance tests, artifacts, owners, and ROM estimates. Mirrors the
structured LLM orchestration style used in `planexe.plan.executive_summary`.

PROMPT> python -u -m planexe.viability.legacy_blockers4 | tee output4.txt
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

logger = logging.getLogger(__name__)

PILLAR_ENUM: Sequence[str] = (
    "HumanStability",
    "EconomicResilience",
    "EcologicalIntegrity",
    "Rights_Legality",
)
STATUS_ENUM: Sequence[str] = ("GREEN", "YELLOW", "RED", "GRAY")
NON_GREEN_STATUSES = {status for status in STATUS_ENUM if status != "GREEN"}
COST_BAND_ENUM: Sequence[str] = ("LOW", "MEDIUM", "HIGH")
DEFAULT_ROM = {"cost_band": "LOW", "eta_days": 14}


class PillarItem(BaseModel):
    pillar: str
    status: str
    score: Optional[int] = None
    reason_codes: List[str] = Field(default_factory=list)
    evidence_todo: List[str] = Field(default_factory=list)


class PillarsPayload(BaseModel):
    pillars: List[PillarItem]


class ROM(BaseModel):
    cost_band: str
    eta_days: int


class BlockerItem(BaseModel):
    id: str
    pillar: str
    title: str
    rationale: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    acceptance_tests: conlist(str, min_length=1, max_length=3)
    artifacts_required: conlist(str, min_length=1, max_length=3)
    owner: Optional[str] = None
    due_by: Optional[str] = None
    rom: Optional[ROM] = None


class BlockersPayload(BaseModel):
    blockers: conlist(BlockerItem, max_length=5)


BLOCKERS_SYSTEM_PROMPT = f"""
You are a viability risk analyst creating Step 2 blockers. Return JSON only with
`blockers`. Respect this schema:
{{
  "blockers": [
    {{
      "id": "B1",
      "pillar": "HumanStability",
      "title": "Title",
      "rationale": "Short justification of why this is blocking execution.",
      "reason_codes": ["STAFF_AVERSION"],
      "acceptance_tests": ["Specific, verifiable test"],
      "artifacts_required": ["Artifact name"],
      "owner": "Role or team",
      "due_by": "2025-03-31",
      "rom": {{"cost_band": "LOW", "eta_days": 14}}
    }}
  ]
}}
Rules:
- Derive blockers only from input pillars with status RED, YELLOW, or GRAY.
- Cap the total number of blockers at five; focus on the highest leverage fixes.
- Use sequential IDs (B1..B5) and canonical pillar names from {{{', '.join(PILLAR_ENUM)}}}.
- `reason_codes` must be a subset of the pillar's reason codes.
- Provide 1-3 crisp acceptance tests and required artifacts per blocker.
- Always include a ROM with `cost_band` in {{{', '.join(COST_BAND_ENUM)}}} and realistic `eta_days`.
- If there are no non-green pillars, return an empty blockers array.
Output JSON only.
"""


@dataclass
class BlockerAssessment:
    system_prompt: str
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm: LLM, pillars_payload: Any) -> "BlockerAssessment":
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")

        validated_pillars = _load_pillars_payload(pillars_payload)
        non_green = [pillar for pillar in validated_pillars.pillars if pillar.status in NON_GREEN_STATUSES]

        if not non_green:
            empty_output = BlockersPayload(blockers=[]).model_dump()
            metadata = dict(llm.metadata)
            metadata.update({"llm_classname": llm.class_name(), "duration": 0, "response_byte_count": 0})
            return cls(
                system_prompt=BLOCKERS_SYSTEM_PROMPT.strip(),
                user_prompt=json.dumps({"pillars": []}, indent=2),
                response=empty_output,
                markdown=cls.convert_to_markdown(BlockersPayload.model_validate(empty_output)),
                metadata=metadata,
            )

        user_payload = _build_user_payload(non_green)
        user_prompt = json.dumps(user_payload, indent=2)

        system_prompt = BLOCKERS_SYSTEM_PROMPT.strip()
        chat_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        sllm = llm.as_structured_llm(BlockersPayload)
        start = time.perf_counter()
        chat_response = sllm.chat(chat_messages)
        end = time.perf_counter()

        duration = int(ceil(end - start))
        sanitized = _enforce_guardrails(chat_response.raw, non_green)

        metadata = dict(llm.metadata)
        metadata.update(
            {
                "llm_classname": llm.class_name(),
                "duration": duration,
                "response_byte_count": len(json.dumps(sanitized.model_dump()).encode("utf-8")),
            }
        )

        markdown = cls.convert_to_markdown(sanitized)

        return cls(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=sanitized.model_dump(),
            markdown=markdown,
            metadata=metadata,
        )

    @staticmethod
    def convert_to_markdown(blockers_output: BlockersPayload) -> str:
        if not blockers_output.blockers:
            return "## Blockers\n\n- None identified"

        rows: List[str] = ["## Blockers"]
        for blocker in blockers_output.blockers:
            rows.append(f"### {blocker.id}: {blocker.title}")
            rows.append(f"**Pillar:** {blocker.pillar}")
            if blocker.reason_codes:
                rows.append(f"**Reason Codes:** {', '.join(blocker.reason_codes)}")
            if blocker.rationale:
                rows.append(f"**Rationale:** {blocker.rationale}")
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
            if blocker.due_by:
                rows.append(f"**Due By:** {blocker.due_by}")
            if blocker.rom:
                rows.append(f"**ROM:** {blocker.rom.cost_band} cost, {blocker.rom.eta_days} days")
            rows.append("")
        markdown = "\n".join(rows).strip()
        return fix_bullet_lists(markdown)

    def to_dict(
        self,
        *,
        include_metadata: bool = True,
        include_system_prompt: bool = True,
        include_user_prompt: bool = True,
    ) -> Dict[str, Any]:
        data = {
            "response": self.response,
            "markdown": self.markdown,
        }
        if include_metadata:
            data["metadata"] = self.metadata
        if include_system_prompt:
            data["system_prompt"] = self.system_prompt
        if include_user_prompt:
            data["user_prompt"] = self.user_prompt
        return data

    def save_json(self, file_path: str, *, include_context: bool = False) -> None:
        payload = self.to_dict() if include_context else self.response
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def save_markdown(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(self.markdown)


def _load_pillars_payload(pillars_payload: Any) -> PillarsPayload:
    if isinstance(pillars_payload, str):
        try:
            raw = json.loads(pillars_payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid pillars JSON supplied.") from exc
    elif isinstance(pillars_payload, dict):
        raw = pillars_payload
    else:
        raise ValueError("pillars_payload must be str or dict.")

    try:
        return PillarsPayload.model_validate(raw)
    except ValidationError as exc:
        raise ValueError("pillars_payload failed validation.") from exc


def _build_user_payload(pillars: Sequence[PillarItem]) -> Dict[str, Any]:
    return {
        "pillars": [
            {
                "pillar": pillar.pillar,
                "status": pillar.status,
                "score": pillar.score,
                "reason_codes": pillar.reason_codes,
                "evidence_todo": pillar.evidence_todo,
            }
            for pillar in pillars
        ]
    }


def _enforce_guardrails(blockers_output: BlockersPayload, pillars: Sequence[PillarItem]) -> BlockersPayload:
    allowed_pillars = {pillar.pillar: pillar for pillar in pillars}
    canonical_order = {pillar: index for index, pillar in enumerate(PILLAR_ENUM)}
    sanitized_blockers: List[Dict[str, Any]] = []

    for candidate in blockers_output.blockers:
        if candidate.pillar not in allowed_pillars:
            continue

        pillar_reason_codes = set(allowed_pillars[candidate.pillar].reason_codes)
        blocker_data = candidate.model_dump()
        blocker_data["id"] = f"B{len(sanitized_blockers) + 1}"

        blocker_data["reason_codes"] = [
            code for code in blocker_data.get("reason_codes", []) if code in pillar_reason_codes
        ]

        acceptance_tests = [
            test.strip()
            for test in (blocker_data.get("acceptance_tests") or [])
            if isinstance(test, str) and test.strip()
        ][:3]
        if not acceptance_tests:
            continue
        blocker_data["acceptance_tests"] = acceptance_tests

        artifacts_required = [
            artifact.strip()
            for artifact in (blocker_data.get("artifacts_required") or [])
            if isinstance(artifact, str) and artifact.strip()
        ][:3]
        if not artifacts_required:
            continue
        blocker_data["artifacts_required"] = artifacts_required

        rationale = blocker_data.get("rationale")
        if isinstance(rationale, str):
            blocker_data["rationale"] = rationale.strip() or None
        else:
            blocker_data["rationale"] = None

        owner_value = blocker_data.get("owner")
        blocker_data["owner"] = owner_value.strip() if isinstance(owner_value, str) and owner_value.strip() else None

        due_by_value = blocker_data.get("due_by")
        blocker_data["due_by"] = due_by_value.strip() if isinstance(due_by_value, str) and due_by_value.strip() else None

        rom_payload = blocker_data.get("rom") or {}
        cost_band = rom_payload.get("cost_band")
        if cost_band not in COST_BAND_ENUM:
            cost_band = DEFAULT_ROM["cost_band"]
        eta_days = rom_payload.get("eta_days")
        if not isinstance(eta_days, int) or eta_days < 0:
            eta_days = DEFAULT_ROM["eta_days"]
        blocker_data["rom"] = {"cost_band": cost_band, "eta_days": eta_days}

        sanitized_blockers.append(blocker_data)
        if len(sanitized_blockers) == 5:
            break

    sanitized_blockers = sorted(
        sanitized_blockers,
        key=lambda item: (
            canonical_order.get(item["pillar"], len(PILLAR_ENUM)),
            item["id"],
        ),
    )

    for index, blocker in enumerate(sanitized_blockers, start=1):
        blocker["id"] = f"B{index}"

    sanitized_payload = {"blockers": sanitized_blockers}
    return BlockersPayload.model_validate(sanitized_payload)


if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    example_input = {
        "pillars": [
            {
                "pillar": "HumanStability",
                "status": "RED",
                "score": 20,
                "reason_codes": ["STAFF_AVERSION", "TALENT_UNKNOWN"],
                "evidence_todo": ["Stakeholder survey baseline"],
            },
            {
                "pillar": "EconomicResilience",
                "status": "YELLOW",
                "score": 55,
                "reason_codes": ["CONTINGENCY_LOW", "ALT_COST_UNKNOWN"],
                "evidence_todo": ["Update unit economics model"],
            },
            {
                "pillar": "EcologicalIntegrity",
                "status": "GREEN",
                "score": 85,
                "reason_codes": ["EIA_COMPLETE"],
                "evidence_todo": [],
            },
        ]
    }

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    assessment = BlockerAssessment.execute(llm, example_input)
    print(json.dumps(assessment.response, indent=2))
    print("\nMarkdown:\n")
    print(assessment.markdown)
