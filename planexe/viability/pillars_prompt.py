import json
from typing import Dict, List, Optional, Tuple

def make_pillars_system_prompt(
    PILLAR_ORDER: List[str],
    REASON_CODES_BY_PILLAR: Dict[str, List[str]],
    STATUS_BANDS: Optional[Dict[str, Optional[Tuple[int, int]]]] = None,
) -> str:
    """
    Build a self-contained system prompt for Step 1 (PILLARS) that
    auto-injects current pillar order and reason-code whitelists.

    Args
    ----
    PILLAR_ORDER: e.g. ["HumanStability","EconomicResilience","EcologicalIntegrity","Rights_Legality"]
    REASON_CODES_BY_PILLAR: {"EconomicResilience":["CONTINGENCY_LOW", ...], ...}
    STATUS_BANDS: optional override, e.g. {
        "GREEN":  (70, 100),
        "YELLOW": (40, 69),
        "RED":    (0, 39),
        "GRAY":   None
    }

    Returns
    -------
    A system prompt string.
    """
    # Defaults if you don’t pass STATUS_BANDS
    if STATUS_BANDS is None:
        STATUS_BANDS = {
            "GREEN":  (70, 100),
            "YELLOW": (40, 69),
            "RED":    (0, 39),
            "GRAY":   None,
        }

    def _midpoints(bands: Dict[str, Optional[Tuple[int, int]]]) -> Dict[str, Optional[int]]:
        m = {}
        for k, rng in bands.items():
            if rng is None:
                m[k] = None
            else:
                lo, hi = rng
                m[k] = (lo + hi) // 2
        return m

    BAND_MIDPOINTS = _midpoints(STATUS_BANDS)

    pillar_order_json = json.dumps(PILLAR_ORDER)
    reason_whitelist_json = json.dumps(REASON_CODES_BY_PILLAR, indent=2, sort_keys=True)
    status_bands_json = json.dumps(
        {k: v for k, v in STATUS_BANDS.items()},
        indent=2, sort_keys=True
    )
    band_midpoints_json = json.dumps(BAND_MIDPOINTS, indent=2, sort_keys=True)

    output_contract = r"""
Output contract (emit JSON only; exactly one object per pillar, arrays must exist even if empty):
{
  "pillars": [
    {
      "pillar": "HumanStability" | "EconomicResilience" | "EcologicalIntegrity" | "Rights_Legality",
      "status": "GREEN" | "YELLOW" | "RED" | "GRAY",
      "score":  integer | null,
      "reason_codes": [string, ...],   // only from the whitelist for this pillar
      "evidence_todo": [string, ...],  // ≤ 2 artifact-style items; empty for GREEN
      "strength_rationale": "string"   // OPTIONAL; only for GREEN; omit otherwise
    }
  ]
}
""".strip()

    prompt = (
        "You output JSON only. No prose, no markdown.\n\n"
        "ASSIGNMENT — Viability Protocol · Step 1: PILLARS\n"
        "Given a plan (free-text), assess viability across the defined pillars and return a single JSON object.\n\n"
        "Pillar order (emit exactly one object per pillar, in this exact order):\n"
        f"{pillar_order_json}\n\n"
        "Reason-code whitelist by pillar (use UPPERCASE exactly; do NOT invent new codes; empty array if none apply):\n"
        f"{reason_whitelist_json}\n\n"
        "Status bands (scores must stay within the chosen band; GRAY has no score):\n"
        f"{status_bands_json}\n\n"
        "Band midpoints to use when uncertain within a band:\n"
        f"{band_midpoints_json}\n\n"
        "Pillar scopes (evaluate all pillars even if absent in the input):\n"
        "- HumanStability — people/org readiness, governance, change management, training, operating model.\n"
        "- EconomicResilience — budget/contingency, unit economics, suppliers/SPOF/integration, delivery risk.\n"
        "- EcologicalIntegrity — environmental impact/baselines, carbon/water/waste, permits/mitigation.\n"
        "- Rights_Legality — laws, licenses/permissions, data protection/ethics, biosecurity/permits.\n\n"
        "Scoring rules:\n"
        "- GREEN  → score ∈ GREEN band (use the GREEN midpoint if uncertain).\n"
        "- YELLOW → score ∈ YELLOW band (use the YELLOW midpoint if uncertain).\n"
        "- RED    → score ∈ RED band (use the RED midpoint if uncertain).\n"
        "- GRAY   → score must be null (insufficient/ambiguous evidence).\n\n"
        "Evidence gating:\n"
        "- GREEN ⇒ evidence_todo MUST be empty.\n"
        "- YELLOW/RED ⇒ include 1–2 concise artifact-style evidence TODOs tied to the issues.\n"
        "- If information is too thin to justify YELLOW/RED with a listed reason_code, use GRAY and propose evidence.\n\n"
        "Evidence style (artifacts, not actions):\n"
        "- GOOD: \"Unit economics model v1 + sensitivity table\", \"Supplier risk register v1\", \"Top-N data sources: licenses + DPIAs bundle\".\n"
        "- BAD:  \"hire engineers\", \"do research\", \"offset carbon\". Avoid action verbs; name the artifact to be produced.\n\n"
        "Tie-breaks & determinism:\n"
        "- If unsure between GREEN and YELLOW, choose YELLOW with at least one whitelist reason_code; if still unsure, choose GRAY.\n"
        "- If the plan never touches a pillar, mark it GRAY and propose concrete evidence to unlock assessment.\n"
        "- Do not invent fields. Do not output prose or markdown.\n\n"
        f"{output_contract}\n"
    )
    return prompt