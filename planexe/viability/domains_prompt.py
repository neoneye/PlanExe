import json
from typing import Dict, List, Optional
from planexe.viability.taxonomy import DOMAIN_ORDER, REASON_CODES_BY_DOMAIN, DEFAULT_EVIDENCE_BY_DOMAIN

def make_domains_system_prompt(
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

        "Acceptance criteria handling (STRICT):\n"
        "- Do NOT output acceptance criteria. Do not add \"— acceptance criteria: …\" and do not use parenthetical checklists.\n"
        "- Emit evidence items as TITLE-ONLY; a post-processor will append acceptance criteria.\n\n"
        "Evidence titles (CANONICAL + MATCHABLE):\n"
        "- Use short, artifact-style nouns with a version tag (e.g., \"… v1\", \"… v2\").\n"
        "- Prefer canonical titles from the cheat sheet below. Do not invent synonyms. Do not change word order.\n"
        "- Avoid extra adjectives or trailing parentheses unless they appear in the cheat sheet.\n"
        "- Keep titles ≤12 words, ASCII punctuation only; use ‘+’ to join paired artifacts (e.g., \"X + Y list\").\n\n"
        "Evidence gating (STRICT):\n"
        "- Status → evidence_todo:\n"
        "  • GREEN → [] (must be empty).\n"
        "  • YELLOW or RED → MUST contain 1–2 artifact-style TODO item titles. Never leave empty.\n"
        "  • GRAY → MUST contain 1–2 discovery artifacts to resolve unknowns.\n"
        "- Selection rule for YELLOW/RED:\n"
        "  1) Map listed reason_codes to the most relevant cheat-sheet titles below.\n"
        "  2) If none fit, synthesize a canonical-style artifact title (5–10 words) with a version tag (e.g., \"v1\").\n"
        "  3) Do not duplicate items already present in the evidence list.\n"
        "- Content rules for each evidence_todo item:\n"
        "  • Title only (no acceptance criteria, owners, or dates).\n"
        "  • Artifact-style, concrete nouns (e.g., \"Supplier risk register v1\"), not vague actions (\"improve supplier risk\").\n"
        "  • Keep items unique.\n"
        "- Sanity check before finalizing:\n"
        "  • If status ∈ {YELLOW, RED} AND evidence_todo == [], FIX IT by adding 2 items per the rules above.\n"
        "  • If you cannot justify YELLOW/RED with at least one reason_code, use GRAY and include discovery artifacts.\n\n"
        "Canonical evidence cheat sheet (use these titles verbatim when relevant):\n"
        "- Stakeholder map + skills gap snapshot\n"
        "- Change plan v1 (communications, training, adoption KPIs)\n"
        "- Assumption ledger v1 + sensitivity table\n"
        "- Cost model v2 (on-prem vs cloud TCO)\n"
        "- Environmental baseline note (scope, metrics)\n"
        "- Cloud carbon estimate v1 (regions/services)\n"
        "- Regulatory mapping v1 + open questions list\n"
        "- Licenses & permits inventory + gaps list\n"
        "- Supplier risk register v1 + diversification plan\n"
        "- Unit economics model v1 + sensitivity table (key drivers)\n"
        "- Threat model + control mapping (e.g., STRIDE mapped to CIS/NIST)\n"
        "- Data profiling report (completeness, accuracy, drift)\n"
        "- Business impact analysis v1 (RTO/RPO, critical processes)\n"
        "- DR/BCP test report (last test + outcomes)\n"
        "- Top-N data sources: licenses + DPIAs bundle\n\n"

        "Examples:\n"
        "- Issues: [SUPPLIER_CONCENTRATION] → evidence_todo: [\"Supplier risk register v1 + diversification plan\"]\n"
        "- Issues: [DPIA_GAPS, INFOSEC_GAPS] → evidence_todo: [\"Bundle the license files for the top data sources and the corresponding DPIAs.\",\"Threat model + control mapping (e.g. STRIDE mapped to CIS/NIST)\"]\n\n"

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
