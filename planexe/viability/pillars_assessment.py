"""
Pillars assessment

Auto-repair that enforces status/score bands, evidence gating, and reason-code whitelists.

IDEA: Should the EVIDENCE_TEMPLATES contain lists of strings, when the lists only have one item. Seems like it can be simplified, to a single string.
IDEA: Extract the REASON_CODES_BY_PILLAR, DEFAULT_EVIDENCE_BY_PILLAR, EVIDENCE_TEMPLATES into a JSON file.

PROMPT> python -u -m planexe.viability.pillars_assessment | tee output_a.txt
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
from planexe.viability.pillars_prompt import make_pillars_system_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & enums
# ---------------------------------------------------------------------------

STATUS_ENUM: List[str] = ["GREEN", "YELLOW", "RED", "GRAY"]

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

# This list is not exhaustive, more items are likely to be added over time.
REASON_CODES_BY_PILLAR: Dict[str, List[str]] = {
    "HumanStability": [
        "TALENT_UNKNOWN",
        "STAFF_AVERSION",
        "GOVERNANCE_WEAK",
        "CHANGE_MGMT_GAPS",
        "TRAINING_GAPS",
        "STAKEHOLDER_CONFLICT",
        "SAFETY_CULTURE_WEAK",
    ],
    "EconomicResilience": [
        "CONTINGENCY_LOW",
        "SINGLE_CUSTOMER",
        "ALT_COST_UNKNOWN",
        "LEGACY_IT",
        "INTEGRATION_RISK",
        "UNIT_ECON_UNKNOWN",
        "SUPPLIER_CONCENTRATION",
        "SPOF_DEPENDENCY",
        "BIA_MISSING",
        "DR_TEST_GAPS",
    ],
    "EcologicalIntegrity": [
        "CLOUD_CARBON_UNKNOWN",
        "CLIMATE_UNQUANTIFIED",
        "WATER_STRESS",
        "EIA_MISSING",
        "BIODIVERSITY_RISK_UNSET",
        "WASTE_MANAGEMENT_GAPS",
        "WATER_PERMIT_RISK",
    ],
    "Rights_Legality": [
        "DPIA_GAPS",
        "LICENSE_GAPS",
        "ABS_UNDEFINED",
        "PERMIT_COMPLEXITY",
        "BIOSECURITY_GAPS",
        "ETHICS_VAGUE",
        "INFOSEC_GAPS",
        "DATA_QUALITY_WEAK",
        "MODEL_RISK_UNQUANTIFIED",
        "CROSSBORDER_RISK",
        "CONSENT_MODEL_WEAK",
    ],
}

NEGATIVE_REASON_CODES: List[str] = sorted(
    {code for codes in REASON_CODES_BY_PILLAR.values() for code in codes}
)

DEFAULT_EVIDENCE_BY_PILLAR = {
    "HumanStability": [
        "Stakeholder map + skills gap snapshot",
        "Change plan v1 (communications, training, adoption KPIs)",
    ],
    "EconomicResilience": [
        "Assumption ledger v1 + sensitivity table",
        "Cost model v2 (on-prem vs cloud TCO)",
    ],
    "EcologicalIntegrity": [
        "Environmental baseline note (scope, metrics)",
        "Cloud carbon estimate v1 (regions/services)",
    ],
    "Rights_Legality": [
        "Regulatory mapping v1 + open questions list",
        "Licenses & permits inventory + gaps list",
    ],
}

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

# --- strength codes allowed for GREEN status and canonical evidence templates ---
STRENGTH_REASON_CODES = {
    # Use positive signals that justify GREEN
    "HITL_GOVERNANCE_OK",
}

# Canonical evidence templates per reason code (artifact-first, not actions)
# This list is not exhaustive, more items are likely to be added over time.
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
    "GOVERNANCE_WEAK": [
        "RACI + decision log v1 (scope: this plan)"
    ],
    "CHANGE_MGMT_GAPS": [
        "Change plan v1 (communications, training, adoption KPIs)"
    ],
    "TRAINING_GAPS": [
        "Training needs assessment + skill gap analysis report"
    ],
    "STAKEHOLDER_CONFLICT": [
        "Stakeholder conflict resolution framework + escalation matrix"
    ],
    "SAFETY_CULTURE_WEAK": [
        "Safety culture assessment report (survey, incident analysis)"
    ],
    "UNIT_ECON_UNKNOWN": [
        "Unit economics model v1 + sensitivity table (key drivers)"
    ],
    "SUPPLIER_CONCENTRATION": [
        "Supplier risk register v1 + diversification plan"
    ],
    "SPOF_DEPENDENCY": [
        "SPOF analysis note + mitigation options"
    ],
    "BIA_MISSING": [
        "Business impact analysis v1 (RTO/RPO, critical processes)"
    ],
    "DR_TEST_GAPS": [
        "DR/BCP test report (last test + outcomes)"
    ],
    "EIA_MISSING": [
        "Environmental impact assessment scope + baseline metrics"
    ],
    "BIODIVERSITY_RISK_UNSET": [
        "Biodiversity screening memo (species/habitat, mitigation)"
    ],
    "WASTE_MANAGEMENT_GAPS": [
        "Waste management plan v1 (types, handling, compliance)"
    ],
    "WATER_PERMIT_RISK": [
        "Water permit inventory + compliance status"
    ],
    "INFOSEC_GAPS": [
        "Threat model + control mapping (e.g., STRIDE ↔ CIS/NIST)"
    ],
    "DATA_QUALITY_WEAK": [
        "Data profiling report (completeness, accuracy, drift)"
    ],
    "MODEL_RISK_UNQUANTIFIED": [
        "Model card + evaluation report (intended use, metrics, limits)"
    ],
    "CROSSBORDER_RISK": [
        "Data flow map + transfer mechanism memo (SCCs/BCRs)"
    ],
    "CONSENT_MODEL_WEAK": [
        "Consent/permission model spec + audit sample"
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
# Lightweight schema for structured output
# ---------------------------------------------------------------------------

class PillarItemSchema(BaseModel):
    pillar: str = Field(..., description="Pillar name from PILLAR_ORDER")
    status: str = Field(..., description="Status indicator")
    score: Optional[int] = Field(None, description="Score 0-100 matching the status band")
    reason_codes: Optional[List[str]] = Field(default=None)
    evidence_todo: Optional[List[str]] = Field(default=None)
    strength_rationale: Optional[str] = Field(default=None, description="Short rationale for why status is GREEN; omit otherwise")


    class Config:
        extra = "ignore"


class PillarsSchema(BaseModel):
    pillars: List[PillarItemSchema] = Field(default_factory=list)

    class Config:
        extra = "ignore"


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

PILLARS_SYSTEM_PROMPT = make_pillars_system_prompt(PILLAR_ORDER, REASON_CODES_BY_PILLAR, STATUS_TO_SCORE)

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

def enforce_gray_evidence(
    items: List[Dict[str, Any]],
    defaults: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """
    Ensure every GRAY pillar has 1–2 artifact-style evidence items.
    If missing, fill from `defaults[pillar]`; if that’s empty/missing, use a generic fallback.
    """
    GENERIC_FALLBACK: List[str] = ["Baseline note v1 (scope, metrics)"]

    for it in items:
        if it.get("status") == "GRAY":
            raw_ev = it.get("evidence_todo") or []
            ev: List[str] = [e for e in raw_ev if isinstance(e, str) and e.strip()]
            if not ev:
                pillar = str(it.get("pillar", ""))
                ev = list(defaults.get(pillar, GENERIC_FALLBACK))[:2]
            it["evidence_todo"] = ev[:2]
    return items

def enforce_colored_evidence(
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Ensure YELLOW/RED pillars have at least one artifact-style evidence item.
    If empty, insert a minimal default. Also cap evidence_todo to max 2 items.
    """
    DEFAULT_EVIDENCE: List[str] = ["Issue analysis memo v1"]

    for it in items:
        status = it.get("status")
        if status in {"YELLOW", "RED"}:
            raw_ev = it.get("evidence_todo") or []
            ev: List[str] = [e for e in raw_ev if isinstance(e, str) and e.strip()]
            if not ev:
                ev = DEFAULT_EVIDENCE[:1]
            it["evidence_todo"] = ev[:2]
    return items

def validate_and_repair(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Make weak-model output deterministic and policy-compliant."""
    data = dict(payload)  # shallow copy
    pillars = data.get("pillars", [])
    validated: List[Dict[str, Any]] = []

    for p in pillars:
        pillar_name = p.get("pillar", "Rights_Legality")
        status_raw = p.get("status", "GRAY")
        score = p.get("score")

        reason_codes = [rc for rc in (p.get("reason_codes") or []) if isinstance(rc, str)]
        evidence_todo = [e for e in (p.get("evidence_todo") or []) if isinstance(e, str) and e.strip()]
        strength_rationale = p.get("strength_rationale")

        # Normalize status
        status_enum = status_raw if status_raw in STATUS_TO_SCORE or status_raw == "GRAY" else "GRAY"

        # Evidence gate: GREEN with evidence -> downgrade
        if status_enum == "GREEN" and evidence_todo:
            status_enum = "YELLOW"
            score = None  # will snap later

        # Reason code gate: GREEN with negative reason codes -> downgrade
        if status_enum == "GREEN" and any(rc in NEGATIVE_REASON_CODES for rc in reason_codes):
            status_enum = "YELLOW"
            score = None  # will snap later

        # Strength gate for GREEN
        if status_enum == "GREEN":
            has_strength = any(rc in STRENGTH_REASON_CODES for rc in reason_codes)
            has_rationale = isinstance(strength_rationale, str) and strength_rationale.strip()
            if not (has_strength or has_rationale):
                status_enum = "YELLOW"
                score = None

        # Canonicalize evidence BEFORE checking GRAY fallback
        evidence_todo = _canonicalize_evidence(pillar_name, reason_codes, evidence_todo)

        # If YELLOW/RED but no reason codes AND no evidence → GRAY
        if status_enum in ("YELLOW", "RED") and not reason_codes and not evidence_todo:
            status_enum = "GRAY"
            score = None

        # Snap score to band midpoint if missing
        if score is None:
            band = STATUS_TO_SCORE.get(status_enum)
            score = None if band is None else (band[0] + band[1]) // 2

        if score is not None and status_enum in STATUS_TO_SCORE and STATUS_TO_SCORE[status_enum]:
            lo, hi = STATUS_TO_SCORE[status_enum]
            score = max(lo, min(hi, int(score)))

        # Keep rationale only for final GREEN with non-empty text
        if not (status_enum == "GREEN" and isinstance(strength_rationale, str) and strength_rationale.strip()):
            strength_rationale = None

        validated.append({
            "pillar": pillar_name,
            "status": status_enum,
            "score": score,
            "reason_codes": reason_codes,
            "evidence_todo": evidence_todo,
            **({"strength_rationale": strength_rationale} if strength_rationale else {}),
        })

    validated = enforce_gray_evidence(validated, DEFAULT_EVIDENCE_BY_PILLAR)
    validated = enforce_colored_evidence(validated)

    # Keep pillar order & fill any missing pillars (belt-and-suspenders)
    by_name = {it["pillar"]: it for it in validated}
    ordered = [by_name.get(p, _default_pillar(p)) for p in PILLAR_ORDER]
    return {"pillars": ordered}

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

    def _pillars_label(n: int) -> str:
        return "pillar" if n == 1 else "pillars"

    rows: List[str] = []
    rows.append("# Pillars Assessment")
    rows.append("")
    rows.append("## Summary")
    rows.append(f"- **GREEN**: {status_counts['GREEN']} {_pillars_label(status_counts['GREEN'])}")
    rows.append(f"- **YELLOW**: {status_counts['YELLOW']} {_pillars_label(status_counts['YELLOW'])}")
    rows.append(f"- **RED**: {status_counts['RED']} {_pillars_label(status_counts['RED'])}")
    rows.append(f"- **GRAY**: {status_counts['GRAY']} {_pillars_label(status_counts['GRAY'])}")
    rows.append("")
    rows.append("## Pillar Details")

    for pillar in pillars:
        name = pillar.get("pillar", "Unknown")
        display_name = PILLAR_DISPLAY_NAMES.get(name, name)
        status = pillar.get("status", "GRAY")
        score = pillar.get("score", None)
        reason_codes = pillar.get("reason_codes", []) or []
        evidence = pillar.get("evidence_todo", []) or []
        strength_rationale = pillar.get("strength_rationale")

        rows.append(f"### {display_name}")
        rows.append(f"**Status**: {status} ({score if score is not None else '—'})")

        if status == "GREEN":
            # GREEN pillars should not show evidence; optionally render the rationale if provided.
            if strength_rationale:
                rows.append(f"_Why green:_ {strength_rationale}")
        elif status in ("YELLOW", "RED"):
            if reason_codes:
                rows.append("**Issues:** " + ", ".join(reason_codes))
            if evidence:
                rows.append("**Evidence Needed:**")
                for item in evidence:
                    rows.append(f"- {item}")
        else:  # GRAY (or anything else treated as GRAY)
            if evidence:
                rows.append("**Evidence Needed:**")
                for item in evidence:
                    rows.append(f"- {item}")

        rows.append("")

    markdown = "\n".join(rows)
    return fix_bullet_lists(markdown)


@dataclass
class PillarsAssessment:
    system_prompt: str
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> "PillarsAssessment":
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


if __name__ == "__main__":  # pragma: no cover
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

    print(f"PILLARS_SYSTEM_PROMPT: {PILLARS_SYSTEM_PROMPT}\n\n")
    result = PillarsAssessment.execute(llm, plan_text)
    print(json.dumps(result.response, indent=2, ensure_ascii=False))
    print("\nMarkdown:\n")
    print(result.markdown)
