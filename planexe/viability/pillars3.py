"""
Step 1: Pillars assessment with resilient validation and LLM-friendly schema.

This module combines the reliability of the original pillars implementation with the
strict repair rules described in viability/README.md. It keeps the JSON contract small
and enum-driven so GPT-5 style models can comply, while still providing:

- Structured prompts and metadata capture (works well with llamalindex LLMs).
- Auto-repair that enforces color/score bands, evidence gating, and reason-code whitelists.
- Deterministic markdown rendering (never trust the model to format it).

Usage
-----

```
from planexe.viability.pillars3 import PillarsAssessmentResult
from planexe.llm_factory import get_llm

llm = get_llm("gpt-4o-mini")
result = PillarsAssessmentResult.execute(llm, plan_text)
print(result.markdown)
```

PROMPT> python -m planexe.viability.pillars3
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from math import ceil
from typing import Any, Dict, Iterable, List, Optional

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field

from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & enums (string-based for LLM friendliness)
# ---------------------------------------------------------------------------

PILLAR_ORDER: List[str] = [
    "HumanStability",
    "EconomicResilience",
    "EcologicalIntegrity",
    "Rights_Legality",
]

COLOR_ENUM: List[str] = ["GREEN", "YELLOW", "RED", "GRAY"]

REASON_CODES_BY_PILLAR: Dict[str, List[str]] = {
    "HumanStability": ["TALENT_UNKNOWN", "STAFF_AVERSION"],
    "EconomicResilience": [
        "CONTINGENCY_LOW",
        "SINGLE_CUSTOMER",
        "ALT_COST_UNKNOWN",
        "LEGACY_IT",
        "INTEGRATION_RISK",
    ],
    "EcologicalIntegrity": [
        "CLOUD_CARBON_UNKNOWN",
        "CLIMATE_UNQUANTIFIED",
        "WATER_STRESS",
    ],
    "Rights_Legality": [
        "DPIA_GAPS",
        "LICENSE_GAPS",
        "ABS_UNDEFINED",
        "PERMIT_COMPLEXITY",
        "BIOSECURITY_GAPS",
        "ETHICS_VAGUE",
    ],
}

NEGATIVE_REASON_CODES: List[str] = sorted(
    {code for codes in REASON_CODES_BY_PILLAR.values() for code in codes}
)

COLOR_TO_SCORE = {
    "GREEN": (70, 100),
    "YELLOW": (40, 69),
    "RED": (0, 39),
    "GRAY": None,
}

COLOR_MIDPOINT = {
    "GREEN": 85,
    "YELLOW": 55,
    "RED": 20,
}

DEFAULT_RULES_APPLIED = {
    "color_to_score": {
        "GREEN": [70, 100],
        "YELLOW": [40, 69],
        "RED": [0, 39],
        "GRAY": None,
    },
    "evidence_gate": "No GREEN unless evidence_todo is empty",
}

DEFAULT_EVIDENCE_ITEM = "Gather evidence for assessment"

# ---------------------------------------------------------------------------
# Lightweight schema for structured output (keeps GPT-5 happy)
# ---------------------------------------------------------------------------

class PillarItemSchema(BaseModel):
    pillar: str = Field(..., description="Pillar name from PILLAR_ORDER")
    color: str = Field(..., description="Traffic light color")
    score: Optional[int] = Field(None, description="Score 0-100 matching the color band")
    reason_codes: Optional[List[str]] = Field(default=None)
    evidence_todo: Optional[List[str]] = Field(default=None)

    class Config:
        extra = "ignore"


class PillarsSchema(BaseModel):
    pillars: List[PillarItemSchema] = Field(default_factory=list)
    rules_applied: Optional[Dict[str, Any]] = Field(default=None)

    class Config:
        extra = "ignore"


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

PILLARS_SYSTEM_PROMPT = f"""
You output JSON only. No prose, no markdown.
Task: Step 1 (PILLARS) of the Viability protocol. Emit an object with fields
"pillars" (array of 4 items) and "rules_applied".

Rules:
- Emit exactly one item per pillar in this order: {', '.join(PILLAR_ORDER)}.
- Colors must be one of {', '.join(COLOR_ENUM)}.
- reason_codes must come from the whitelist for each pillar:
  {json.dumps(REASON_CODES_BY_PILLAR)}
- Provide a numeric score for any pillar that is not GRAY.
- Score must sit inside the color band: GREEN 70-100, YELLOW 40-69, RED 0-39.
- GREEN requires evidence_todo to be empty. If unsure, use GRAY and add evidence_todo items.
- If there are no clear negatives, leave reason_codes empty.
- Keep evidence_todo short bullet fragments.

Return JSON shaped like:
{{
  "pillars": [
    {{"pillar":"HumanStability","color":"YELLOW","score":60,
      "reason_codes":["STAFF_AVERSION"],
      "evidence_todo":["Stakeholder survey baseline"]}}
  ],
  "rules_applied": {json.dumps(DEFAULT_RULES_APPLIED)}
}}
""".strip()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()
    if not text:
        return {"pillars": [], "rules_applied": {}}

    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    starts = [m.start() for m in re.finditer(r"\{", text)]
    ends = [m.start() for m in re.finditer(r"\}", text)]
    for start in starts:
        for end in reversed(ends):
            if end <= start:
                continue
            chunk = text[start : end + 1]
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue
    return {"pillars": [], "rules_applied": {}}


def _ensure_list(value: Optional[Iterable[str]]) -> List[str]:
    if not value:
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _score_in_band(score: int, color: str) -> bool:
    band = COLOR_TO_SCORE.get(color)
    if band is None:
        return True
    lower, upper = band
    return lower <= score <= upper


def _sanitize_score(color: str, score: Optional[int]) -> Optional[int]:
    if color == "GRAY":
        return None
    if score is None:
        return COLOR_MIDPOINT[color]
    if not isinstance(score, int):
        try:
            score = int(score)
        except (TypeError, ValueError):
            return COLOR_MIDPOINT[color]
    if _score_in_band(score, color):
        return score
    return COLOR_MIDPOINT[color]


def _sanitize_reason_codes(pillar: str, reason_codes: Optional[Iterable[str]]) -> List[str]:
    allowed = set(REASON_CODES_BY_PILLAR.get(pillar, []))
    sanitized = []
    for code in _ensure_list(reason_codes):
        if code in allowed:
            sanitized.append(code)
    return sanitized


def _sanitize_evidence(color: str, evidence: Optional[Iterable[str]]) -> List[str]:
    sanitized = _ensure_list(evidence)
    if color == "GRAY" and not sanitized:
        return [DEFAULT_EVIDENCE_ITEM]
    if color != "GREEN":
        return sanitized
    # GREEN cannot carry evidence tasks – force empty list
    return []


def _enforce_color_rules(pillar: str, color: str, reason_codes: List[str], evidence: List[str]) -> str:
    if color not in COLOR_ENUM:
        color = "GRAY"
    if color == "GREEN" and evidence:
        color = "YELLOW"
    if color == "GREEN" and any(code in NEGATIVE_REASON_CODES for code in reason_codes):
        color = "YELLOW"
    if color in {"YELLOW", "RED"} and not reason_codes and not evidence:
        color = "GRAY"
    return color


def _sanitize_pillar(raw: Dict[str, Any]) -> Dict[str, Any]:
    pillar = raw.get("pillar")
    if pillar not in PILLAR_ORDER:
        pillar = "Rights_Legality"

    color = raw.get("color", "GRAY")
    if color not in COLOR_ENUM:
        color = "GRAY"

    reason_codes = _sanitize_reason_codes(pillar, raw.get("reason_codes"))
    evidence = _sanitize_evidence(color, raw.get("evidence_todo"))
    color = _enforce_color_rules(pillar, color, reason_codes, evidence)
    evidence = _sanitize_evidence(color, evidence)

    score = _sanitize_score(color, raw.get("score"))

    return {
        "pillar": pillar,
        "color": color,
        "score": score,
        "reason_codes": reason_codes,
        "evidence_todo": evidence,
    }


def _default_pillar(pillar: str) -> Dict[str, Any]:
    return {
        "pillar": pillar,
        "color": "GRAY",
        "score": None,
        "reason_codes": [],
        "evidence_todo": [DEFAULT_EVIDENCE_ITEM],
    }


def validate_and_repair(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {"pillars": []}

    pillars_raw = payload.get("pillars", [])
    if not isinstance(pillars_raw, list):
        pillars_raw = []

    sanitized: List[Dict[str, Any]] = []
    seen = set()
    for raw_item in pillars_raw:
        if not isinstance(raw_item, dict):
            continue
        repaired = _sanitize_pillar(raw_item)
        sanitized.append(repaired)
        seen.add(repaired["pillar"])

    for pillar in PILLAR_ORDER:
        if pillar not in seen:
            sanitized.append(_default_pillar(pillar))

    sanitized.sort(key=lambda item: PILLAR_ORDER.index(item["pillar"]))

    repaired_payload = {
        "pillars": sanitized,
        "rules_applied": DEFAULT_RULES_APPLIED,
    }
    return repaired_payload


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def convert_to_markdown(data: Dict[str, Any]) -> str:
    pillars = data.get("pillars", [])
    color_counts = {color: 0 for color in COLOR_ENUM}
    for pillar in pillars:
        color = pillar.get("color", "GRAY")
        if color in color_counts:
            color_counts[color] += 1

    rows: List[str] = []
    rows.append("# Pillars Assessment")
    rows.append("")
    rows.append("## Summary")
    rows.append(f"- **GREEN**: {color_counts['GREEN']} pillars")
    rows.append(f"- **YELLOW**: {color_counts['YELLOW']} pillars")
    rows.append(f"- **RED**: {color_counts['RED']} pillars")
    rows.append(f"- **GRAY**: {color_counts['GRAY']} pillars")
    rows.append("")
    rows.append("## Pillar Details")

    for pillar in pillars:
        name = pillar.get("pillar", "Unknown")
        color = pillar.get("color", "GRAY")
        score = pillar.get("score", "N/A")
        reason_codes = pillar.get("reason_codes", [])
        evidence = pillar.get("evidence_todo", [])

        rows.append(f"### {name}")
        rows.append(f"**Status**: {color} ({score})")
        if reason_codes:
            rows.append(f"**Issues**: {', '.join(reason_codes)}")
        if evidence:
            rows.append("**Evidence Needed:**")
            for item in evidence:
                rows.append(f"- {item}")
        rows.append("")

    rows.append("## Assessment Rules")
    rows.append(f"- **Evidence Gate**: {DEFAULT_RULES_APPLIED['evidence_gate']}")

    markdown = "\n".join(rows)
    return fix_bullet_lists(markdown)


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------

@dataclass
class PillarsAssessmentResult:
    system_prompt: str
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> "PillarsAssessmentResult":
        if not isinstance(user_prompt, str):
            raise TypeError("user_prompt must be a string")
        if not isinstance(llm, LLM):
            raise TypeError("llm must be an instance of LLM")

        system_prompt = PILLARS_SYSTEM_PROMPT
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        start_time = time.perf_counter()
        raw_payload: Dict[str, Any] = {}
        raw_text = ""
        used_structured = False

        try:
            structured_llm = llm.as_structured_llm(PillarsSchema)
            chat_response = structured_llm.chat(messages)
            used_structured = True
            raw_payload = chat_response.raw.model_dump()
            raw_text = chat_response.message.content or json.dumps(raw_payload)
        except Exception as exc:  # pragma: no cover - depends on model support
            logger.info("Structured output failed, falling back to plain JSON parse: %s", exc)
            try:
                chat_response = llm.chat(messages)
            except Exception as chat_exc:  # pragma: no cover - unexpected transport failure
                raise RuntimeError("LLM chat interaction failed") from chat_exc
            raw_text = chat_response.message.content or ""
            raw_payload = _extract_json_from_text(raw_text)

        duration = time.perf_counter() - start_time
        response_byte_count = len(raw_text.encode("utf-8")) if raw_text else len(json.dumps(raw_payload).encode("utf-8"))

        validated_response = validate_and_repair(raw_payload)

        metadata = dict(getattr(llm, "metadata", {}) or {})
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = int(ceil(duration))
        metadata["response_byte_count"] = response_byte_count
        metadata["used_structured_output"] = used_structured

        markdown = convert_to_markdown(validated_response)

        return cls(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=validated_response,
            markdown=markdown,
            metadata=metadata,
        )

    def to_dict(
        self,
        include_metadata: bool = True,
        include_system_prompt: bool = True,
        include_user_prompt: bool = True,
    ) -> Dict[str, Any]:
        result = dict(self.response)
        result["markdown"] = self.markdown
        if include_metadata:
            result["metadata"] = self.metadata
        if include_system_prompt:
            result["system_prompt"] = self.system_prompt
        if include_user_prompt:
            result["user_prompt"] = self.user_prompt
        return result

    def save_raw(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI demo for manual runs
# ---------------------------------------------------------------------------


def main() -> None:  # pragma: no cover - convenience helper
    from planexe.llm_factory import get_llm

    plan_text = """
    Project: Sustainable Data Center Migration

    We plan to migrate our legacy data center infrastructure to a cloud-based solution
    with renewable energy sources. The project involves moving 50+ servers, updating
    security protocols, and ensuring compliance with new data protection regulations.

    Budget: $2M allocated, with 5% contingency
    Timeline: 12 months
    Team: 15 engineers, 3 compliance specialists

    Risks: Legacy system integration, data sovereignty requirements, staff training needs
    """.strip()

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)
    result = PillarsAssessmentResult.execute(llm, plan_text)
    print(json.dumps(result.response, indent=2, ensure_ascii=False))
    print("\nMarkdown:\n")
    print(result.markdown)


if __name__ == "__main__":  # pragma: no cover
    main()
