# Why this exists

Big plans die from two things: cognitive overload and fuzzy follow-through. A 20-page plan and a 200-row risk register can make a team feel like everything is broken, so nothing moves. In reality, most plans are a few fixes away from viable—yet a long, undifferentiated list of risks is demotivating and stalls execution.

This protocol turns that mess into a short, decision-ready path:
	•	Contain the scope first. We score four CAS pillars so risk lives inside a clear frame, not as a free-for-all list.
	•	Convert weakness into action. Only non-green pillars produce 3–5 blockers, each with acceptance tests and artifacts—no hand-wavy “mitigate later.”
	•	Bundle execution. We group blockers into Fix Packs, with FP0 (Pre-Commit Gate) capturing the minimal, high-leverage work that flips the recommendation.
	•	Make the verdict mechanical. The final Overall & Summary is a roll-up driven by rules, not vibes: worst pillar color, upgraded only if FP0 closes the hard gaps.

It also solves a practical tooling problem: weaker LLMs struggle with rich schemas and will hallucinate fields. Splitting the task into four small steps with enums and guardrails keeps outputs stable, auditable, and easy to wire into CI/CD or dashboards.

Bottom line: this exists so teams don’t stall at the sight of a scary risk list. You get a tight set of must-do fixes, a clear pre-commit gate, and a repeatable verdict that tells you exactly what flips to GO.

⸻

ViabilityAssessor — 4-Step, LLM-Friendly Protocol

A minimal, deterministic protocol that lets even a weaker LLM produce a useful viability assessment in four constrained steps:
	1.	Pillars → 2) Blockers → 3) Fix Packs → 4) Overall & Summary

This README defines purpose, data flow, enums, JSON shapes, guardrails, and validator rules so a programmer can wire it up without prior context.

⸻

TL;DR
	•	Order matters: Do Pillars first (scope), then Blockers (derived), then Fix Packs (clusters), then Overall/Summary (mechanical roll-up).
	•	Keep outputs tiny, enum-driven, ID-stable.
	•	After each step, run a validator/auto-repair pass to fix color/score ranges, drop unknown fields, and back-fill defaults.

⸻

Overall Purpose

The ViabilityAssessor turns a plan snapshot into a decision-ready assessment. It does this by:
	•	scoring the plan on four CAS pillars (HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality),
	•	turning weak pillars into a short list of blockers with acceptance tests and artifacts,
	•	bundling them into Fix Packs (with FP0 = Pre-Commit Gate),
	•	and producing an executive summary with a crisp recommendation and a small “what flips to GO” checklist.

Why four steps? Weak LLMs often fail strict schemas. Breaking the task into sequenced, derivation-based steps limits hallucination and keeps the JSON stable.

⸻

Data Flow

Plan text ──> Step 1: PILLARS ──> Step 2: BLOCKERS ──> Step 3: FIX_PACKS ──> Step 4: OVERALL+SUMMARY
                     ▲                  ▲                      ▲
                     │                  │                      │
                 validator           validator               validator

	•	Each step consumes the prior step’s JSON and emits its own small JSON.
	•	Your backend runs a validator after each step (see “Validation & Auto-repair”).

⸻

Step 0 — Constants & Enums (used in all steps)

PILLAR_ENUM
	•	HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality

COLOR_ENUM
	•	GREEN, YELLOW, RED, GRAY (unknown/insufficient info)

REASON_CODE_ENUM (small, stable set)
	•	Budget/Finance: CONTINGENCY_LOW, SINGLE_CUSTOMER, ALT_COST_UNKNOWN
	•	Rights/Compliance: DPIA_GAPS, LICENSE_GAPS, ABS_UNDEFINED, PERMIT_COMPLEXITY
	•	Tech/Integration: LEGACY_IT, INTEGRATION_RISK
	•	People/Adoption: TALENT_UNKNOWN, STAFF_AVERSION
	•	Climate/Ecology: CLOUD_CARBON_UNKNOWN, CLIMATE_UNQUANTIFIED, WATER_STRESS
	•	Biosecurity: BIOSECURITY_GAPS
	•	Governance/Ethics: ETHICS_VAGUE

COST_BAND_ENUM
	•	LOW, MEDIUM, HIGH
(You can map these to internal ROM ranges; e.g., LOW < 2 weeks or <$50k, etc.)

⸻

Step 1 — Emit Pillars

Goal: Establish the authoritative scope and evidence gates. No blockers yet.

Input
	•	Plan synopsis (text)
	•	Pillar and reason-code enums

Output (JSON) — what the LLM must emit

{
  "pillars": [
    {
      "pillar": "HumanStability",
      "light": "YELLOW",
      "score": 60,
      "reason_codes": ["STAFF_AVERSION"],
      "evidence_todo": ["Stakeholder survey baseline"]
    }
  ]
}

Note: The model outputs only the pillars array. No inline rule metadata.

Interpretation & validation (spec — not emitted by the LLM)
	•	Enumerations
	•	light ∈ {"GREEN","YELLOW","RED","GRAY"}
	•	pillar ∈ PILLAR_ENUM (unknown pillar names → treated as GRAY)
	•	reason_codes must come from the whitelist for that pillar (enforced downstream)
	•	Score bands
	•	GREEN: 70–100
	•	YELLOW: 40–69
	•	RED: 0–39
	•	GRAY: score must be null
	•	Validator behavior
	•	If light ≠ GRAY and score is missing or outside the band, the validator snaps to the band midpoint (GREEN:85, YELLOW:55, RED:20).
	•	If light == GRAY, score must be null (validator will null it if present).
	•	Unknown/unsupported pillar values are coerced to { "light":"GRAY", "score":null }.
	•	Evidence gating
	•	GREEN requires no open evidence items: evidence_todo must be empty.
	•	YELLOW/RED may have evidence_todo entries.
	•	Recommendation: For GRAY, include at least one concrete “first measurement” in evidence_todo to exit unknown.
	•	Formatting & determinism
	•	Emit plain JSON (no Markdown).
	•	Keep field names stable and lowercase with underscores for arrays.
	•	Order pillars consistently (e.g., the canonical PILLAR_ENUM order).

⸻

Step 2 — Emit Blockers (derived from Step 1)

Goal: Convert weak/unknown pillars into 3–5 crisp blockers with verifiable acceptance tests.

Derivation rule
	•	Only from pillars where color ∈ {RED, YELLOW, GRAY}.
	•	reason_codes must be a subset of the pillar’s reason_codes (or drawn from a small mapping you control).

Output (JSON)

{
  "source_pillars": ["EconomicResilience","Rights_Legality"],
  "blockers": [
    {
      "id": "B1",
      "pillar": "EconomicResilience",
      "title": "Contingency too low",
      "reason_codes": ["CONTINGENCY_LOW"],
      "acceptance_tests": [
        "≥10% contingency approved",
        "Monte Carlo risk workbook attached"
      ],
      "artifacts_required": ["Budget_v2.pdf","Risk_MC.xlsx"],
      "owner": "PMO",
      "rom": {"cost_band": "LOW", "eta_days": 14}
    }
  ]
}

Guardrails
	•	pillar must match one from Step 1.
	•	If rom missing, back-fill {"cost_band":"LOW","eta_days":14}.
	•	Cap blockers at max 5.

⸻

Step 3 — Emit Fix Packs (cluster Step-2 blockers)

Goal: Provide execution bundles. FP0 is the pre-commit gate.

Algorithm (simple)
	•	FP0 = every blocker mapped to must-fix criteria:
	•	any blocker from a GRAY pillar, or
	•	any blocker whose reason_codes include a must-fix set you define (e.g., DPIA_GAPS, CONTINGENCY_LOW, ETHICS_VAGUE).
	•	Remaining blockers → group by theme for FP1..FPn.

Output (JSON)

{
  "fix_packs": [
    {"id":"FP0","title":"Pre-Commit Gate","blocker_ids":["B1","B3"],"priority":"Immediate"},
    {"id":"FP1","title":"Governance Hardening","blocker_ids":["B2"],"priority":"High"}
  ]
}

Guardrails
	•	Every blocker_id must exist in Step 2.
	•	No new IDs allowed.

⸻

Step 4 — Emit Overall & Viability Summary (mechanical roll-up)

Computation rules (do these outside the LLM, in code)
	•	Overall color: start with the worst pillar color; upgrade one notch if FP0 fully covers all RED/GRAY blockers.
	•	Recommendation:
	•	Any RED pillar → PROCEED_WITH_CAUTION
(If FP0 neutralizes all RED/GRAY, use GO_IF_FP0.)
	•	All pillars GREEN/YELLOW → GO.
	•	what_flips_to_go: union of acceptance_tests from all blockers in FP0 (dedup, ≤5).

Output (JSON)

{
  "overall": {"score": 56, "color": "YELLOW", "confidence": "Medium"},
  "viability_summary": {
    "recommendation": "PROCEED_WITH_CAUTION",
    "why": [
      "Evidence gaps on data rights and budget contingency",
      "Integration risk with legacy IT"
    ],
    "what_flips_to_go": [
      "≥10% contingency approved",
      "Top-5 sources licensed + DPIAs"
    ]
  }
}


⸻

Validation & Auto-repair (run after each step)

Implement a tiny validator that:
	1.	Enum checks: drop unknown fields; coerce invalid enum values to GRAY/defaults.
	2.	Color/score sync: enforce color_to_score bands; if score missing, set to band midpoint.
	3.	Evidence gate: if color="GREEN" and evidence_todo not empty → downgrade to YELLOW.
	4.	ID integrity: verify blocker_ids exist; remove or flag extras.
	5.	Defaults: back-fill rom missing with {"cost_band":"LOW","eta_days":14}.

Pseudocode (Python):

def band_mid(color): return {"GREEN":85,"YELLOW":55,"RED":20}.get(color)
def validate_pillars(pillars):
    out=[]
    for p in pillars:
        if p["pillar"] not in PILLAR_ENUM: p["pillar"]="Rights_Legality"; p["color"]="GRAY"
        if p["color"]=="GREEN" and p.get("evidence_todo"): p["color"]="YELLOW"
        if "score" not in p or not in_band(p["score"], p["color"]):
            p["score"]=band_mid(p["color"])
        out.append(p)
    return out

def validate_blockers(blockers, pillars):
    valid_pillars={p["pillar"] for p in pillars}
    out=[]
    for b in blockers[:5]:
        if b["pillar"] not in valid_pillars: continue
        b.setdefault("rom", {"cost_band":"LOW","eta_days":14})
        out.append(b)
    return out


⸻

Prompt Snippets (for weaker LLMs)

General header (prepend to every step):

Output JSON only with exactly the fields listed.
Use only these enums: … Do not invent new fields.
If unsure, use GRAY or leave list empty.

Step 1 (pillars):

Emit pillars array with 4 items (one per pillar).
GREEN requires evidence_todo empty.

Step 2 (blockers):

Create ≤5 blockers only from pillars where color ≠ GREEN.
reason_codes must be a subset of the pillar’s reason_codes.

Step 3 (fix packs):

Build FP0 from blockers tied to GRAY pillars or reason codes in {DPIA_GAPS, CONTINGENCY_LOW, ETHICS_VAGUE}.
Then group remaining blockers into FP1..FPn by theme.

Step 4 (overall & summary):

Provide overall and viability_summary.
Do not restate blockers; derive what_flips_to_go from FP0 acceptance tests (≤5).

⸻

Interfaces (optional; keep loose for weaker models)

TypeScript (consuming side):

type Color = "GREEN" | "YELLOW" | "RED" | "GRAY";
type Pillar = "HumanStability" | "EconomicResilience" | "EcologicalIntegrity" | "Rights_Legality";
type CostBand = "LOW" | "MEDIUM" | "HIGH";

interface PillarItem {
  pillar: Pillar; color: Color; score?: number;
  reason_codes?: string[]; evidence_todo?: string[];
}

interface Blocker {
  id: string; pillar: Pillar; title: string;
  reason_codes?: string[]; acceptance_tests?: string[];
  artifacts_required?: string[]; owner?: string;
  rom?: { cost_band: CostBand; eta_days: number };
}


⸻

Design Rationale
	•	Pillars-first bounds the problem and gives deterministic derivations.
	•	Evidence-gated GREEN prevents “optimistic greenwashing.”
	•	Fix Packs with FP0 create a pre-commit gate that flips the recommendation without re-scoring everything.
	•	Roll-up in code (not in the LLM) keeps the final decision consistent and auditable.
