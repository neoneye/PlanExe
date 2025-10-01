"""
IDEA: Get rid of the hardcoded "RED"/"YELLOW"/"GREEN" strings and use the StatusEnum instead.
However before doing so, I want to rework the scoring system. Currently it is value 0-100. 
I want to change it to a multiple parameters in the range 1-5, so that the score can be fact checked.
Then it make sense to get rid of the hardcoded "RED"/"YELLOW"/"GREEN" strings and use the StatusEnum instead.
"""
import json
from typing import Dict, List, Optional, Tuple

def make_pillars_system_prompt(
    PILLAR_ORDER: List[str],
    REASON_CODES_BY_PILLAR: Dict[str, List[str]],
    STATUS_BANDS: Optional[Dict[str, Optional[Tuple[int, int]]]] = None,
    DEFAULT_EVIDENCE_BY_PILLAR: Optional[Dict[str, List[str]]] = None,
    FORBID_FIRST_WORDS: Optional[List[str]] = None,
) -> str:
    """
    Build a self-contained system prompt for Viability Protocol · Step 1 (PILLARS),
    with an inline, *ordered* skeleton JSON the model must overwrite in-place.

    Auto-sync:
      - Pillar order: from PILLAR_ORDER
      - Reason-code whitelist: from REASON_CODES_BY_PILLAR
      - Status bands + midpoints: from STATUS_BANDS (or defaults)
      - GRAY defaults: from DEFAULT_EVIDENCE_BY_PILLAR (or sensible defaults)

    Returns:
      A system prompt string.
    """

    # ---- Defaults -----------------------------------------------------------
    if STATUS_BANDS is None:
        STATUS_BANDS = {
            "GREEN":  (70, 100),
            "YELLOW": (40, 69),
            "RED":    (0, 39),
            "GRAY":   None,
        }

    if FORBID_FIRST_WORDS is None:
        FORBID_FIRST_WORDS = [
            "conduct", "ensure", "perform", "create", "update",
            "implement", "analyze", "review"
        ]

    # Provide robust defaults for GRAY evidence if caller doesn't supply them.
    if DEFAULT_EVIDENCE_BY_PILLAR is None:
        DEFAULT_EVIDENCE_BY_PILLAR = {
            "HumanStability": [
                "Stakeholder map + skills gap snapshot",
                "Change plan v1 (communications, training, adoption KPIs)"
            ],
            "EconomicResilience": [
                "Assumption ledger v1 + sensitivity table",
                "Cost model v2 (on-prem vs cloud TCO)"
            ],
            "EcologicalIntegrity": [
                "Environmental baseline note (scope, metrics)",
                "Cloud carbon estimate v1 (regions/services)"
            ],
            "Rights_Legality": [
                "Regulatory mapping v1 + open questions list",
                "Licenses & permits inventory + gaps list"
            ],
        }

    # Ensure every pillar in order has at least 2 default items (fallbacks).
    for p in PILLAR_ORDER:
        DEFAULT_EVIDENCE_BY_PILLAR.setdefault(p, [
            "Baseline note v1 (scope, metrics)",
            "Risk register v1 (issues, owners)"
        ])

    # ---- Derived values -----------------------------------------------------
    def _midpoints(bands: Dict[str, Optional[Tuple[int, int]]]) -> Dict[str, Optional[int]]:
        # Hardcode rounded midpoints to match validator logic.
        MIDPOINT_OVERRIDES = {"GREEN": 85, "YELLOW": 55, "RED": 20}
        out: Dict[str, Optional[int]] = {}
        for k, rng in bands.items():
            out[k] = MIDPOINT_OVERRIDES.get(k) if rng is not None else None
        return out

    BAND_MIDPOINTS = _midpoints(STATUS_BANDS)

    # The enforced, ordered skeleton the model must overwrite.
    skeleton = {
        "pillars": [
            {
                "pillar": p,
                "status": "GRAY",
                "score": None,
                "reason_codes": [],
                "evidence_todo": DEFAULT_EVIDENCE_BY_PILLAR.get(p, [])[:2],
                "strength_rationale": None,
            }
            for p in PILLAR_ORDER
        ]
    }

    # ---- JSON blocks to embed verbatim into the prompt ----------------------
    pillar_order_json        = json.dumps(PILLAR_ORDER, indent=2, ensure_ascii=False)
    reason_whitelist_json    = json.dumps(REASON_CODES_BY_PILLAR, indent=2, sort_keys=True, ensure_ascii=False)
    status_bands_json        = json.dumps(STATUS_BANDS, indent=2, sort_keys=True, ensure_ascii=False)
    band_midpoints_json      = json.dumps(BAND_MIDPOINTS, indent=2, sort_keys=True, ensure_ascii=False)
    skeleton_json            = json.dumps(skeleton, indent=2, ensure_ascii=False)
    gray_defaults_json       = json.dumps(DEFAULT_EVIDENCE_BY_PILLAR, indent=2, sort_keys=True, ensure_ascii=False)
    forbid_first_words_json  = json.dumps(FORBID_FIRST_WORDS, indent=2, ensure_ascii=False)

    # ---- Output contract (kept for clarity; skeleton enforces order) --------
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

    # ---- Prompt -------------------------------------------------------------
    prompt = (
        "You output JSON only. No prose, no markdown.\n\n"
        "ASSIGNMENT — Determine viability of a plan — PILLARS\n"
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
        "- If information is too thin to justify YELLOW/RED with a listed reason_code, use GRAY.\n"
        "- For every GRAY pillar, evidence_todo MUST contain 1–2 artifact-style items (do NOT leave it empty).\n\n"

        "Evidence style (artifacts, not actions):\n"
        '- GOOD: "Unit economics model v1 + sensitivity table", "Supplier risk register v1", "Top-N data sources: licenses + DPIAs bundle".\n'
        '- BAD:  "hire engineers", "do research", "offset carbon". Avoid action verbs; name the artifact to be produced.\n\n'

        "Evidence sanity:\n"
        "- Each evidence_todo MUST be a noun phrase naming an artifact (report, model, register, baseline, inventory, memo, map, plan, log, workbook), optionally with 'v1/v2'.\n"
        f"- FORBIDDEN as a first word: from this list {forbid_first_words_json}.\n"
        "- If an item begins with a verb, REWRITE it into the artifact that would result from that action.\n\n"

        "GRAY defaults:\n"
        "- If a pillar is GRAY and you have not proposed evidence, use the defaults for that pillar from this mapping:\n"
        f"{gray_defaults_json}\n\n"

        "STRICT OUTPUT METHOD — OVERWRITE THE SKELETON BELOW:\n"
        "Return your result by OVERWRITING this exact JSON structure in-place. Keep the same order and keys. Replace values only. Do NOT add, remove, or reorder objects. Do NOT add fields.\n"
        "If you keep any pillar as GRAY, you MUST NOT delete the prefilled evidence_todo; either keep them or REPLACE them with 1–2 artifact items. An empty evidence_todo for a GRAY pillar is INVALID.\n"
        f"{skeleton_json}\n\n"

        "Tie-breaks & determinism:\n"
        "- If unsure between GREEN and YELLOW, choose YELLOW with at least one whitelist reason_code; if still unsure, choose GRAY.\n"
        "- If the plan never touches a pillar, mark it GRAY and propose concrete evidence to unlock assessment.\n"
        "- Treat any risk or need mentioned in the plan as an open issue unless there is explicit evidence it has been resolved.\n"
        "- Scrutinize quantitative claims (e.g., budgets, timelines, percentages). A low contingency (<10-15%) for a complex project is a significant risk; do not mark it GREEN without strong counter-evidence.\n"
        "- Do not invent fields. Do not output prose or markdown.\n\n"

        f"{output_contract}\n"
    )

    return prompt