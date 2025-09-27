"""
Step 1: Pillars assessment with resilient validation and LLM-friendly schema.

This module combines the reliability of the original pillars implementation with the
strict repair rules described in viability/README.md. It keeps the JSON contract small
and enum-driven so GPT-5 style models can comply, while still providing:

- Structured prompts and metadata capture (works well with llamalindex LLMs).
- Auto-repair that enforces status/score bands, evidence gating, and reason-code whitelists.
- Deterministic markdown rendering (never trust the model to format it).

Usage
-----

```
from planexe.viability.pillars4 import PillarsAssessmentResult
from planexe.llm_factory import get_llm

llm = get_llm("gpt-4o-mini")
result = PillarsAssessmentResult.execute(llm, plan_text)
print(result.markdown)
```

PROMPT> python -m planexe.viability.pillars4
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

PILLAR_DISPLAY_NAMES: Dict[str, str] = {
    "HumanStability": "Human Stability",
    "EconomicResilience": "Economic Resilience",
    "EcologicalIntegrity": "Ecological Integrity",
    "Rights_Legality": "Rights & Legality",
}

STATUS_ENUM: List[str] = ["GREEN", "YELLOW", "RED", "GRAY"]

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

STATUS_TO_SCORE = {
    "GREEN": (70, 100),
    "YELLOW": (40, 69),
    "RED": (0, 39),
    "GRAY": None,
}

STATUS_MIDPOINT = {
    "GREEN": 85,
    "YELLOW": 55,
    "RED": 20,
}

DEFAULT_EVIDENCE_ITEM = "Gather evidence for assessment"

# --- NEW: strength codes allowed for GREEN status and canonical evidence templates ---
STRENGTH_REASON_CODES = {
    # Use positive signals that justify GREEN
    "HITL_GOVERNANCE_OK",
}

# Canonical evidence templates per reason code (artifact-first, not actions)
EVIDENCE_TEMPLATES: Dict[str, List[str]] = {
    "TALENT_UNKNOWN": [
        "Talent market scan report (availability, salary ranges, channels)"
    ],
    "CLOUD_CARBON_UNKNOWN": [
        "Cloud carbon baseline (last 30 days) using CCF method (kWh, kgCO2e)"
    ],
    "LEGACY_IT": [
        "IT integration audit (systems map, gap analysis)"
    ],
    "INTEGRATION_RISK": [
        "Middleware integration POC report (data transfer ≥80% on sample)"
    ],
    "DPIA_GAPS": [
        "Top-N data sources: licenses + DPIAs bundle"
    ],
    "LICENSE_GAPS": [
        "License registry (source, terms, expiry)"
    ],
    "ABS_UNDEFINED": [
        "ABS/benefit-sharing term sheet + playbook"
    ],
    "CLIMATE_UNQUANTIFIED": [
        "Climate exposure maps (2030/2040/2050) + site vulnerability memo"
    ],
    "WATER_STRESS": [
        "Water budget & drought plan baseline for target sites"
    ],
    "CONTINGENCY_LOW": [
        "Budget v2 with ≥10% contingency + Monte Carlo risk workbook"
    ],
    "SINGLE_CUSTOMER": [
        "Market expansion memo (3 jurisdictions) + risk/opportunity analysis"
    ],
    "ETHICS_VAGUE": [
        "Normative Charter v1.0 with auditable rules & dissent logging"
    ],
}

def _canonicalize_evidence(pillar: str, reason_codes: List[str], evidence_todo: List[str]) -> List[str]:
    """
    Replace action-y items with artifact names and fill from templates.
    Cap at 2 items to keep Step-1 tight.
    """
    out: List[str] = []
    # Auto-rewrite common vague lines
    rewrites = {
        "recruit additional engineers": None,  # drop from step-1; becomes a blocker if needed
        "offset": None,  # offsets are not evidence; baseline first
        "carbon offset": None,
        "research carbon offset": None,
    }
    for item in evidence_todo or []:
        lower = item.lower()
        if any(k in lower for k in rewrites.keys()):
            continue
        out.append(item.strip())
    # Add canonical artifacts per reason code
    for rc in reason_codes:
        for tmpl in EVIDENCE_TEMPLATES.get(rc, []):
            if tmpl not in out:
                out.append(tmpl)
    # Cap to 2 items
    return out[:2]

# ---------------------------------------------------------------------------
# Lightweight schema for structured output (keeps GPT-5 happy)
# ---------------------------------------------------------------------------

class PillarItemSchema(BaseModel):
    pillar: str = Field(..., description="Pillar name from PILLAR_ORDER")
    status: str = Field(..., description="Status indicator")
    score: Optional[int] = Field(None, description="Score 0-100 matching the status band")
    reason_codes: Optional[List[str]] = Field(default=None)
    evidence_todo: Optional[List[str]] = Field(default=None)

    class Config:
        extra = "ignore"


class PillarsSchema(BaseModel):
    pillars: List[PillarItemSchema] = Field(default_factory=list)

    class Config:
        extra = "ignore"


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

PILLARS_SYSTEM_PROMPT = f"""
You output JSON only. No prose, no markdown.
Task: Step 1 (PILLARS) of the Viability protocol. Emit an object with the field
"pillars" (array of 4 items).

Rules:
- Emit exactly one item per pillar in this order: {', '.join(PILLAR_ORDER)}.
- Status must be one of {', '.join(STATUS_ENUM)}.
- reason_codes must come from the whitelist for each pillar:
  {json.dumps(REASON_CODES_BY_PILLAR)}
- Provide a numeric score for any pillar that is not GRAY.
- Score must sit inside the status band: GREEN 70-100, YELLOW 40-69, RED 0-39.
- GREEN requires evidence_todo to be empty. If unsure, use GRAY and add evidence_todo items.
- If there are no clear negatives, leave reason_codes empty.
- Keep evidence_todo short bullet fragments.

Return JSON shaped like:
{{
  "pillars": [
    {{"pillar":"HumanStability","status":"YELLOW","score":60,
      "reason_codes":["STAFF_AVERSION"],
      "evidence_todo":["Stakeholder survey baseline"]}}
  ]
}}
""".strip()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()
    if not text:
        return {"pillars": []}

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
    return {"pillars": []}


def _ensure_list(value: Optional[Iterable[str]]) -> List[str]:
    if not value:
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _score_in_band(score: int, status: str) -> bool:
    band = STATUS_TO_SCORE.get(status)
    if band is None:
        return True
    lower, upper = band
    return lower <= score <= upper


def _sanitize_score(status: str, score: Optional[int]) -> Optional[int]:
    if status == "GRAY":
        return None
    if score is None:
        return STATUS_MIDPOINT[status]
    if not isinstance(score, int):
        try:
            score = int(score)
        except (TypeError, ValueError):
            return STATUS_MIDPOINT[status]
    if _score_in_band(score, status):
        return score
    return STATUS_MIDPOINT[status]


def _sanitize_reason_codes(pillar: str, reason_codes: Optional[Iterable[str]]) -> List[str]:
    allowed = set(REASON_CODES_BY_PILLAR.get(pillar, []))
    sanitized = []
    for code in _ensure_list(reason_codes):
        if code in allowed:
            sanitized.append(code)
    return sanitized


def _sanitize_evidence(status: str, evidence: Optional[Iterable[str]]) -> List[str]:
    sanitized = _ensure_list(evidence)
    if status == "GRAY" and not sanitized:
        return [DEFAULT_EVIDENCE_ITEM]
    if status != "GREEN":
        return sanitized
    # GREEN cannot carry evidence tasks – force empty list
    return []


def _enforce_status_rules(pillar: str, status: str, reason_codes: List[str], evidence: List[str]) -> str:
    if status not in STATUS_ENUM:
        status = "GRAY"
    if status == "GREEN" and evidence:
        status = "YELLOW"
    if status == "GREEN" and any(code in NEGATIVE_REASON_CODES for code in reason_codes):
        status = "YELLOW"
    if status in {"YELLOW", "RED"} and not reason_codes and not evidence:
        status = "GRAY"
    return status


def _sanitize_pillar(raw: Dict[str, Any]) -> Dict[str, Any]:
    pillar = raw.get("pillar")
    if pillar not in PILLAR_ORDER:
        pillar = "Rights_Legality"

    status = raw.get("status", "GRAY")
    if status not in STATUS_ENUM:
        status = "GRAY"

    reason_codes = _sanitize_reason_codes(pillar, raw.get("reason_codes"))
    evidence = _sanitize_evidence(status, raw.get("evidence_todo"))
    status = _enforce_status_rules(pillar, status, reason_codes, evidence)
    evidence = _sanitize_evidence(status, evidence)

    score = _sanitize_score(status, raw.get("score"))

    return {
        "pillar": pillar,
        "status": status,
        "score": score,
        "reason_codes": reason_codes,
        "evidence_todo": evidence,
    }


def _default_pillar(pillar: str) -> Dict[str, Any]:
    return {
        "pillar": pillar,
        "status": "GRAY",
        "score": None,
        "reason_codes": [],
        "evidence_todo": [DEFAULT_EVIDENCE_ITEM],
    }


def validate_and_repair(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Make weak-model output deterministic and policy-compliant."""
    data = dict(payload)  # shallow copy
    pillars = data.get("pillars", [])
    validated: List[Dict[str, Any]] = []

    for p in pillars:
        pillar_name = p.get("pillar", "Rights_Legality")
        status = p.get("status", "GRAY")
        score = p.get("score")
        reason_codes = p.get("reason_codes", []) or []
        evidence_todo = p.get("evidence_todo", []) or []

        # Normalize enums/strings
        try:
            status_enum = status  # Keep as string for compatibility
        except Exception:
            status_enum = "GRAY"
        # Evidence gate: GREEN must have empty evidence_todo
        if status_enum == "GREEN" and evidence_todo:
            status_enum = "YELLOW"
            score = None  # will snap to band midpoint

        # --- NEW: Strength gate for GREEN ---
        if status_enum == "GREEN":
            has_strength = any(rc in STRENGTH_REASON_CODES for rc in reason_codes)
            has_rationale = bool(p.get("strength_rationale"))
            if not (has_strength or has_rationale):
                # Downgrade optimistic GREEN to YELLOW unless we have a strength signal
                status_enum = "YELLOW"
                score = None

        # If YELLOW/RED but no reason codes AND no evidence → GRAY (we lack justification)
        if status_enum in ("YELLOW", "RED") and not reason_codes and not evidence_todo:
            status_enum = "GRAY"
            score = None

        # Canonicalize evidence to artifacts; drop action-y lines
        evidence_todo = _canonicalize_evidence(pillar_name, reason_codes, evidence_todo)

        # Snap score to status band midpoint when needed
        if score is None:
            band = STATUS_TO_SCORE.get(status_enum)
            score = None if band is None else int((band[0] + band[1]) / 2)

        validated.append({
            "pillar": pillar_name,
            "status": status_enum,
            "score": score,
            "reason_codes": reason_codes,
            "evidence_todo": evidence_todo,
            # Expose rationale only if model provided one
            **({"strength_rationale": p["strength_rationale"]} if p.get("strength_rationale") else {}),
        })

    return {"pillars": validated}


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def convert_to_markdown(data: Dict[str, Any]) -> str:
    pillars = data.get("pillars", [])
    status_counts = {status: 0 for status in STATUS_ENUM}
    for pillar in pillars:
        status = pillar.get("status", "GRAY")
        if status in status_counts:
            status_counts[status] += 1

    rows: List[str] = []
    rows.append("# Pillars Assessment")
    rows.append("")
    rows.append("## Summary")
    rows.append(f"- **GREEN**: {status_counts['GREEN']} pillars")
    rows.append(f"- **YELLOW**: {status_counts['YELLOW']} pillars")
    rows.append(f"- **RED**: {status_counts['RED']} pillars")
    rows.append(f"- **GRAY**: {status_counts['GRAY']} pillars")
    rows.append("")
    rows.append("## Pillar Details")

    for pillar in pillars:
        name = pillar.get("pillar", "Unknown")
        display_name = PILLAR_DISPLAY_NAMES.get(name, name)
        status = pillar.get("status", "GRAY")
        score = pillar.get("score", "N/A")
        reason_codes = pillar.get("reason_codes", [])
        evidence = pillar.get("evidence_todo", [])

        rows.append(f"### {display_name}")
        rows.append(f"**Status**: {status} ({score})")
        if reason_codes:
            rows.append(f"**Issues**: {', '.join(reason_codes)}")
        if evidence:
            rows.append("**Evidence Needed:**")
            for item in evidence:
                rows.append(f"- {item}")
        rows.append("")

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
