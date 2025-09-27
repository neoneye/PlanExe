"""
DO NOT USE, it's broken and doesn't use the PlanExe LLMs correctly.

Step 1: Pillars assessment for the ViabilityAssessor pipeline.

This module queries an LLM for a raw pillars JSON, then *validates and repairs* it:
- Enforces per-pillar reason-code whitelists (prevents cross-pillar leakage).
- Enforces "No GREEN with negatives" (downgrades to YELLOW and snaps score to band midpoint).
- Promotes unjustified YELLOW/RED to GRAY when there are no valid reason codes and no evidence.
- Ensures evidence-gated GREEN (GREEN requires evidence_todo == []).
- Drops any model-provided markdown; renders our own markdown.

It is safe to run on weaker models. If no LLM is available, it falls back to a minimal stub.

PROMPT> python -m planexe.viability.legacy_pillars2
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

# Quiet transformer backend noise (best-effort; harmless if not present)
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# ------------------------------------------------------------------------------
# Enums & Constants
# ------------------------------------------------------------------------------

class PillarEnum(str, Enum):
    HUMAN_STABILITY = "HumanStability"
    ECONOMIC_RESILIENCE = "EconomicResilience"
    ECOLOGICAL_INTEGRITY = "EcologicalIntegrity"
    RIGHTS_LEGALITY = "Rights_Legality"


class ColorEnum(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    GRAY = "GRAY"


class ReasonCodeEnum(str, Enum):
    # Budget/Finance
    CONTINGENCY_LOW = "CONTINGENCY_LOW"
    SINGLE_CUSTOMER = "SINGLE_CUSTOMER"
    ALT_COST_UNKNOWN = "ALT_COST_UNKNOWN"
    LEGACY_IT = "LEGACY_IT"
    INTEGRATION_RISK = "INTEGRATION_RISK"
    # Rights/Compliance
    DPIA_GAPS = "DPIA_GAPS"
    LICENSE_GAPS = "LICENSE_GAPS"
    ABS_UNDEFINED = "ABS_UNDEFINED"
    PERMIT_COMPLEXITY = "PERMIT_COMPLEXITY"
    BIOSECURITY_GAPS = "BIOSECURITY_GAPS"
    # People/Adoption
    TALENT_UNKNOWN = "TALENT_UNKNOWN"
    STAFF_AVERSION = "STAFF_AVERSION"
    # Climate/Ecology
    CLOUD_CARBON_UNKNOWN = "CLOUD_CARBON_UNKNOWN"
    CLIMATE_UNQUANTIFIED = "CLIMATE_UNQUANTIFIED"
    WATER_STRESS = "WATER_STRESS"
    # Governance/Ethics
    ETHICS_VAGUE = "ETHICS_VAGUE"
    # Positive/strength codes (allowed with GREEN only)
    HITL_GOVERNANCE_OK = "HITL_GOVERNANCE_OK"


COLOR_TO_SCORE: Dict[ColorEnum, Optional[Tuple[int, int]]] = {
    ColorEnum.GREEN: (70, 100),
    ColorEnum.YELLOW: (40, 69),
    ColorEnum.RED: (0, 39),
    ColorEnum.GRAY: None,
}


def get_color_band_midpoint(color: ColorEnum) -> Optional[int]:
    band = COLOR_TO_SCORE.get(color)
    if not band:
        return None
    lo, hi = band
    return int((lo + hi) / 2)


# Per-pillar reason-code whitelist (prevents cross-pillar leakage)
REASON_CODES_BY_PILLAR: Dict[PillarEnum, Set[ReasonCodeEnum]] = {
    PillarEnum.HUMAN_STABILITY: {
        ReasonCodeEnum.TALENT_UNKNOWN, ReasonCodeEnum.STAFF_AVERSION
    },
    PillarEnum.ECONOMIC_RESILIENCE: {
        ReasonCodeEnum.CONTINGENCY_LOW, ReasonCodeEnum.SINGLE_CUSTOMER,
        ReasonCodeEnum.ALT_COST_UNKNOWN, ReasonCodeEnum.LEGACY_IT, ReasonCodeEnum.INTEGRATION_RISK
    },
    PillarEnum.ECOLOGICAL_INTEGRITY: {
        ReasonCodeEnum.CLOUD_CARBON_UNKNOWN, ReasonCodeEnum.CLIMATE_UNQUANTIFIED,
        ReasonCodeEnum.WATER_STRESS
    },
    PillarEnum.RIGHTS_LEGALITY: {
        ReasonCodeEnum.DPIA_GAPS, ReasonCodeEnum.LICENSE_GAPS, ReasonCodeEnum.ABS_UNDEFINED,
        ReasonCodeEnum.PERMIT_COMPLEXITY, ReasonCodeEnum.BIOSECURITY_GAPS, ReasonCodeEnum.ETHICS_VAGUE
    },
}

NEGATIVE_REASON_CODES: Set[ReasonCodeEnum] = {
    c for s in REASON_CODES_BY_PILLAR.values() for c in s
}
STRENGTH_REASON_CODES: Set[ReasonCodeEnum] = {ReasonCodeEnum.HITL_GOVERNANCE_OK}

# ------------------------------------------------------------------------------
# LLM plumbing (minimal; uses ollama if available, else stub)
# ------------------------------------------------------------------------------

@dataclass
class LLMResponse:
    text: str
    raw: Any = None
    duration_s: float = 0.0


class LLMClient:
    def __init__(self, model: str = "ollama-llama3.1"):
        self.model = model

    def complete(self, prompt: str, temperature: float = 0.2, max_tokens: int = 512) -> LLMResponse:
        """
        Try ollama first; if unavailable, return a stubbed JSON skeleton (GRAY pillars).
        """
        start = time.time()
        try:
            import ollama  # type: ignore
        except Exception:
            # Stub fallback for environments without ollama
            skeleton = {
                "pillars": [
                    {"pillar": PillarEnum.HUMAN_STABILITY.value, "color": ColorEnum.GRAY.value, "score": None,
                     "reason_codes": [], "evidence_todo": ["Gather evidence for assessment"]},
                    {"pillar": PillarEnum.ECONOMIC_RESILIENCE.value, "color": ColorEnum.GRAY.value, "score": None,
                     "reason_codes": [], "evidence_todo": ["Gather evidence for assessment"]},
                    {"pillar": PillarEnum.ECOLOGICAL_INTEGRITY.value, "color": ColorEnum.GRAY.value, "score": None,
                     "reason_codes": [], "evidence_todo": ["Gather evidence for assessment"]},
                    {"pillar": PillarEnum.RIGHTS_LEGALITY.value, "color": ColorEnum.GRAY.value, "score": None,
                     "reason_codes": [], "evidence_todo": ["Gather evidence for assessment"]},
                ],
                "rules_applied": {
                    "color_to_score": COLOR_TO_SCORE_TO_LITERALS(),
                    "evidence_gate": "No GREEN unless evidence_todo is empty"
                }
            }
            txt = json.dumps(skeleton, indent=2)
            return LLMResponse(text=txt, raw=skeleton, duration_s=time.time() - start)

        # Actual ollama call
        try:
            resp = ollama.chat(model=self.model, messages=[
                {"role": "system", "content": PILLAR_SYSTEM_PROMPT()},
                {"role": "user", "content": prompt}
            ])
            txt = resp.get("message", {}).get("content", "")
            return LLMResponse(text=txt, raw=resp, duration_s=time.time() - start)
        except Exception as e:
            logging.warning("Ollama call failed (%s). Falling back to stub JSON.", e)
            return self.complete(prompt=prompt)  # recurse into stub path


def PILLAR_SYSTEM_PROMPT() -> str:
    allowed_pillars = ", ".join(p.value for p in PillarEnum)
    allowed_colors = ", ".join(c.value for c in ColorEnum)
    allowed_codes = ", ".join(rc.value for rc in ReasonCodeEnum)
    per_pillar_map = {
        p.value: sorted(rc.value for rc in REASON_CODES_BY_PILLAR[p])
        for p in REASON_CODES_BY_PILLAR
    }
    return (
        "You emit JSON ONLY. No prose, no markdown.\n"
        "Task: Step-1 PILLARS. Emit an object with fields: pillars[], rules_applied.\n"
        f"Pillars must be one of: [{allowed_pillars}]. Colors from: [{allowed_colors}].\n"
        f"Allowed reason_codes: [{allowed_codes}]. Use only codes allowed for each pillar as per map: "
        f"{json.dumps(per_pillar_map)}.\n"
        "Rules:\n"
        "- Emit exactly 4 items (one per pillar).\n"
        "- GREEN requires evidence_todo == []. If any evidence_todo is present, do not use GREEN.\n"
        "- If unsure, set color=GRAY and leave reason_codes empty.\n"
        "Shape example:\n"
        "{\n"
        '  "pillars":[{"pillar":"HumanStability","color":"YELLOW","score":60,"reason_codes":["STAFF_AVERSION"],'
        ' "evidence_todo":["Stakeholder survey baseline"]}],\n'
        '  "rules_applied":{"color_to_score":{"GREEN":[70,100],"YELLOW":[40,69],"RED":[0,39],"GRAY":null},'
        '  "evidence_gate":"No GREEN unless evidence_todo is empty"}\n'
        "}\n"
    )


def COLOR_TO_SCORE_TO_LITERALS() -> Dict[str, Optional[List[int]]]:
    out: Dict[str, Optional[List[int]]] = {}
    for k, v in COLOR_TO_SCORE.items():
        out[k.value] = list(v) if v else None
    return out

# ------------------------------------------------------------------------------
# JSON helpers & Validation/Repair
# ------------------------------------------------------------------------------

def extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    Extract the first top-level JSON object from arbitrary text.
    """
    text = text.strip()
    # Fast path: starts with '{'
    if text.startswith("{"):
        try:
            return json.loads(text)
        except Exception:
            pass

    # Fallback: find the largest {...} block
    start_idxs = [m.start() for m in re.finditer(r"\{", text)]
    end_idxs = [m.start() for m in re.finditer(r"\}", text)]
    for s in start_idxs:
        for e in reversed(end_idxs):
            if e > s:
                chunk = text[s : e + 1]
                try:
                    return json.loads(chunk)
                except Exception:
                    continue
    # Final fallback: empty skeleton
    return {"pillars": [], "rules_applied": {}}


def _pretty_pillar_name(p: str) -> str:
    return (p.replace("_", " ").replace("-", " ")
            .replace("HumanStability", "Human Stability")
            .replace("EconomicResilience", "Economic Resilience")
            .replace("EcologicalIntegrity", "Ecological Integrity")
            .replace("Rights_Legality", "Rights & Legality"))


def _in_band(score: Optional[int], color: ColorEnum) -> bool:
    if score is None:
        return False
    band = COLOR_TO_SCORE.get(color)
    if not band:
        return False
    lo, hi = band
    return lo <= score <= hi


def validate_and_repair(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce schema rules and repair weak-model mistakes.
    """
    if not isinstance(data, dict):
        data = {"pillars": [], "rules_applied": {}}

    # Never trust model-provided markdown at Step 1
    data.pop("markdown", None)

    # Ensure pillars exist
    pillars = data.get("pillars", [])
    if not isinstance(pillars, list):
        pillars = []
    validated: List[Dict[str, Any]] = []

    # Seed map for presence tracking
    expected = {
        PillarEnum.HUMAN_STABILITY,
        PillarEnum.ECONOMIC_RESILIENCE,
        PillarEnum.ECOLOGICAL_INTEGRITY,
        PillarEnum.RIGHTS_LEGALITY,
    }
    seen: Set[PillarEnum] = set()

    # Normalize provided pillars
    for raw in pillars:
        if not isinstance(raw, dict):
            continue

        # Pillar enum
        try:
            pillar = PillarEnum(raw.get("pillar", PillarEnum.RIGHTS_LEGALITY.value))
        except Exception:
            pillar = PillarEnum.RIGHTS_LEGALITY
        raw["pillar"] = pillar.value
        seen.add(pillar)

        # Color enum
        try:
            color = ColorEnum(raw.get("color", ColorEnum.GRAY.value))
        except Exception:
            color = ColorEnum.GRAY
        raw["color"] = color.value

        # Evidence todo
        evidence_todo: List[str] = raw.get("evidence_todo", []) or []
        if not isinstance(evidence_todo, list):
            evidence_todo = []

        # Score
        score = raw.get("score", None)
        if isinstance(score, (int, float)):
            score = int(score)
        else:
            score = None

        # Reason codes: validate & whitelist by pillar
        raw_codes: List[str] = raw.get("reason_codes", []) or []
        validated_codes: List[str] = []
        for code in raw_codes:
            try:
                rc = ReasonCodeEnum(code)
            except Exception:
                continue
            if rc in REASON_CODES_BY_PILLAR[pillar]:
                validated_codes.append(rc.value)

        # Evidence-gated GREEN
        if color == ColorEnum.GREEN and evidence_todo:
            color = ColorEnum.YELLOW

        # No GREEN with negatives
        if color == ColorEnum.GREEN and any(ReasonCodeEnum(c) in NEGATIVE_REASON_CODES for c in validated_codes):
            color = ColorEnum.YELLOW

        # If YELLOW/RED but with no valid reason codes and no evidence → GRAY
        if color in (ColorEnum.YELLOW, ColorEnum.RED) and not validated_codes and not evidence_todo:
            color = ColorEnum.GRAY

        # Snap score to band midpoint if missing or out of band
        if color == ColorEnum.GRAY:
            score = None
        else:
            if (score is None) or (not _in_band(score, color)):
                score = get_color_band_midpoint(color)

        repaired = {
            "pillar": pillar.value,
            "color": color.value if isinstance(color, ColorEnum) else color,
            "score": score,
            "reason_codes": validated_codes,
            "evidence_todo": evidence_todo if evidence_todo else ([] if color == ColorEnum.GREEN else evidence_todo),
        }

        # Ensure GRAY has at least one evidence task
        if repaired["color"] == ColorEnum.GRAY.value and not repaired["evidence_todo"]:
            repaired["evidence_todo"] = ["Gather evidence for assessment"]

        validated.append(repaired)

    # Add any missing pillars as GRAY placeholders
    missing = expected - seen
    for p in sorted(missing, key=lambda x: x.value):
        validated.append({
            "pillar": p.value,
            "color": ColorEnum.GRAY.value,
            "score": None,
            "reason_codes": [],
            "evidence_todo": ["Gather evidence for assessment"],
        })

    # Sort pillars to canonical order
    order = [
        PillarEnum.HUMAN_STABILITY.value,
        PillarEnum.ECONOMIC_RESILIENCE.value,
        PillarEnum.ECOLOGICAL_INTEGRITY.value,
        PillarEnum.RIGHTS_LEGALITY.value,
    ]
    validated.sort(key=lambda d: order.index(d["pillar"]) if d.get("pillar") in order else 999)

    # Overwrite rules_applied with authoritative constants
    repaired_data = {
        "pillars": validated,
        "rules_applied": {
            "color_to_score": COLOR_TO_SCORE_TO_LITERALS(),
            "evidence_gate": "No GREEN unless evidence_todo is empty"
        }
    }
    return repaired_data


def fix_bullet_lists(md: str) -> str:
    # Minimal cleanup helper; extend if your renderer needs it
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md


def convert_to_markdown(data: Dict[str, Any]) -> str:
    """Render our own markdown (never trust LLM markdown)."""
    pillars: List[Dict[str, Any]] = data.get("pillars", [])
    color_counts = {c.value: 0 for c in ColorEnum}
    for p in pillars:
        c = p.get("color", ColorEnum.GRAY.value)
        if c in color_counts:
            color_counts[c] += 1

    rows: List[str] = []
    rows.append("# Pillars Assessment")
    rows.append("")
    rows.append("## Summary")
    rows.append("")
    rows.append(f"- **GREEN**: {color_counts['GREEN']} pillars")
    rows.append(f"- **YELLOW**: {color_counts['YELLOW']} pillars")
    rows.append(f"- **RED**: {color_counts['RED']} pillars")
    rows.append(f"- **GRAY**: {color_counts['GRAY']} pillars")
    rows.append("")
    rows.append("## Pillar Details")

    for pillar in pillars:
        pillar_name = _pretty_pillar_name(str(pillar.get("pillar", "Unknown")))
        color = pillar.get("color", "GRAY")
        score = pillar.get("score", "N/A")
        reason_codes = pillar.get("reason_codes", [])
        evidence_todo = pillar.get("evidence_todo", [])

        rows.append(f"### {pillar_name}")
        rows.append(f"**Status**: {color} ({score})")

        if reason_codes:
            rows.append(f"**Issues**: {', '.join(reason_codes)}")

        if evidence_todo:
            rows.append("**Evidence Needed:**")
            rows.append("")
            for item in evidence_todo:
                rows.append(f"- {item}")
            rows.append("")

    rows.append("")
    rows.append("## Assessment Rules")
    rows.append("")
    rows.append("- **Evidence Gate**: No GREEN unless evidence_todo is empty")

    markdown = "\n".join(rows)
    return fix_bullet_lists(markdown)

# ------------------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------------------

def assess_pillars(plan_text: str, model: str = "ollama-llama3.1",
                   temperature: float = 0.2, max_tokens: int = 512) -> Dict[str, Any]:
    """
    Run Step-1: ask the LLM for raw pillars JSON, then validate & repair it.
    """
    client = LLMClient(model=model)
    logging.info("Assessing plan with %s...", model)

    prompt = (
        "Extract Step-1 pillars for the following plan. "
        "Return JSON only (no markdown), following the system instructions.\n\n"
        f"--- PLAN START ---\n{plan_text}\n--- PLAN END ---"
    )

    resp = client.complete(prompt=prompt, temperature=temperature, max_tokens=max_tokens)
    raw_json = extract_json_from_text(resp.text)
    repaired = validate_and_repair(raw_json)
    repaired["metadata"] = {
        "context_window": None,  # unknown without model internals
        "num_output": max_tokens,
        "is_chat_model": True,
        "is_function_calling_model": False,
        "model_name": model,
        "system_role": "system",
        "llm_classname": client.__class__.__name__,
        "duration": int(resp.duration_s),
        "response_byte_count": len(resp.text.encode("utf-8")),
    }
    repaired["markdown"] = convert_to_markdown(repaired)
    return repaired

# ------------------------------------------------------------------------------
# CLI entrypoint
# ------------------------------------------------------------------------------

def _read_all_stdin() -> str:
    if sys.stdin and not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def main() -> None:

    plan_text = """
    Project: Sustainable Data Center Migration
    
    We plan to migrate our legacy data center infrastructure to a cloud-based solution
    with renewable energy sources. The project involves moving 50+ servers, updating
    security protocols, and ensuring compliance with new data protection regulations.
    
    Budget: $2M allocated, with 5% contingency
    Timeline: 12 months
    Team: 15 engineers, 3 compliance specialists
    
    Risks: Legacy system integration, data sovereignty requirements, staff training needs
    """
    
    model_name = "ollama-llama3.1"
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    result = assess_pillars(plan_text, model=model_name, temperature=0.2, max_tokens=512)

    # Pretty print JSON block (first), then our markdown block for humans.
    print("\nResponse:")
    print(json.dumps({k: v for k, v in result.items() if k != "markdown"}, indent=2, ensure_ascii=False))
    print("\n\nMarkdown:")
    print(result["markdown"])


if __name__ == "__main__":
    main()