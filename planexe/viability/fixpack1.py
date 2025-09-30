"""
Implements Step 3 of the ViabilityAssessor protocol: Fix Pack generation.

This module consumes the JSON outputs from Step 1 (Pillars) and Step 2 (Blockers)
and emits a structured set of Fix Packs that bundle blockers into execution-ready
clusters. FP0 is always reserved for the pre-commit gate containing the blockers
that must be resolved before proceeding.

PROMPT> python -u -m planexe.viability.fixpack1 | tee output1.txt
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from math import ceil
from typing import Dict, List, Optional, Sequence

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, ValidationError, conlist

logger = logging.getLogger(__name__)

# --- Enums mirroring viability/README.md ---

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


class FixPackPriorityEnum(str, Enum):
    IMMEDIATE = "Immediate"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


MUST_FIX_REASON_CODES = {"DPIA_GAPS", "CONTINGENCY_LOW", "ETHICS_VAGUE"}

# --- Pydantic models for input payloads ---


class PillarItem(BaseModel):
    pillar: str
    status: str
    score: Optional[int] = None
    reason_codes: List[str] = Field(default_factory=list)
    evidence_todo: List[str] = Field(default_factory=list)


class PillarsInput(BaseModel):
    pillars: List[PillarItem]


class ROM(BaseModel):
    cost_band: str
    eta_days: int


class Blocker(BaseModel):
    id: str
    pillar: str
    title: str
    reason_codes: List[str] = Field(default_factory=list)
    acceptance_tests: List[str] = Field(default_factory=list)
    artifacts_required: List[str] = Field(default_factory=list)
    owner: Optional[str] = None
    rom: Optional[ROM] = None


class BlockersOutput(BaseModel):
    source_pillars: List[str] = Field(default_factory=list)
    blockers: List[Blocker]


class FixPack(BaseModel):
    id: str
    title: str
    blocker_ids: conlist(str, min_length=1)
    priority: FixPackPriorityEnum


class FixPacksOutput(BaseModel):
    fix_packs: List[FixPack]


class NonFP0FixPacks(BaseModel):
    fix_packs: List[FixPack]


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
class FixPackGenerationResult:
    system_prompt: str
    user_prompt: str
    response: Dict[str, object]
    metadata: Dict[str, object]

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
        return data

    def save_json(self, file_path: str, include_full_context: bool = False) -> None:
        payload = self.to_dict() if include_full_context else self.response
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        logger.info("Fix pack data saved to %s", file_path)


# --- Helper functions ---


def _status_by_pillar(pillars: Sequence[PillarItem]) -> Dict[str, str]:
    return {item.pillar: item.status for item in pillars}


def _select_fp0_blockers(
    blockers: Sequence[Blocker],
    status_map: Dict[str, str],
    must_fix_codes: Sequence[str],
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
        "must_fix_reason_codes": list(must_fix_codes),
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
    fix_packs: Sequence[FixPack],
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


# --- Main generator ---


class FixPackGenerator:
    @classmethod
    def execute(
        cls,
        llm: LLM,
        pillars_json: str,
        blockers_json: str,
        fp0_title: str = "Pre-Commit Gate",
        fp0_priority: FixPackPriorityEnum = FixPackPriorityEnum.IMMEDIATE,
    ) -> FixPackGenerationResult:
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")

        try:
            pillars_input = PillarsInput.model_validate_json(pillars_json)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON payload for pillars.") from exc

        try:
            blockers_output = BlockersOutput.model_validate_json(blockers_json)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON payload for blockers.") from exc

        if not blockers_output.blockers:
            response = FixPacksOutput(fix_packs=[]).model_dump()
            metadata = {
                "status": "No blockers provided.",
                "llm_invoked": False,
            }
            return FixPackGenerationResult(
                system_prompt=FIX_PACK_SYSTEM_PROMPT,
                user_prompt=json.dumps({}, indent=2),
                response=response,
                metadata=metadata,
            )

        status_map = _status_by_pillar(pillars_input.pillars)
        fp0_blocker_ids = _select_fp0_blockers(
            blockers_output.blockers, status_map, MUST_FIX_REASON_CODES
        )

        remaining_blockers = [
            blocker for blocker in blockers_output.blockers if blocker.id not in fp0_blocker_ids
        ]

        user_prompt = _build_user_prompt(
            remaining_blockers,
            status_map,
            MUST_FIX_REASON_CODES,
            fp0_blocker_ids,
        )

        non_fp0_fix_packs: List[FixPack] = []
        llm_metadata: Dict[str, object] = {
            "llm_invoked": False,
            "llm_classname": None,
            "duration": 0,
            "response_byte_count": 0,
        }

        if remaining_blockers:
            chat_messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=FIX_PACK_SYSTEM_PROMPT),
                ChatMessage(role=MessageRole.USER, content=user_prompt),
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
            non_fp0_fix_packs = [FixPack.model_validate(pack) for pack in raw_output["fix_packs"]]

            llm_metadata.update(
                {
                    "llm_invoked": True,
                    "llm_classname": llm.class_name(),
                    "duration": int(ceil(end_time - start_time)),
                    "response_byte_count": len(json.dumps(raw_output).encode("utf-8")),
                }
            )

        fix_packs: List[FixPack] = []
        if fp0_blocker_ids:
            fix_packs.append(
                FixPack(
                    id="FP0",
                    title=fp0_title,
                    blocker_ids=fp0_blocker_ids,
                    priority=fp0_priority,
                )
            )

        fix_packs.extend(non_fp0_fix_packs)

        _validate_fix_packs(
            non_fp0_fix_packs,
            [blocker.id for blocker in blockers_output.blockers],
            fp0_blocker_ids,
        )

        response_model = FixPacksOutput(fix_packs=fix_packs)
        result = FixPackGenerationResult(
            system_prompt=FIX_PACK_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response=response_model.model_dump(),
            metadata=llm_metadata,
        )
        return result


if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    pillars_example = {
        "pillars": [
            {
                "pillar": "HumanStability",
                "status": "YELLOW",
                "score": 55,
                "reason_codes": ["STAFF_AVERSION"],
                "evidence_todo": ["Stakeholder interviews"]
            },
            {
                "pillar": "EconomicResilience",
                "status": "GRAY",
                "score": None,
                "reason_codes": ["CONTINGENCY_LOW"],
                "evidence_todo": ["Budget scenario analysis"]
            },
            {
                "pillar": "EcologicalIntegrity",
                "status": "YELLOW",
                "score": 60,
                "reason_codes": ["WATER_STRESS"],
                "evidence_todo": ["Water sourcing assessment"]
            },
            {
                "pillar": "Rights_Legality",
                "status": "RED",
                "score": 25,
                "reason_codes": ["DPIA_GAPS", "ETHICS_VAGUE"],
                "evidence_todo": ["Run DPIA v1"]
            }
        ]
    }

    blockers_example = {
        "source_pillars": ["EconomicResilience", "Rights_Legality", "HumanStability"],
        "blockers": [
            {
                "id": "B1",
                "pillar": "EconomicResilience",
                "title": "Budget contingency below policy floor",
                "reason_codes": ["CONTINGENCY_LOW"],
                "acceptance_tests": ["15% contingency approved"],
                "artifacts_required": ["Budget_v3.xlsx"],
                "owner": "Finance",
                "rom": {"cost_band": "MEDIUM", "eta_days": 10}
            },
            {
                "id": "B2",
                "pillar": "Rights_Legality",
                "title": "DPIA not initiated for launch regions",
                "reason_codes": ["DPIA_GAPS"],
                "acceptance_tests": ["DPIA submitted for all regions"],
                "artifacts_required": ["DPIA_Report.pdf"],
                "owner": "Legal",
                "rom": {"cost_band": "MEDIUM", "eta_days": 14}
            },
            {
                "id": "B3",
                "pillar": "HumanStability",
                "title": "Stakeholder readiness unclear",
                "reason_codes": ["STAFF_AVERSION"],
                "acceptance_tests": ["Stakeholder survey ≥70% positive"],
                "artifacts_required": ["Stakeholder_Survey.xlsx"],
                "owner": "PMO",
                "rom": {"cost_band": "LOW", "eta_days": 7}
            },
            {
                "id": "B4",
                "pillar": "EcologicalIntegrity",
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

    pillars_json = json.dumps(pillars_example)
    blockers_json = json.dumps(blockers_example)

    result = FixPackGenerator.execute(llm, pillars_json, blockers_json)
    print(json.dumps(result.response, indent=2))
    print("\nMetadata:")
    print(json.dumps(result.metadata, indent=2))
