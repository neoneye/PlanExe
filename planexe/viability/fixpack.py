"""
Implements Step 3 of the ViabilityAssessor protocol: Fix Pack generation.

This module consumes the JSON outputs from Step 1 (Pillars) and Step 2 (Blockers)
packaged in the combined pipeline prompt and emits a structured set of Fix Packs
that bundle blockers into execution-ready clusters. FP0 is always reserved for
the pre-commit gate containing the blockers that must be resolved before
proceeding.

PROMPT> python -u -m planexe.viability.fixpack | tee output.txt
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from math import ceil
from typing import Dict, Iterable, List, Optional, Sequence

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, ConfigDict, Field, ValidationError, conlist

from planexe.viability.model_pillar import PillarEnum
from planexe.viability.model_status import StatusEnum

logger = logging.getLogger(__name__)

# --- Enums mirroring viability/README.md ---

class CostBandEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FixPackPriorityEnum(str, Enum):
    IMMEDIATE = "Immediate"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


FP0_TITLE = "Pre-Commit Gate"
MUST_FIX_REASON_CODES = {"DPIA_GAPS", "CONTINGENCY_LOW", "ETHICS_VAGUE"}

# --- Pydantic models for input payloads ---


class PillarItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    pillar: PillarEnum
    status: StatusEnum
    reason_codes: List[str] = Field(default_factory=list)
    evidence_todo: List[str] = Field(default_factory=list)


class PillarsInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    pillars: List[PillarItem]


class ROM(BaseModel):
    model_config = ConfigDict(extra="allow")

    cost_band: str
    eta_days: int


class Blocker(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    pillar: str
    title: str
    reason_codes: List[str] = Field(default_factory=list)
    acceptance_tests: List[str] = Field(default_factory=list)
    artifacts_required: List[str] = Field(default_factory=list)
    owner: Optional[str] = None
    rom: Optional[ROM] = None


class BlockersOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_pillars: List[str] = Field(default_factory=list)
    blockers: List[Blocker]


class FixPackEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    blocker_ids: conlist(str, min_length=1)
    priority: FixPackPriorityEnum


class FixPacksOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    fix_packs: List[FixPackEntry]


class NonFP0FixPacks(BaseModel):
    model_config = ConfigDict(extra="allow")

    fix_packs: List[FixPackEntry]


# --- Prompt templates ---

FIX_PACK_SYSTEM_PROMPT = """
You are a rigorous program execution lead.
Given a list of blockers that are NOT part of FP0 (pre-commit gate), cluster them into themed Fix Packs.

Rules you must follow:
1. Respond with JSON only, matching the schema provided: {"fix_packs": FixPack[]}.
2. Each fix pack must have:
   - id: sequential FP1, FP2, ... with no gaps.
   - title: 2-8 words describing the shared theme.
   - blocker_ids: 1-4 blocker IDs drawn only from the provided list.
   - priority: one of {"Immediate", "High", "Medium", "Low"}.
3. Do NOT include FP0 in your response; it is already assembled elsewhere.
4. Cover every remaining blocker exactly once; do not duplicate or omit blocker IDs.
5. Prefer grouping blockers that share the same pillar or address closely related themes.
6. If there are no blockers provided, return {"fix_packs": []}.
""".strip()

# --- Result container ---


@dataclass
class FixPack:
    system_prompt: str
    user_prompt: str
    response: Dict[str, object]
    metadata: Dict[str, object]
    markdown: str

    def to_dict(
        self,
        include_metadata: bool = True,
        include_system_prompt: bool = True,
        include_user_prompt: bool = True,
    ) -> Dict[str, object]:
        data = dict(self.response)
        if include_metadata:
            data["metadata"] = self.metadata
        if include_system_prompt:
            data["system_prompt"] = self.system_prompt
        if include_user_prompt:
            data["user_prompt"] = self.user_prompt
        data["markdown"] = self.markdown
        return data

    def save_raw(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def save_markdown(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.markdown)

    @staticmethod
    def convert_to_markdown(fix_packs_output: FixPacksOutput) -> str:
        rows: List[str] = []

        if not fix_packs_output.fix_packs:
            rows.append("No fix packs generated. All blockers were placed into FP0.")
            return "\n".join(rows)

        for fix_pack in fix_packs_output.fix_packs:
            rows.append(f"### {fix_pack.id}: {fix_pack.title}")
            rows.append(f"- Priority: {fix_pack.priority.value}")
            rows.append("- Blockers:")
            for blocker_id in fix_pack.blocker_ids:
                rows.append(f"  - {blocker_id}")
            rows.append("")

        return "\n".join(rows).rstrip()

    @classmethod
    def execute(
        cls,
        llm: LLM,
        user_prompt: str,
        pillars_assessment_json: str,
        blockers_json: str,
    ) -> "FixPack":
        """Generate fix packs using pipeline context and serialized step outputs."""
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        if not isinstance(pillars_assessment_json, str):
            raise ValueError("Invalid pillars_assessment_json.")
        if not isinstance(blockers_json, str):
            raise ValueError("Invalid blockers_json.")

        try:
            pillars_input = PillarsInput.model_validate_json(pillars_assessment_json)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON payload for pillars assessment.") from exc

        try:
            blockers_output = BlockersOutput.model_validate_json(blockers_json)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON payload for blockers.") from exc

        status_map = _status_by_pillar(pillars_input.pillars)
        fp0_blocker_ids = _select_fp0_blockers(
            blockers_output.blockers,
            status_map,
            MUST_FIX_REASON_CODES,
        )

        remaining_blockers = [
            blocker for blocker in blockers_output.blockers if blocker.id not in fp0_blocker_ids
        ]

        llm_payload = _build_user_prompt(
            remaining_blockers,
            status_map,
            MUST_FIX_REASON_CODES,
            fp0_blocker_ids,
        )

        non_fp0_fix_packs: List[FixPackEntry] = []
        llm_metadata: Dict[str, object] = {
            "llm_invoked": False,
            "llm_classname": None,
            "duration": 0,
            "response_byte_count": 0,
            "raw_context_bytes": len(user_prompt.encode("utf-8")),
            "pillars_payload_bytes": len(pillars_assessment_json.encode("utf-8")),
            "blockers_payload_bytes": len(blockers_json.encode("utf-8")),
            "fp0_blocker_ids": fp0_blocker_ids,
            "remaining_blocker_ids": [blocker.id for blocker in remaining_blockers],
            "fp0_title": FP0_TITLE,
        }

        if not blockers_output.blockers:
            llm_metadata["status"] = "No blockers provided."
        elif not remaining_blockers:
            llm_metadata["status"] = "All blockers assigned to FP0; no clustering required."

        if remaining_blockers:
            chat_messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=FIX_PACK_SYSTEM_PROMPT),
                ChatMessage(role=MessageRole.USER, content=llm_payload),
            ]

            structured_llm = llm.as_structured_llm(NonFP0FixPacks)
            start_time = time.perf_counter()
            try:
                chat_response = structured_llm.chat(chat_messages)
            except Exception as exc:
                logger.error("LLM chat interaction failed.", exc_info=True)
                raise ValueError("LLM chat interaction failed.") from exc
            end_time = time.perf_counter()

            raw_output = chat_response.raw.model_dump()
            non_fp0_fix_packs = [FixPackEntry.model_validate(pack) for pack in raw_output["fix_packs"]]

            llm_metadata.update(
                {
                    "llm_invoked": True,
                    "llm_classname": llm.class_name(),
                    "duration": int(ceil(end_time - start_time)),
                    "response_byte_count": len(json.dumps(raw_output).encode("utf-8")),
                }
            )

        fix_packs: List[FixPackEntry] = []
        if fp0_blocker_ids:
            fix_packs.append(
                FixPackEntry(
                    id="FP0",
                    title=FP0_TITLE,
                    blocker_ids=fp0_blocker_ids,
                    priority=FixPackPriorityEnum.IMMEDIATE,
                )
            )

        fix_packs.extend(non_fp0_fix_packs)

        _validate_fix_packs(
            non_fp0_fix_packs,
            [blocker.id for blocker in blockers_output.blockers],
            fp0_blocker_ids,
        )

        response_model = FixPacksOutput(fix_packs=fix_packs)
        markdown = cls.convert_to_markdown(response_model)
        return cls(
            system_prompt=FIX_PACK_SYSTEM_PROMPT,
            user_prompt=llm_payload,
            response=response_model.model_dump(),
            metadata=llm_metadata,
            markdown=markdown,
        )


def _status_by_pillar(pillars: Sequence[PillarItem]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for item in pillars:
        pillar_name = item.pillar.value if isinstance(item.pillar, Enum) else str(item.pillar)
        status_value = item.status.value if isinstance(item.status, Enum) else str(item.status)
        mapping[pillar_name] = status_value
    return mapping


def _select_fp0_blockers(
    blockers: Sequence[Blocker],
    status_map: Dict[str, str],
    must_fix_codes: Iterable[str],
) -> List[str]:
    must_fix_set = set(must_fix_codes)
    fp0_ids: List[str] = []
    for blocker in blockers:
        pillar_status = status_map.get(blocker.pillar)
        if pillar_status == StatusEnum.GRAY:
            fp0_ids.append(blocker.id)
            continue
        if any(code in must_fix_set for code in blocker.reason_codes):
            fp0_ids.append(blocker.id)
    return fp0_ids


def _build_user_prompt(
    remaining_blockers: Sequence[Blocker],
    status_map: Dict[str, str],
    must_fix_codes: Sequence[str],
    fp0_blocker_ids: Sequence[str],
) -> str:
    payload = {
        "status_by_pillar": status_map,
        "must_fix_reason_codes": sorted(set(must_fix_codes)),
        "fp0_blocker_ids": list(fp0_blocker_ids),
        "blockers": [
            {
                "id": blocker.id,
                "pillar": blocker.pillar,
                "title": blocker.title,
                "reason_codes": blocker.reason_codes,
                "acceptance_tests": blocker.acceptance_tests,
                "artifacts_required": blocker.artifacts_required,
                "owner": blocker.owner,
            }
            for blocker in remaining_blockers
        ],
    }
    return json.dumps(payload, indent=2)


def _validate_fix_packs(
    fix_packs: Sequence[FixPackEntry],
    known_blocker_ids: Sequence[str],
    fp0_blocker_ids: Sequence[str],
) -> None:
    known_ids = set(known_blocker_ids)
    fp0_set = set(fp0_blocker_ids)
    seen_pack_ids: set[str] = set()
    covered_blockers: set[str] = set()

    sequential_ids: List[str] = []

    for fix_pack in fix_packs:
        if fix_pack.id in seen_pack_ids:
            raise ValueError(f"Duplicate fix pack id detected: {fix_pack.id}")
        seen_pack_ids.add(fix_pack.id)

        if not fix_pack.id.startswith("FP"):
            raise ValueError(f"Fix pack id must start with 'FP': {fix_pack.id}")
        sequential_ids.append(fix_pack.id)

        for blocker_id in fix_pack.blocker_ids:
            if blocker_id not in known_ids:
                raise ValueError(f"Unknown blocker id in fix pack {fix_pack.id}: {blocker_id}")
            if blocker_id in fp0_set:
                raise ValueError(
                    f"Blocker {blocker_id} assigned to FP0 cannot appear in {fix_pack.id}"
                )
            if blocker_id in covered_blockers:
                raise ValueError(f"Blocker {blocker_id} assigned to multiple fix packs")
            covered_blockers.add(blocker_id)

    expected_blockers = set(known_ids) - fp0_set
    if covered_blockers != expected_blockers:
        missing = expected_blockers - covered_blockers
        extra = covered_blockers - expected_blockers
        raise ValueError(
            "Fix pack coverage mismatch. "
            f"Missing blockers: {sorted(missing)}, extra blockers: {sorted(extra)}"
        )

    expected_ids = [f"FP{index + 1}" for index in range(len(fix_packs))]
    if sequential_ids != expected_ids:
        raise ValueError(
            "Non-FP0 fix pack IDs must be sequential starting at FP1 "
            f"(expected {expected_ids}, received {sequential_ids})."
        )


if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    pillars_example = {
        "pillars": [
            {
                "pillar": PillarEnum.HumanStability.value,
                "status": "YELLOW",
                "reason_codes": ["STAFF_AVERSION"],
                "evidence_todo": ["Stakeholder interviews"]
            },
            {
                "pillar": PillarEnum.EconomicResilience.value,
                "status": "GRAY",
                "reason_codes": ["CONTINGENCY_LOW"],
                "evidence_todo": ["Budget scenario analysis"]
            },
            {
                "pillar": PillarEnum.EcologicalIntegrity.value,
                "status": "YELLOW",
                "reason_codes": ["WATER_STRESS"],
                "evidence_todo": ["Water sourcing assessment"]
            },
            {
                "pillar": PillarEnum.Rights_Legality.value,
                "status": "RED",
                "reason_codes": ["DPIA_GAPS", "ETHICS_VAGUE"],
                "evidence_todo": ["Run DPIA v1"]
            }
        ]
    }

    blockers_example = {
        "source_pillars": [PillarEnum.EconomicResilience.value, PillarEnum.Rights_Legality.value, PillarEnum.HumanStability.value],
        "blockers": [
            {
                "id": "B1",
                "pillar": PillarEnum.EconomicResilience.value,
                "title": "Budget contingency below policy floor",
                "reason_codes": ["CONTINGENCY_LOW"],
                "acceptance_tests": ["15% contingency approved"],
                "artifacts_required": ["Budget_v3.xlsx"],
                "owner": "Finance",
                "rom": {"cost_band": "MEDIUM", "eta_days": 10}
            },
            {
                "id": "B2",
                "pillar": PillarEnum.Rights_Legality.value,
                "title": "DPIA not initiated for launch regions",
                "reason_codes": ["DPIA_GAPS"],
                "acceptance_tests": ["DPIA submitted for all regions"],
                "artifacts_required": ["DPIA_Report.pdf"],
                "owner": "Legal",
                "rom": {"cost_band": "MEDIUM", "eta_days": 14}
            },
            {
                "id": "B3",
                "pillar": PillarEnum.HumanStability.value,
                "title": "Stakeholder readiness unclear",
                "reason_codes": ["STAFF_AVERSION"],
                "acceptance_tests": ["Stakeholder survey ≥70% positive"],
                "artifacts_required": ["Stakeholder_Survey.xlsx"],
                "owner": "PMO",
                "rom": {"cost_band": "LOW", "eta_days": 7}
            },
            {
                "id": "B4",
                "pillar": PillarEnum.EcologicalIntegrity.value,
                "title": "Water sourcing plan incomplete",
                "reason_codes": ["WATER_STRESS"],
                "acceptance_tests": ["Signed water supply MOU"],
                "artifacts_required": ["Water_MOU.pdf"],
                "owner": "Operations",
                "rom": {"cost_band": "MEDIUM", "eta_days": 9}
            }
        ]
    }

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    prompt = (
        "File '029-1-pillars_assessment_raw.json':\n"
        f"{json.dumps(pillars_example, indent=2)}\n\n"
        "File '029-3-blockers_raw.json':\n"
        f"{json.dumps(blockers_example, indent=2)}"
    )

    result = FixPack.execute(
        llm=llm,
        user_prompt=prompt,
        pillars_assessment_json=json.dumps(pillars_example),
        blockers_json=json.dumps(blockers_example),
    )
    print(json.dumps(result.response, indent=2))
    print("\nMarkdown:\n")
    print(result.markdown)
    print("\nMetadata:")
    print(json.dumps(result.metadata, indent=2))
