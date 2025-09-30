
"""
Blockers (Step 2) — README-compliant + LLM pattern

- Output JSON shape: {"blockers": Blocker[]}
- Single-owner field: "owner" (string).

Usage pattern:
    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)
    blocker_assessment = BlockerAssessment.execute(llm, query)

When run as a script:
- Reads big concatenated input from PLANEXE_QUERY or stdin (no CLI args).
- Prints strict JSON only.

PROMPT> python -u -m planexe.viability.blockers7 | tee output7.txt
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from math import ceil
from typing import Optional, List, Dict, Any, Iterable, Literal
from pydantic import BaseModel, Field, field_validator
from llama_index.core.llms.llm import LLM
from llama_index.core.llms import ChatMessage, MessageRole

# -----------------------------
# Schema (Pydantic) — minimal by README
# -----------------------------
PILLAR_ENUM = ["HumanStability", "EconomicResilience", "EcologicalIntegrity", "Rights_Legality"]

class Blocker(BaseModel):
    id: str = Field(description="Short stable ID like 'B1', 'B2'. If absent in input, generate deterministically from the title.")
    title: str = Field(description="Concise, actionable title for the blocker.")
    pillar: Optional[str] = Field(default=None, description="One of: " + ", ".join(PILLAR_ENUM))
    reason_codes: Optional[List[str]] = Field(default_factory=list, description="Short reason codes tying back to Step 1.")
    acceptance_tests: Optional[List[str]] = Field(default_factory=list, description="Binary/threshold tests that prove the blocker is cleared.")
    artifacts_required: Optional[List[str]] = Field(default_factory=list, description="Named artifacts required to pass the tests.")
    owner: Optional[str] = Field(default=None, description="Single accountable owner (role or person).")

    @field_validator("pillar")
    @classmethod
    def validate_pillar(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # tolerate minor variations and normalize
        key = re.sub(r"[\s/_&-]+", "_", v.strip().lower())
        mapping = {
            "humanstability": "HumanStability",
            "human_stability": "HumanStability",
            "economicresilience": "EconomicResilience",
            "economic_resilience": "EconomicResilience",
            "ecologicalintegrity": "EcologicalIntegrity",
            "ecological_integrity": "EcologicalIntegrity",
            "rights_legality": "Rights_Legality",
            "rights_and_legality": "Rights_Legality",
            "rights_&_legality": "Rights_Legality",
            "rights": "Rights_Legality",
            "legality": "Rights_Legality",
        }
        return mapping.get(key, v)

class BlockersOutput(BaseModel):
    blockers: List[Blocker] = Field(description="Up to 5 blockers. If none, an empty list.")


# -----------------------------
# Prompt
# -----------------------------
BLOCKERS_SYSTEM_PROMPT = """
You are the Step-2 engine (Emit Blockers) of the ViabilityAssessor protocol.
Given a messy concatenation of documents (markdown + snippets of JSON), extract and emit up to 5 crisp, testable blockers.

Rules (MUST follow):
- Output must match this JSON schema exactly: {"blockers": Blocker[]}. No extra keys.
- Do NOT include top-level "source_pillars".
- Do NOT include any "rom" fields.
- Prefer binary/threshold acceptance tests (approve/threshold/met).
- If tests are weak (e.g., "plan in place"), replace with artifact-anchored checks.
- Use single "owner" string (no owners[]).

Allowed pillars: HumanStability | EconomicResilience | EcologicalIntegrity | Rights_Legality.

Only output JSON. No markdown, no commentary.
""".strip()


# -----------------------------
# Cleaner — post-LLM hardening (defensive)
# -----------------------------
WEAK_TEST_FRAGMENTS = [
    "plan in place", "improved satisfaction", "stakeholders aligned",
    "documentation updated", "process defined", "communication sent",
    "approved by management",
]

def _dedupe(items: Iterable[str]) -> List[str]:
    out, seen = [], set()
    for x in items or []:
        x = re.sub(r"\s+", " ", str(x)).strip()
        if not x:
            continue
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out

def _normalize_artifacts(artifacts: List[str]) -> List[str]:
    cleaned = []
    for a in artifacts or []:
        a = re.sub(r"\s+", " ", str(a)).strip()
        if not a:
            continue
        a = re.sub(r"\.(pdf|docx?|xlsx?|csv|pptx?)$", "", a, flags=re.I)
        a = re.sub(r"\b(plan|policy|register|budget|assessment|analysis|report)\b", lambda m: m.group(0).title(), a, flags=re.I)
        cleaned.append(a)
    return _dedupe(cleaned)

def _normalize_tests(tests: List[str], artifacts: List[str], owner: Optional[str]) -> List[str]:
    out: List[str] = []
    for t in tests or []:
        t = re.sub(r"\s+", " ", str(t)).strip().rstrip(".")
        if not t:
            continue
        for pm in re.findall(r"(\d+(?:\.\d+)?)\s*%", t):
            try:
                if float(pm) > 100:
                    t = t.replace(pm, "100")
            except Exception:
                pass
        if not any(p in t.lower() for p in WEAK_TEST_FRAGMENTS):
            out.append(t)
    if not out:
        approver = owner or "Designated approver"
        for a in artifacts[:3] or []:
            out.append(f"Artifact '{a}' approved by {approver}")
    if not out:
        out = ["Mitigation accepted by designated owner with signed record"]
    return _dedupe(out)

def _harden_blockers(data: Dict[str, Any]) -> Dict[str, Any]:
    """Drop disallowed fields and strengthen content."""
    blockers = data.get("blockers") or []
    sanitized: List[Dict[str, Any]] = []
    for i, b in enumerate(blockers, 1):
        nb: Dict[str, Any] = {
            "id": str(b.get("id") or f"B{i}"),
            "title": re.sub(r"\s+", " ", str(b.get("title") or f"Blocker {i}")).strip().rstrip("."),
        }
        # pillar optional
        p = b.get("pillar")
        if p:
            key = re.sub(r"[\s/_&-]+", "_", str(p).strip().lower())
            mapping = {
                "humanstability": "HumanStability",
                "human_stability": "HumanStability",
                "economicresilience": "EconomicResilience",
                "economic_resilience": "EconomicResilience",
                "ecologicalintegrity": "EcologicalIntegrity",
                "ecological_integrity": "EcologicalIntegrity",
                "rights_legality": "Rights_Legality",
                "rights_and_legality": "Rights_Legality",
                "rights_&_legality": "Rights_Legality",
                "rights": "Rights_Legality",
                "legality": "Rights_Legality",
            }
            nb["pillar"] = mapping.get(key, b.get("pillar"))
        # optional fields
        owner = b.get("owner")
        if not owner and b.get("owners"):
            owners = [str(x).strip() for x in (b.get("owners") or []) if str(x).strip()]
            owner = owners[0] if owners else None
        if owner:
            nb["owner"] = re.sub(r"\s+", " ", str(owner)).strip()

        arts = b.get("artifacts_required") or b.get("artifacts") or []
        nb["artifacts_required"] = _normalize_artifacts([str(x) for x in arts])

        tests = b.get("acceptance_tests") or b.get("tests") or []
        nb["acceptance_tests"] = _normalize_tests([str(x) for x in tests], nb["artifacts_required"], nb.get("owner"))

        rc = b.get("reason_codes") or []
        nb["reason_codes"] = _dedupe([str(x) for x in rc])

        # Explicitly drop any 'rom' or unknown keys by omission
        sanitized.append(nb)

    # Dedupe by (pillar,title)
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for b in sanitized:
        key = ((b.get("pillar") or "").lower(), b["title"].lower())
        if key not in seen:
            seen.add(key)
            deduped.append(b)

    return {"blockers": deduped[:5]}


# -----------------------------
# BlockerAssessment — public API matching your pattern
# -----------------------------
class BlockerAssessment:
    system_prompt: str
    user_prompt: str
    response: Dict[str, Any]
    markdown: str
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'BlockerAssessment':
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        system_prompt = BLOCKERS_SYSTEM_PROMPT
        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        sllm = llm.as_structured_llm(BlockersOutput)
        start_time = time.perf_counter()
        chat_response = sllm.chat(chat_message_list)
        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_bytes = len(chat_response.message.content.encode("utf-8"))

        # Raw pydantic -> dict
        raw = chat_response.raw.model_dump()

        # Defensive hardening/sanitization
        hardened = _harden_blockers(raw)

        # Validate against schema again
        validated = BlockersOutput(**hardened).model_dump()

        # Markdown (optional): no source_pillars section
        markdown = cls.convert_to_markdown(BlockersOutput(**validated))

        meta = dict(llm.metadata)
        meta["llm_classname"] = llm.class_name()
        meta["duration"] = duration
        meta["response_byte_count"] = response_bytes

        inst = cls.__new__(cls)
        inst.system_prompt = system_prompt
        inst.user_prompt = user_prompt
        inst.response = validated
        inst.markdown = markdown
        inst.metadata = meta
        return inst

    @staticmethod
    def convert_to_markdown(out: BlockersOutput) -> str:
        rows = ["## Blockers"]
        for blk in out.blockers:
            rows.append(f"### {blk.id}: {blk.title}")
            if blk.pillar:
                rows.append(f"**Pillar:** {blk.pillar}")
            if blk.owner:
                rows.append(f"**Owner:** {blk.owner}")
            if blk.reason_codes:
                rows.append(f"**Reason Codes:** {', '.join(blk.reason_codes)}")
            if blk.artifacts_required:
                rows.append("**Artifacts Required:**")
                for a in blk.artifacts_required:
                    rows.append(f"- {a}")
            if blk.acceptance_tests:
                rows.append("**Acceptance Tests:**")
                for t in blk.acceptance_tests:
                    rows.append(f"- {t}")
            rows.append("")
        return "\n".join(rows)


# -----------------------------
# Script entrypoint: no CLI, JSON-only stdout
# -----------------------------
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
    assessment = BlockerAssessment.execute(llm, query)
    print(json.dumps(assessment.response, ensure_ascii=False, separators=(",", ":")))
