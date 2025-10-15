"""
IDEA: Get rid of the hardcoded "RED"/"YELLOW"/"GREEN" strings and use the StatusEnum instead.
However before doing so, I want to rework the scoring system. Currently it is value 0-100. 
I want to change it to a multiple parameters in the range 1-5, so that the score can be fact checked.
Then it make sense to get rid of the hardcoded "RED"/"YELLOW"/"GREEN" strings and use the StatusEnum instead.
"""
import json
from typing import Dict, List, Optional

def make_domains_system_prompt(
    DOMAIN_ORDER: List[str],
    REASON_CODES_BY_DOMAIN: Dict[str, List[str]],
    DEFAULT_EVIDENCE_BY_DOMAIN: Optional[Dict[str, List[str]]] = None,
    FORBID_FIRST_WORDS: Optional[List[str]] = None,
) -> str:
    """
    Build a self-contained system prompt for Viability Protocol · Step 1 (DOMAINS),
    with an inline, *ordered* skeleton JSON the model must overwrite in-place.

    Auto-sync:
      - Domain order: from DOMAIN_ORDER
      - Reason-code whitelist: from REASON_CODES_BY_DOMAIN
      - GRAY defaults: from DEFAULT_EVIDENCE_BY_DOMAIN (or sensible defaults)

    Returns:
      A system prompt string.
    """

    # ---- Defaults -----------------------------------------------------------
    if FORBID_FIRST_WORDS is None:
        FORBID_FIRST_WORDS = [
            "conduct", "ensure", "perform", "create", "update",
            "implement", "analyze", "review"
        ]

    # Provide robust defaults for GRAY evidence if caller doesn't supply them.
    if DEFAULT_EVIDENCE_BY_DOMAIN is None:
        DEFAULT_EVIDENCE_BY_DOMAIN = {
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

    # Ensure every domain in order has at least 2 default items (fallbacks).
    for p in DOMAIN_ORDER:
        DEFAULT_EVIDENCE_BY_DOMAIN.setdefault(p, [
            "Baseline note v1 (scope, metrics)",
            "Risk register v1 (issues, owners)"
        ])

    # ---- Derived values -----------------------------------------------------
    factor_rubric_lines = [
        "- HumanStability — evidence: org charts, RACI, training plans, comms plan; risk: stakeholder conflict, turnover risk, change fatigue; fit: governance clarity, incentives aligned.",
        "- EconomicResilience — evidence: budget, unit economics, funding letters, signed contracts; risk: sensitivity to shocks, supplier concentration, FX/rate exposure; fit: cost/benefit logic, ramp realism, contingency buffers.",
        "- EcologicalIntegrity — evidence: EIA/EIS, baseline studies, third-party audits; risk: biodiversity/water/air risks post-mitigation; fit: mitigation hierarchy, circularity, waste design.",
        "- Rights_Legality — evidence: DPIA, legal opinions, permits/licenses; risk: compliance failure, infosec/privacy breach, sanctions; fit: ethical framework, data rights alignment, due process.",
    ]
    factor_rubric_text = "\n".join(factor_rubric_lines)

    # The enforced, ordered skeleton the model must overwrite.
    skeleton = {
        "domains": [
            {
                "domain": p,
                "status": "GRAY",
                "score": {
                    "evidence": None,
                    "risk": None,
                    "fit": None,
                },
                "reason_codes": [],
                "evidence_todo": DEFAULT_EVIDENCE_BY_DOMAIN.get(p, [])[:2],
                "strength_rationale": None,
            }
            for p in DOMAIN_ORDER
        ]
    }

    # ---- JSON blocks to embed verbatim into the prompt ----------------------
    domain_order_json        = json.dumps(DOMAIN_ORDER, indent=2, ensure_ascii=False)
    reason_whitelist_json    = json.dumps(REASON_CODES_BY_DOMAIN, indent=2, sort_keys=True, ensure_ascii=False)
    skeleton_json            = json.dumps(skeleton, indent=2, ensure_ascii=False)
    gray_defaults_json       = json.dumps(DEFAULT_EVIDENCE_BY_DOMAIN, indent=2, sort_keys=True, ensure_ascii=False)
    forbid_first_words_json  = json.dumps(FORBID_FIRST_WORDS, indent=2, ensure_ascii=False)

    # ---- Output contract (kept for clarity; skeleton enforces order) --------
    output_contract = r"""
Output contract (emit JSON only; exactly one object per domain, arrays must exist even if empty):
{
  "domains": [
    {
      "domain": "HumanStability" | "EconomicResilience" | "EcologicalIntegrity" | "Rights_Legality",
      "status": "GREEN" | "YELLOW" | "RED" | "GRAY",
      "score": {
        "evidence": integer | null,  // Likert 1–5, null if status is GRAY
        "risk": integer | null,
        "fit": integer | null
      },
      "reason_codes": [string, ...],   // only from the whitelist for this domain
      "evidence_todo": [string, ...],  // ≤ 2 artifact-style items; empty for GREEN
      "strength_rationale": "string"   // OPTIONAL; only for GREEN; omit otherwise
    }
  ]
}
""".strip()

    # ---- Prompt -------------------------------------------------------------
    prompt = (
        "You output JSON only. No prose, no markdown.\n\n"
        "ASSIGNMENT — Determine viability of a plan — DOMAINS\n"
        "Given a plan (free-text), assess viability across the defined domains and return a single JSON object.\n\n"

        "Domain order (emit exactly one object per domain, in this exact order):\n"
        f"{domain_order_json}\n\n"

        "Reason-code whitelist by domain (use UPPERCASE exactly; do NOT invent new codes; empty array if none apply):\n"
        f"{reason_whitelist_json}\n\n"

        "Domain scopes (evaluate all domains even if absent in the input):\n"
        "- HumanStability — people/org readiness, governance, change management, training, operating model.\n"
        "- EconomicResilience — budget/contingency, unit economics, suppliers/SPOF/integration, delivery risk.\n"
        "- EcologicalIntegrity — environmental impact/baselines, carbon/water/waste, permits/mitigation.\n"
        "- Rights_Legality — laws, licenses/permissions, data protection/ethics, biosecurity/permits.\n\n"

        "Likert scoring (1=poor, 5=excellent):\n"
        "- evidence — strength of supporting docs/artifacts.\n"
        "- risk — residual risk posture after mitigations.\n"
        "- fit — alignment/coherence with the domain’s aims.\n\n"

        "Scoring discipline:\n"
        "- Start from the defaults above, then adjust each factor individually based on the plan.\n"
        "- Only output identical factor values when the underlying evidence truly supports the same posture.\n"
        "- Allow stronger dimensions to remain high even if a single weak factor drives RED/YELLOW.\n\n"

        "Factor rubric (use this mental checklist when assigning values):\n"
        f"{factor_rubric_text}\n\n"

        "Status derivation (keep status aligned with the worst factor):\n"
        "- Any factor ≤2 ⇒ RED.\n"
        "- Else if the worst factor ==3 ⇒ YELLOW.\n"
        "- Else if all factors ≥4 ⇒ GREEN.\n"
        "- Missing factors ⇒ GRAY (leave the factors null and propose evidence to unlock assessment).\n\n"

        "Evidence gating:\n"
        "- GREEN ⇒ evidence_todo MUST be empty.\n"
        "- YELLOW/RED ⇒ include 1–2 concise artifact-style evidence TODOs tied to the issues.\n"
        "- If information is too thin to justify YELLOW/RED with a listed reason_code, use GRAY.\n"
        "- For every GRAY domain, evidence_todo MUST contain 1–2 artifact-style items (do NOT leave it empty).\n\n"

        "Evidence style (artifacts, not actions):\n"
        '- GOOD: "Unit economics model v1 + sensitivity table", "Supplier risk register v1", "Top-N data sources: licenses + DPIAs bundle".\n'
        '- BAD:  "hire engineers", "do research", "offset carbon". Avoid action verbs; name the artifact to be produced.\n\n'

        "Evidence sanity:\n"
        "- Each evidence_todo MUST be a noun phrase naming an artifact (report, model, register, baseline, inventory, memo, map, plan, log, workbook), optionally with 'v1/v2'.\n"
        f"- FORBIDDEN as a first word: from this list {forbid_first_words_json}.\n"
        "- If an item begins with a verb, REWRITE it into the artifact that would result from that action.\n\n"

        "GRAY defaults:\n"
        "- If a domain is GRAY and you have not proposed evidence, use the defaults for that domain from this mapping:\n"
        f"{gray_defaults_json}\n\n"

        "### FACTOR DIFFERENTIATION RULE (MANDATORY)\n"
        "For any domain with status RED or YELLOW:\n"
        "- Do not set evidence, risk, and fit to the same value.\n"
        "- Choose a decisive factor (one of: evidence, risk, fit) that most strongly justifies the status per the rubric, and set it strictly lower than at least one of the other two.\n"
        "- Include at least one reason_code that clearly supports the chosen decisive factor.\n"
        "Examples (illustrative, not prescriptive):\n"
        "- Acceptable (RED): evidence=2, risk=1, fit=2 with GOVERNANCE_WEAK, STAKEHOLDER_CONFLICT (decisive factor: risk).\n"
        "- Acceptable (YELLOW): evidence=2, risk=3, fit=3 with DPIA_GAPS (decisive factor: evidence).\n"
        "- Not acceptable: evidence=3, risk=3, fit=3 with multiple issues.\n"
        "Note: Use equal factors only for GRAY. If the rubric seems balanced, choose the factor with the clearest supporting reason_code as decisive and reflect that in the numbers.\n\n"

        "STRICT OUTPUT METHOD — OVERWRITE THE SKELETON BELOW:\n"
        "Return your result by OVERWRITING this exact JSON structure in-place. Keep the same order and keys. Replace values only. Do NOT add, remove, or reorder objects. Do NOT add fields.\n"
        "If you keep any domain as GRAY, you MUST NOT delete the prefilled evidence_todo; either keep them or REPLACE them with 1–2 artifact items. An empty evidence_todo for a GRAY domain is INVALID.\n"
        f"{skeleton_json}\n\n"

        "Tie-breaks & determinism:\n"
        "- If unsure between GREEN and YELLOW, choose YELLOW with at least one whitelist reason_code; if still unsure, choose GRAY.\n"
        "- If the plan never touches a domain, mark it GRAY and propose concrete evidence to unlock assessment.\n"
        "- Treat any risk or need mentioned in the plan as an open issue unless there is explicit evidence it has been resolved.\n"
        "- Scrutinize quantitative claims (e.g., budgets, timelines, percentages). A low contingency (<10-15%) for a complex project is a significant risk; do not mark it GREEN without strong counter-evidence.\n"
        "- Do not invent fields. Do not output prose or markdown.\n\n"

        f"{output_contract}\n"
    )

    return prompt
