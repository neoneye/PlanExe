"""
Domains assessment

Auto-repair that enforces status/score bands, evidence gating, and reason-code whitelists.

PROMPT> python -u -m planexe.viability.domains_assessment | tee output.txt
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from math import ceil, floor
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field

from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists
from planexe.viability.domains_prompt import make_domains_system_prompt
from planexe.viability.model_domain import DomainEnum
from planexe.viability.model_status import StatusEnum

from planexe.viability.taxonomy import (
    DOMAIN_ORDER,
    REASON_CODES_BY_DOMAIN,
    DEFAULT_EVIDENCE_BY_DOMAIN,
    EVIDENCE_TEMPLATES,
    STRENGTH_REASON_CODES,
    FALLBACK_REASON_CODE_BY_DOMAIN_AND_FACTOR,
    EVIDENCE_ACCEPTANCE_CRITERIA,
    LIKERT_MIN, LIKERT_MAX, LIKERT_FACTOR_KEYS,
    DEFAULT_LIKERT_BY_STATUS, FACTOR_ORDER_INDEX,
    reason_code_factor_set,
)

logger = logging.getLogger(__name__)


def _translate_reason_code_to_human_readable(reason_code: str) -> str:
    """
    Translate a reason code to human-readable text using evidence templates.
    
    Args:
        reason_code: The reason code (e.g., 'CHANGE_MGMT_GAPS')
        
    Returns:
        Human-readable description from evidence templates, or the original code if not found
    """
    if reason_code in EVIDENCE_TEMPLATES:
        # Get the first (most canonical) template for this reason code
        templates = EVIDENCE_TEMPLATES[reason_code]
        if templates and len(templates) > 0:
            return templates[0]
    
    # Fallback to the original reason code if no template found
    return reason_code

# ---------------------------------------------------------------------------
# Constants & enums
# ---------------------------------------------------------------------------

NEGATIVE_REASON_CODES: List[str] = sorted(
    {code for codes in REASON_CODES_BY_DOMAIN.values() for code in codes}
)

DEFAULT_EVIDENCE_ITEM = "Gather evidence for assessment"

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

    return normalized


def _fallback_factors_for_status(status: str) -> Dict[str, Optional[int]]:
    template = DEFAULT_LIKERT_BY_STATUS.get(status, DEFAULT_LIKERT_BY_STATUS[StatusEnum.GRAY.value])
    return dict(template)


def _derive_status_from_factors(factors: Dict[str, Optional[int]]) -> str:
    coerced: Dict[str, Optional[int]] = {}
    for key in LIKERT_FACTOR_KEYS:
        value = factors.get(key)
        coerced[key] = value if isinstance(value, int) else None

    if any(coerced[key] is None for key in LIKERT_FACTOR_KEYS):
        return StatusEnum.GRAY.value

    evidence = coerced["evidence"]
    risk = coerced["risk"]
    fit = coerced["fit"]

    if risk <= 2:
        return StatusEnum.RED.value
    if evidence <= 2 and fit <= 2:
        return StatusEnum.RED.value
    if evidence <= 2 or fit <= 2:
        return StatusEnum.YELLOW.value
    return StatusEnum.GREEN.value


def _enforce_status(factors: Dict[str, Optional[int]], status: str) -> Dict[str, Optional[int]]:
    if status == StatusEnum.GRAY.value:
        return _empty_likert_score()

    factors = factors or {}
    sanitized: Dict[str, Optional[int]] = {}
    for key in LIKERT_FACTOR_KEYS:
        sanitized[key] = _clamp_factor(factors.get(key))

    if status == StatusEnum.RED.value:
        original_risk = sanitized["risk"]
        evidence_val = sanitized["evidence"]
        fit_val = sanitized["fit"]
        double_gap = (
            isinstance(evidence_val, int)
            and evidence_val <= 2
            and isinstance(fit_val, int)
            and fit_val <= 2
            and (original_risk is None or original_risk > 2)
        )

        if original_risk is None:
            sanitized["risk"] = 3 if double_gap else 2
        elif original_risk > 2 and not double_gap:
            sanitized["risk"] = 2

        for key in ("evidence", "fit"):
            current = sanitized[key]
            if current is None:
                sanitized[key] = 2 if double_gap else 3
        return sanitized

    if status == StatusEnum.YELLOW.value:
        if sanitized["risk"] is None or sanitized["risk"] <= 2:
            sanitized["risk"] = 3

        gap_keys = ("evidence", "fit")
        has_gap = any(
            sanitized[key] is not None and sanitized[key] <= 2 for key in gap_keys
        )
        if not has_gap:
            sanitized["evidence"] = 2

        for key in gap_keys:
            if sanitized[key] is None:
                sanitized[key] = 2 if key == "evidence" else 3

        if not any(sanitized[key] <= 2 for key in gap_keys):
            sanitized["evidence"] = 2
        return sanitized

    if status == StatusEnum.GREEN.value:
        for key in LIKERT_FACTOR_KEYS:
            value = sanitized.get(key)
            if value is None or value < 4:
                sanitized[key] = 4
        return sanitized

    return dict(_fallback_factors_for_status(status))


def _compute_derived_metrics(factors: Dict[str, Optional[int]]) -> Dict[str, Any]:
    return {key: factors.get(key) for key in LIKERT_FACTOR_KEYS}


def _attach_acceptance_criteria(item: str) -> str:
    text = item.strip()
    if not text:
        return text
    if "acceptance criteria:" in text.lower():
        return text
    criteria = EVIDENCE_ACCEPTANCE_CRITERIA.get(
        text,
        "artifact is published to the workspace with an owner, acceptance evidence, and review date recorded.",
    )
    return f"{text} — acceptance criteria: {criteria}"


def _apply_acceptance_criteria(items: List[str]) -> List[str]:
    return [_attach_acceptance_criteria(item) for item in items if isinstance(item, str) and item.strip()]


def _base_evidence_name(text: str) -> str:
    if not isinstance(text, str):
        return ""
    base = text.split(" — acceptance criteria:")[0]
    return base.strip()


def _canonicalize_evidence(domain: str, reason_codes: List[str], evidence_todo: List[str]) -> List[str]:
    """
    Replace action-y items with artifact names and fill from templates.
    Cap at 2 items to keep Step-1 tight.
    """
    out: List[str] = []
    base_seen: Set[str] = set()
    # Auto-rewrite common vague lines
    rewrites = {
        "recruit additional engineers": None,  # drop from step-1; becomes a blocker if needed
        "offset": None,  # offsets are not evidence; baseline first
        "carbon offset": None,
        "research carbon offset": None,
    }
    for item in evidence_todo or []:
        if not isinstance(item, str):
            continue
        lower = item.lower()
        if any(k in lower for k in rewrites.keys()):
            continue
        trimmed = item.strip()
        base = _base_evidence_name(trimmed)
        if not base or base in base_seen:
            continue
        base_seen.add(base)
        out.append(trimmed)
    # Add canonical artifacts per reason code
    for rc in reason_codes:
        for tmpl in EVIDENCE_TEMPLATES.get(rc, []):
            base = _base_evidence_name(tmpl)
            if not base or base in base_seen:
                continue
            base_seen.add(base)
            out.append(tmpl)
    # Cap to 2 items
    return _apply_acceptance_criteria(out[:2])

# ---------------------------------------------------------------------------
# Lightweight schema for structured output
# ---------------------------------------------------------------------------

class DomainLikertScoreSchema(BaseModel):
    evidence: Optional[int] = Field(default=None, ge=LIKERT_MIN, le=LIKERT_MAX)
    risk: Optional[int] = Field(default=None, ge=LIKERT_MIN, le=LIKERT_MAX)
    fit: Optional[int] = Field(default=None, ge=LIKERT_MIN, le=LIKERT_MAX)

    class Config:
        extra = "ignore"


class DomainItemSchema(BaseModel):
    domain: str = Field(..., description="Domain name from DomainEnum")
    status: str = Field(..., description="Status indicator")
    score: Optional[DomainLikertScoreSchema] = Field(
        None,
        description="Per-factor Likert scores (1-5)",
    )
    reason_codes: Optional[List[str]] = Field(default=None)
    evidence_todo: Optional[List[str]] = Field(default=None)
    strength_rationale: Optional[str] = Field(default=None, description="Short rationale for why status is GREEN; omit otherwise")


    class Config:
        extra = "ignore"


class DomainsSchema(BaseModel):
    domains: List[DomainItemSchema] = Field(default_factory=list)

    class Config:
        extra = "ignore"


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

DOMAINS_SYSTEM_PROMPT = make_domains_system_prompt()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _default_domain(domain: str) -> Dict[str, Any]:
    return {
        "domain": domain,
        "status": StatusEnum.GRAY.value,
        "score": _compute_derived_metrics(_empty_likert_score()),
        "reason_codes": [],
        "evidence_todo": _apply_acceptance_criteria([DEFAULT_EVIDENCE_ITEM]),
    }

def enforce_gray_evidence(
    items: List[Dict[str, Any]],
    defaults: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """
    Ensure every GRAY domain has 1–2 artifact-style evidence items.
    If missing, fill from `defaults[domain]`; if that’s empty/missing, use a generic fallback.
    """
    GENERIC_FALLBACK: List[str] = ["Baseline note v1 (scope, metrics)"]

    for it in items:
        if it.get("status") == StatusEnum.GRAY.value:
            raw_ev = it.get("evidence_todo") or []
            ev: List[str] = [e for e in raw_ev if isinstance(e, str) and e.strip()]
            if not ev:
                domain = str(it.get("domain", ""))
                ev = list(defaults.get(domain, GENERIC_FALLBACK))[:2]
            it["evidence_todo"] = _apply_acceptance_criteria(ev[:2])
    return items

def enforce_colored_evidence(
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Ensure YELLOW/RED domains have at least one artifact-style evidence item.
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
            it["evidence_todo"] = _apply_acceptance_criteria(ev[:2])
    return items


def _reason_codes_support_factor(reason_codes: List[str], factor: str) -> bool:
    return any(
        factor in reason_code_factor_set(code)
        for code in reason_codes
    )


def _fallback_reason_code(domain: str, factor: str) -> Optional[str]:
    return FALLBACK_REASON_CODE_BY_DOMAIN_AND_FACTOR.get(domain, {}).get(factor)


def validate_and_repair(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Make weak-model output deterministic and policy-compliant."""
    data = dict(payload)  # shallow copy
    domains = data.get("domains", [])
    validated: List[Dict[str, Any]] = []

    valid_statuses = {status.value for status in StatusEnum}

    for p in domains:
        domain_name = p.get("domain", "Rights_Legality")
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
        evidence_todo = _canonicalize_evidence(domain_name, reason_codes, evidence_todo)

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

        factor_values_for_priority = {
            key: factors.get(key) if isinstance(factors.get(key), int) else None
            for key in LIKERT_FACTOR_KEYS
        }
        prioritized_factors = _factor_priority(status_enum, factor_values_for_priority)
        decisive_factor = prioritized_factors[0] if prioritized_factors else None

        if status_enum in (StatusEnum.YELLOW.value, StatusEnum.RED.value) and decisive_factor:
            if not _reason_codes_support_factor(reason_codes, decisive_factor):
                fallback_code = _fallback_reason_code(domain_name, decisive_factor)
                if fallback_code and fallback_code not in reason_codes:
                    reason_codes.append(fallback_code)
                evidence_todo = _canonicalize_evidence(domain_name, reason_codes, evidence_todo)

        score = _compute_derived_metrics(factors)

        # Keep rationale only for final GREEN with non-empty text
        if not (status_enum == StatusEnum.GREEN.value and isinstance(strength_rationale, str) and strength_rationale.strip()):
            strength_rationale = None

        validated.append({
            "domain": domain_name,
            "status": status_enum,
            "score": score,
            "reason_codes": reason_codes,
            "evidence_todo": evidence_todo,
            **({"strength_rationale": strength_rationale} if strength_rationale else {}),
        })

    validated = enforce_gray_evidence(validated, DEFAULT_EVIDENCE_BY_DOMAIN)
    validated = enforce_colored_evidence(validated)

    # Keep domain order & fill any missing domains (belt-and-suspenders)
    by_name = {it["domain"]: it for it in validated}
    ordered = [by_name.get(p, _default_domain(p)) for p in DOMAIN_ORDER]
    return {"domains": ordered}

# ---------------------------------------------------------------------------
# Markdown rendering helpers
# ---------------------------------------------------------------------------


def _factor_priority(status: str, factor_values: Dict[str, Optional[int]]) -> List[str]:
    def value_for(key: str) -> int:
        val = factor_values.get(key)
        return val if isinstance(val, int) else LIKERT_MAX + 1

    ordered: List[str]
    if status == StatusEnum.RED.value and value_for("risk") <= 2:
        remaining = [key for key in LIKERT_FACTOR_KEYS if key != "risk"]
        remaining.sort(key=lambda k: (value_for(k), FACTOR_ORDER_INDEX.get(k, 99)))
        ordered = ["risk"] + remaining
    else:
        low = [key for key in LIKERT_FACTOR_KEYS if value_for(key) <= 2]
        low.sort(key=lambda k: (value_for(k), FACTOR_ORDER_INDEX.get(k, 99)))
        high = [key for key in LIKERT_FACTOR_KEYS if key not in low]
        high.sort(key=lambda k: (value_for(k), FACTOR_ORDER_INDEX.get(k, 99)))
        ordered = low + high
    return ordered


def _select_factor_with_reason_support(candidates: List[str], reason_codes: List[str]) -> Optional[str]:
    for factor in candidates:
        if _reason_codes_support_factor(reason_codes, factor):
            return factor
    return None


def _reason_keywords_for_factor(reason_codes: List[str], factor: str, limit: int = 4) -> List[str]:
    keywords: List[str] = []
    for code in reason_codes:
        if factor not in reason_code_factor_set(code):
            continue
        parts = [segment for segment in code.lower().split("_") if segment]
        if not parts:
            continue
        keyword = " ".join(parts[:2])
        if keyword not in keywords:
            keywords.append(keyword)
        if len(keywords) >= limit:
            break
    return keywords


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def convert_to_markdown(data: Dict[str, Any]) -> str:
    domains = data.get("domains", [])
    status_counts = {status.value: 0 for status in StatusEnum}
    for domain in domains:
        status = domain.get("status", StatusEnum.GRAY.value)
        if status in status_counts:
            status_counts[status] += 1

    def _domains_label(n: int) -> str:
        return "domain" if n == 1 else "domains"

    def _format_count_domains(n: int) -> str:
        return f"{n} {_domains_label(n)}"
        
    def _get_legend_markdown() -> str:
        try:
            path = Path(__file__).parent / "domains_assessment_metrics_legend.md"
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("domains_assessment_metrics_legend.md not found. The legend will not be included in the report.")
            return ""

    def _driver_text(status: str, score_dict: Dict[str, Any], reason_codes: List[str]) -> Optional[str]:
        factor_values: Dict[str, Optional[int]] = {
            key: score_dict.get(key) if isinstance(score_dict.get(key), int) else None
            for key in LIKERT_FACTOR_KEYS
        }

        if any(factor_values[key] is None for key in LIKERT_FACTOR_KEYS):
            return None

        candidates = _factor_priority(status, factor_values)
        driver_factor = _select_factor_with_reason_support(candidates, reason_codes)
        if driver_factor is None:
            driver_factor = candidates[0] if candidates else None

        if driver_factor is None:
            return None

        if status == StatusEnum.GREEN.value:
            if all(factor_values[key] is not None and factor_values[key] >= 4 for key in LIKERT_FACTOR_KEYS):
                return "all factors >=4"
            return "balanced evidence, risk, and fit"

        keywords = _reason_keywords_for_factor(reason_codes, driver_factor)
        if keywords:
            keyword_text = ", ".join(keywords[:4])
            return f"{driver_factor} ({keyword_text})"
        return driver_factor

    # Load the "domains_assessment_summary.html" file
    html_file_path = Path(__file__).parent / "domains_assessment_summary.html"
    with open(html_file_path, "r") as f:
        html = f.read()

    # Replace the GREEN_COUNT, YELLOW_COUNT, RED_COUNT, GRAY_COUNT with the status counts
    html = html.replace("GREEN_COUNT", _format_count_domains(status_counts['GREEN']))
    html = html.replace("YELLOW_COUNT", _format_count_domains(status_counts['YELLOW']))
    html = html.replace("RED_COUNT", _format_count_domains(status_counts['RED']))
    html = html.replace("GRAY_COUNT", _format_count_domains(status_counts['GRAY']))

    # Dim the domain cards if the count is 0
    html = html.replace("GREEN_DOMAIN_CSS_CLASS", "domain-card--count-zero" if status_counts['GREEN'] == 0 else "")
    html = html.replace("YELLOW_DOMAIN_CSS_CLASS", "domain-card--count-zero" if status_counts['YELLOW'] == 0 else "")
    html = html.replace("RED_DOMAIN_CSS_CLASS", "domain-card--count-zero" if status_counts['RED'] == 0 else "")
    html = html.replace("GRAY_DOMAIN_CSS_CLASS", "domain-card--count-zero" if status_counts['GRAY'] == 0 else "")

    rows: List[str] = []
    rows.append(html)
    rows.append("\n\n## Domain Details")
    rows.append(_get_legend_markdown())

    for domain in domains:
        name = domain.get("domain", "Unknown")
        display_name = DomainEnum.get_display_name(name)
        status = domain.get("status", StatusEnum.GRAY.value)
        score = domain.get("score") or {}
        reason_codes = domain.get("reason_codes", []) or []
        evidence = domain.get("evidence_todo", []) or []
        strength_rationale = domain.get("strength_rationale")

        rows.append(f"### Domain: {display_name}\n")
        def _fmt_factor(val: Any) -> str:
            if isinstance(val, (int, float)):
                if isinstance(val, float):
                    return f"{val:.2f}".rstrip("0").rstrip(".")
                return str(val)
            return "—"

        metrics_parts = [f"{key}={_fmt_factor(score.get(key))}" for key in LIKERT_FACTOR_KEYS]
        metrics_text = ", ".join(part for part in metrics_parts if part)

        driver_phrase = _driver_text(status, score, reason_codes)
        status_line = f"**Status**: {status}"
        if driver_phrase:
            status_line += f" — driven by {driver_phrase}."
        else:
            status_line += "."
        rows.append(status_line + "\n")

        if metrics_text:
            rows.append(f"**Metrics**: {metrics_text}\n")

        if status == StatusEnum.GREEN.value:
            # GREEN domains should not show evidence; optionally render the rationale if provided.
            if strength_rationale:
                rows.append(f"_Why green:_ {strength_rationale}\n")
        elif status in (StatusEnum.YELLOW.value, StatusEnum.RED.value):
            if reason_codes:
                rows.append("**Issues:**\n")
                for reason_code in reason_codes:
                    human_readable = _translate_reason_code_to_human_readable(reason_code)
                    rows.append(f"- <code>{reason_code}</code>: {human_readable}")
                rows.append("")
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
class DomainsAssessment:
    system_prompt: str
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> "DomainsAssessment":
        if not isinstance(user_prompt, str):
            raise TypeError("user_prompt must be a string")
        if not isinstance(llm, LLM):
            raise TypeError("llm must be an instance of LLM")

        system_prompt = DOMAINS_SYSTEM_PROMPT
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        start_time = time.perf_counter()
        raw_payload: Dict[str, Any] = {}
        raw_text = ""
        used_structured = False

        sllm = llm.as_structured_llm(DomainsSchema)
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

    print(f"DOMAINS_SYSTEM_PROMPT: {DOMAINS_SYSTEM_PROMPT}\n\n")
    result = DomainsAssessment.execute(llm, plan_text)
    print(json.dumps(result.response, indent=2, ensure_ascii=False))
    print("\nMarkdown:\n")
    print(result.markdown)
