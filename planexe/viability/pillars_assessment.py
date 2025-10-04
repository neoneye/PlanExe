"""
Pillars assessment

Auto-repair that enforces status/score bands, evidence gating, and reason-code whitelists.

IDEA: Scoring transparency. The "score" is currently untrustworthy. I want to change from the range 0-100 to multiple parameters in the range 1-5, so that the score can be fact checked.

IDEA: Extract the REASON_CODES_BY_PILLAR, DEFAULT_EVIDENCE_BY_PILLAR, EVIDENCE_TEMPLATES into a JSON file.

PROMPT> python -u -m planexe.viability.pillars_assessment | tee output.txt
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from math import ceil, floor
from typing import Any, Dict, List, Optional, Tuple

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field

from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists
from planexe.viability.pillars_prompt import make_pillars_system_prompt
from planexe.viability.model_pillar import PillarEnum
from planexe.viability.model_status import StatusEnum

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & enums
# ---------------------------------------------------------------------------

PILLAR_ORDER: List[str] = PillarEnum.value_list()

# This list is not exhaustive, more items are likely to be added over time.
REASON_CODES_BY_PILLAR: Dict[str, List[str]] = {
    PillarEnum.HumanStability.value: [
        "TALENT_UNKNOWN",
        "STAFF_AVERSION",
        "GOVERNANCE_WEAK",
        "CHANGE_MGMT_GAPS",
        "TRAINING_GAPS",
        "STAKEHOLDER_CONFLICT",
        "SAFETY_CULTURE_WEAK",
    ],
    PillarEnum.EconomicResilience.value: [
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
    PillarEnum.EcologicalIntegrity.value: [
        "CLOUD_CARBON_UNKNOWN",
        "CLIMATE_UNQUANTIFIED",
        "WATER_STRESS",
        "EIA_MISSING",
        "BIODIVERSITY_RISK_UNSET",
        "WASTE_MANAGEMENT_GAPS",
        "WATER_PERMIT_RISK",
    ],
    PillarEnum.Rights_Legality.value: [
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
    PillarEnum.HumanStability.value: [
        "Stakeholder map + skills gap snapshot",
        "Change plan v1 (communications, training, adoption KPIs)",
    ],
    PillarEnum.EconomicResilience.value: [
        "Assumption ledger v1 + sensitivity table",
        "Cost model v2 (on-prem vs cloud TCO)",
    ],
    PillarEnum.EcologicalIntegrity.value: [
        "Environmental baseline note (scope, metrics)",
        "Cloud carbon estimate v1 (regions/services)",
    ],
    PillarEnum.Rights_Legality.value: [
        "Regulatory mapping v1 + open questions list",
        "Licenses & permits inventory + gaps list",
    ],
}

LIKERT_MIN = 1
LIKERT_MAX = 5
LIKERT_FACTOR_KEYS: Tuple[str, ...] = ("evidence", "risk", "fit")

DEFAULT_LIKERT_BY_STATUS: Dict[str, Dict[str, Optional[int]]] = {
    StatusEnum.GREEN.value: {key: 4 for key in LIKERT_FACTOR_KEYS},
    StatusEnum.YELLOW.value: {key: 3 for key in LIKERT_FACTOR_KEYS},
    StatusEnum.RED.value: {key: 2 for key in LIKERT_FACTOR_KEYS},
    StatusEnum.GRAY.value: {key: None for key in LIKERT_FACTOR_KEYS},
}

DEFAULT_EVIDENCE_ITEM = "Gather evidence for assessment"

# --- strength codes allowed for GREEN status and canonical evidence templates ---
STRENGTH_REASON_CODES = {
    # Use positive signals that justify GREEN
    "HITL_GOVERNANCE_OK",
}

# Canonical evidence templates per reason code (artifact-first, not actions)
# EVIDENCE_TEMPLATES
# Dict[str, List[str]] mapping a reason code -> ordered list of evidence templates.
# We intentionally use List[str] even when there is only one template for a key.
# Rationale:
#  - Future-proof: adding a second/third template needs no migration or refactor.
#  - Ordering encodes priority: first item is the most canonical form.
# Invariants:
#  - Values are lists of unique, non-empty strings (singleton lists are OK).
#  - Missing keys must be treated by consumers as an empty list, not an error.
# This dict with templates is not exhaustive, more items are likely to be added over time.
# Note: downstream code may dedupe/cap at read time, but the source remains a list.
EVIDENCE_TEMPLATES: Dict[str, List[str]] = {
    # Example:
    # "reason_code": ["template 1", "template 2 (optional)"],
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


def _empty_likert_score() -> Dict[str, Optional[int]]:
    return {key: None for key in LIKERT_FACTOR_KEYS}


def _clamp_factor(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)):
        candidate = int(floor(value))
        if LIKERT_MIN <= candidate <= LIKERT_MAX:
            return candidate
    return None


def _normalize_likert_score(raw_score: Any) -> Dict[str, Optional[int]]:
    normalized = _empty_likert_score()

    if isinstance(raw_score, dict):
        for key in LIKERT_FACTOR_KEYS:
            normalized[key] = _clamp_factor(raw_score.get(key))
    elif isinstance(raw_score, (list, tuple)):
        for key, value in zip(LIKERT_FACTOR_KEYS, raw_score):
            normalized[key] = _clamp_factor(value)
    elif isinstance(raw_score, (int, float)):
        # Legacy 0-100 score fallback → map to Likert (1-5)
        scaled = ((float(raw_score) / 100.0) * (LIKERT_MAX - LIKERT_MIN)) + LIKERT_MIN
        fallback_value = _clamp_factor(scaled)
        if fallback_value is not None:
            return {key: fallback_value for key in LIKERT_FACTOR_KEYS}

    return normalized


def _fallback_factors_for_status(status: str) -> Dict[str, Optional[int]]:
    template = DEFAULT_LIKERT_BY_STATUS.get(status, DEFAULT_LIKERT_BY_STATUS[StatusEnum.GRAY.value])
    return dict(template)


def _derive_status_from_factors(factors: Dict[str, Optional[int]]) -> str:
    values = [val for val in factors.values() if isinstance(val, int)]
    if len(values) < len(LIKERT_FACTOR_KEYS):
        return StatusEnum.GRAY.value

    floor = min(values)
    if floor <= 2:
        return StatusEnum.RED.value
    if floor == 3:
        return StatusEnum.YELLOW.value
    return StatusEnum.GREEN.value


def _enforce_status(factors: Dict[str, Optional[int]], status: str) -> Dict[str, Optional[int]]:
    if status == StatusEnum.GRAY.value:
        return _empty_likert_score()

    template = _fallback_factors_for_status(status)

    if status == StatusEnum.YELLOW.value:
        # Ensure at least one factor is exactly 3, but do not override worse data.
        enforced = {}
        first_set = False
        for key in LIKERT_FACTOR_KEYS:
            current = factors.get(key)
            if isinstance(current, int) and current <= 2:
                enforced[key] = current
                continue
            if not first_set:
                enforced[key] = 3
                first_set = True
            else:
                enforced[key] = max(3, min(5, current)) if isinstance(current, int) else 3
        return enforced

    if status == StatusEnum.RED.value:
        # Keep the lowest value ≤2 if present; otherwise fall back to 2.
        enforced = {}
        for key in LIKERT_FACTOR_KEYS:
            current = factors.get(key)
            if isinstance(current, int) and current <= 2:
                enforced[key] = max(LIKERT_MIN, current)
            else:
                enforced[key] = LIKERT_MIN + 1  # 2
        return enforced

    # Default (GREEN): keep ≥4 and clamp into 4–5 range.
    enforced = {}
    for key in LIKERT_FACTOR_KEYS:
        current = factors.get(key)
        if isinstance(current, int) and current >= 4:
            enforced[key] = min(LIKERT_MAX, current)
        else:
            enforced[key] = 4
    return enforced


def _compute_derived_metrics(factors: Dict[str, Optional[int]]) -> Dict[str, Any]:
    values = [val for val in factors.values() if isinstance(val, int)]
    average_likert: Optional[float] = None
    legacy_0_100: Optional[int] = None

    if len(values) == len(LIKERT_FACTOR_KEYS):
        average_raw = sum(values) / float(len(values))
        average_likert = round(average_raw, 2)
        legacy_raw = int(round((average_raw - LIKERT_MIN) / (LIKERT_MAX - LIKERT_MIN) * 100))
        legacy_0_100 = max(0, min(100, legacy_raw))

    enriched: Dict[str, Any] = {key: factors.get(key) for key in LIKERT_FACTOR_KEYS}
    enriched["average_likert"] = average_likert
    enriched["legacy_0_100"] = legacy_0_100
    return enriched

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

class PillarLikertScoreSchema(BaseModel):
    evidence: Optional[int] = Field(default=None, ge=LIKERT_MIN, le=LIKERT_MAX)
    risk: Optional[int] = Field(default=None, ge=LIKERT_MIN, le=LIKERT_MAX)
    fit: Optional[int] = Field(default=None, ge=LIKERT_MIN, le=LIKERT_MAX)
    average_likert: Optional[float] = Field(default=None)
    legacy_0_100: Optional[int] = Field(default=None)

    class Config:
        extra = "ignore"


class PillarItemSchema(BaseModel):
    pillar: str = Field(..., description="Pillar name from PillarEnum")
    status: str = Field(..., description="Status indicator")
    score: Optional[PillarLikertScoreSchema] = Field(
        None,
        description="Per-factor Likert scores (1-5) with derived averages",
    )
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

PILLARS_SYSTEM_PROMPT = make_pillars_system_prompt(
    PILLAR_ORDER,
    REASON_CODES_BY_PILLAR,
    DEFAULT_LIKERT_BY_STATUS,
    DEFAULT_EVIDENCE_BY_PILLAR,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _default_pillar(pillar: str) -> Dict[str, Any]:
    return {
        "pillar": pillar,
        "status": StatusEnum.GRAY.value,
        "score": _compute_derived_metrics(_empty_likert_score()),
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
        if it.get("status") == StatusEnum.GRAY.value:
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
        if status in {StatusEnum.YELLOW.value, StatusEnum.RED.value}:
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

    valid_statuses = {status.value for status in StatusEnum}

    for p in pillars:
        pillar_name = p.get("pillar", "Rights_Legality")
        status_raw = p.get("status", StatusEnum.GRAY.value)
        status_enum = status_raw if status_raw in valid_statuses else StatusEnum.GRAY.value

        score_raw = p.get("score")
        factors = _normalize_likert_score(score_raw)
        if all(factors[key] is None for key in LIKERT_FACTOR_KEYS):
            factors = _fallback_factors_for_status(status_enum)

        reason_codes = [rc for rc in (p.get("reason_codes") or []) if isinstance(rc, str)]
        evidence_todo = [e for e in (p.get("evidence_todo") or []) if isinstance(e, str) and e.strip()]
        strength_rationale = p.get("strength_rationale")

        # Canonicalize evidence BEFORE applying status rules
        evidence_todo = _canonicalize_evidence(pillar_name, reason_codes, evidence_todo)

        status_from_factors = _derive_status_from_factors(factors)
        if status_from_factors != StatusEnum.GRAY.value:
            status_enum = status_from_factors

        # Evidence gate: GREEN with evidence → downgrade to YELLOW
        if status_enum == StatusEnum.GREEN.value and evidence_todo:
            status_enum = StatusEnum.YELLOW.value
            factors = _enforce_status(factors, status_enum)

        # Reason code gate: GREEN with negative reason codes → downgrade to YELLOW
        if status_enum == StatusEnum.GREEN.value and any(rc in NEGATIVE_REASON_CODES for rc in reason_codes):
            status_enum = StatusEnum.YELLOW.value
            factors = _enforce_status(factors, status_enum)

        # Strength gate for GREEN
        if status_enum == StatusEnum.GREEN.value:
            has_strength = any(rc in STRENGTH_REASON_CODES for rc in reason_codes)
            has_rationale = isinstance(strength_rationale, str) and strength_rationale.strip()
            if not (has_strength or has_rationale):
                status_enum = StatusEnum.YELLOW.value
                factors = _enforce_status(factors, status_enum)

        # If YELLOW/RED but no reason codes AND no evidence → GRAY
        if status_enum in (StatusEnum.YELLOW.value, StatusEnum.RED.value) and not reason_codes and not evidence_todo:
            status_enum = StatusEnum.GRAY.value
            factors = _enforce_status(factors, status_enum)

        # Ensure factor defaults align with final status
        if status_enum != StatusEnum.GRAY.value:
            fallback = _fallback_factors_for_status(status_enum)
            for key in LIKERT_FACTOR_KEYS:
                if factors.get(key) is None:
                    factors[key] = fallback[key]
            status_enum = _derive_status_from_factors(factors)
            # If factors still insufficient, reset to status defaults
            if status_enum == StatusEnum.GRAY.value:
                factors = _enforce_status({}, StatusEnum.GRAY.value)
                status_enum = StatusEnum.GRAY.value
        else:
            factors = _enforce_status({}, StatusEnum.GRAY.value)
            status_enum = StatusEnum.GRAY.value

        score = _compute_derived_metrics(factors)

        # Keep rationale only for final GREEN with non-empty text
        if not (status_enum == StatusEnum.GREEN.value and isinstance(strength_rationale, str) and strength_rationale.strip()):
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
    status_counts = {status.value: 0 for status in StatusEnum}
    for pillar in pillars:
        status = pillar.get("status", StatusEnum.GRAY.value)
        if status in status_counts:
            status_counts[status] += 1

    def _pillars_label(n: int) -> str:
        return "pillar" if n == 1 else "pillars"

    rows: List[str] = []
    rows.append("## Summary")
    rows.append(f"- **GREEN**: {status_counts['GREEN']} {_pillars_label(status_counts['GREEN'])}")
    rows.append(f"- **YELLOW**: {status_counts['YELLOW']} {_pillars_label(status_counts['YELLOW'])}")
    rows.append(f"- **RED**: {status_counts['RED']} {_pillars_label(status_counts['RED'])}")
    rows.append(f"- **GRAY**: {status_counts['GRAY']} {_pillars_label(status_counts['GRAY'])}")
    rows.append("")
    rows.append("## Pillar Details")

    for pillar in pillars:
        name = pillar.get("pillar", "Unknown")
        display_name = PillarEnum.get_display_name(name)
        status = pillar.get("status", StatusEnum.GRAY.value)
        score = pillar.get("score") or {}
        reason_codes = pillar.get("reason_codes", []) or []
        evidence = pillar.get("evidence_todo", []) or []
        strength_rationale = pillar.get("strength_rationale")

        rows.append(f"### {display_name}\n")
        def _fmt_factor(val: Any) -> str:
            if isinstance(val, (int, float)):
                if isinstance(val, float):
                    return f"{val:.2f}".rstrip("0").rstrip(".")
                return str(val)
            return "—"

        factor_parts = [f"{key}={_fmt_factor(score.get(key))}" for key in LIKERT_FACTOR_KEYS]

        avg_val = score.get("average_likert")
        avg_part = None
        if isinstance(avg_val, (int, float)):
            avg_fmt = f"{avg_val:.2f}".rstrip("0").rstrip(".")
            avg_part = f"avg={avg_fmt}"

        legacy_val = score.get("legacy_0_100")
        legacy_part = None
        if isinstance(legacy_val, (int, float)):
            legacy_part = f"legacy={int(legacy_val)}"

        metrics = ", ".join(part for part in factor_parts + [avg_part, legacy_part] if part)
        rows.append(f"**Status**: {status} ({metrics if metrics else '—'})\n")

        if status == StatusEnum.GREEN.value:
            # GREEN pillars should not show evidence; optionally render the rationale if provided.
            if strength_rationale:
                rows.append(f"_Why green:_ {strength_rationale}\n")
        elif status in (StatusEnum.YELLOW.value, StatusEnum.RED.value):
            if reason_codes:
                rows.append("**Issues:** " + ", ".join(reason_codes) + "\n")
            if evidence:
                rows.append("**Evidence Needed:**\n")
                for item in evidence:
                    rows.append(f"- {item}")
                rows.append("")
        else:  # GRAY (or anything else treated as GRAY)
            if evidence:
                rows.append("**Evidence Needed:**\n")
                for item in evidence:
                    rows.append(f"- {item}")
                rows.append("")

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

        sllm = llm.as_structured_llm(PillarsSchema)
        chat_response = sllm.chat(messages)
        used_structured = True
        raw_payload = chat_response.raw.model_dump()
        raw_text = chat_response.message.content or json.dumps(raw_payload)

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
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(self.markdown)


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
