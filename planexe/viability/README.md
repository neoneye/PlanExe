# Why this exists

Big plans die from two things: cognitive overload and fuzzy follow-through. A 20-page plan and a 200-row risk register can make a team feel like everything is broken, so nothing moves. In reality, most plans are a few fixes away from viable—yet a long, undifferentiated list of risks is demotivating and stalls execution.

This protocol turns that mess into a short, decision-ready path:

- Contain the scope first. We score four CAS pillars so risk lives inside a clear frame, not as a free-for-all list.
- Convert weakness into action. Only non-green pillars produce 3–5 blockers, each with acceptance tests and artifacts—no hand-wavy “mitigate later.”
- Bundle execution. We group blockers into Fix Packs, with FP0 (Pre-Commit Gate) capturing the minimal, high-leverage work that flips the recommendation.
- Make the verdict mechanical. The final Overall & Summary is a roll-up driven by rules, not vibes: worst pillar status, upgraded only if FP0 closes the hard gaps.

It also solves a practical tooling problem: weaker LLMs struggle with rich schemas and will hallucinate fields. Splitting the task into four small steps with enums and guardrails keeps outputs stable, auditable, and easy to wire into CI/CD or dashboards.

Bottom line: this exists so teams don’t stall at the sight of a scary risk list. You get a tight set of must-do fixes, a clear pre-commit gate, and a repeatable verdict that tells you exactly what flips to GO.

⸻

## ViabilityAssessor — 4-Step, LLM-Friendly Protocol

A minimal, deterministic protocol that lets even a weaker LLM produce a useful viability assessment in four constrained steps:

```text
1) Pillars → 2) Blockers → 3) Fix Packs → 4) Overall & Summary
```

This README defines purpose, data flow, enums, JSON shapes, guardrails, and validator rules so a programmer can wire it up without prior context.

⸻

TL;DR
- Order matters: Do Pillars first (scope), then Blockers (derived), then Fix Packs (clusters), then Overall/Summary (mechanical roll-up).
- Keep outputs tiny, enum-driven, ID-stable.
- After each step, run a validator/auto-repair pass to fix status/score ranges, drop unknown fields, and back-fill defaults.

⸻

## Overall Purpose

The ViabilityAssessor turns a plan snapshot into a decision-ready assessment. It does this by:

- scoring the plan on four CAS pillars (HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality),
- turning weak pillars into a short list of blockers with acceptance tests and artifacts,
- bundling them into Fix Packs (with FP0 = Pre-Commit Gate),
- and producing an executive summary with a crisp recommendation and a small “what flips to GO” checklist.

Why four steps? Weak LLMs often fail strict schemas. Breaking the task into sequenced, derivation-based steps limits hallucination and keeps the JSON stable.

⸻

## Data Flow

```
Plan text ──> Step 1: PILLARS ──> Step 2: BLOCKERS ──> Step 3: FIX_PACKS ──> Step 4: OVERALL+SUMMARY
                     ▲                  ▲                      ▲
                     │                  │                      │
                 validator           validator               validator
```

- Each step consumes the prior step’s JSON and emits its own small JSON.
- Your backend runs a validator after each step (see “Validation & Auto-repair”).

⸻

## Step 0 — Constants & Enums (used in all steps)

PILLAR_ENUM
- HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality

STATUS_ENUM
- GREEN, YELLOW, RED, GRAY (unknown/insufficient info)

REASON_CODE_ENUM (small, stable set)
- Budget/Finance: CONTINGENCY_LOW, SINGLE_CUSTOMER, ALT_COST_UNKNOWN
- Rights/Compliance: DPIA_GAPS, LICENSE_GAPS, ABS_UNDEFINED, PERMIT_COMPLEXITY
- Tech/Integration: LEGACY_IT, INTEGRATION_RISK
- People/Adoption: TALENT_UNKNOWN, STAFF_AVERSION
- Climate/Ecology: CLOUD_CARBON_UNKNOWN, CLIMATE_UNQUANTIFIED, WATER_STRESS
- Biosecurity: BIOSECURITY_GAPS
- Governance/Ethics: ETHICS_VAGUE

COST_BAND_ENUM
- LOW, MEDIUM, HIGH
(You can map these to internal ROM ranges; e.g., LOW < 2 weeks or <$50k, etc.)

⸻

## Step 1 — Emit Pillars

Goal: Establish the authoritative scope and evidence gates. No blockers yet.

Input
- Plan synopsis (text)
- Pillar and reason-code enums

Output (JSON) — what the LLM must emit

```json
{
  "pillars": [
    {
      "pillar": "HumanStability",
      "status": "YELLOW",
      "score": 60,
      "reason_codes": ["STAFF_AVERSION"],
      "evidence_todo": ["Stakeholder survey baseline"]
    }
  ]
}
```

**Example (GREEN with strength rationale):**
```json
{
  "pillars": [
    {
      "pillar": "HumanStability",
      "status": "GREEN",
      "score": 85,
      "reason_codes": ["STAKEHOLDER_ALIGNMENT"],
      "evidence_todo": [],
      "strength_rationale": "Strong stakeholder buy-in evidenced by baseline survey ≥80% support"
    }
  ]
}
```
Note: The model outputs only the pillars array. No inline rule metadata.

The status mean:
- GREEN — Good to go.
You have solid evidence and no open critical unknowns. Proceed. Any remaining tasks are minor polish.
- YELLOW — Viable, but risks/unknowns exist.
There’s promise, but you’re missing proof on key points or see non-fatal risks. Proceed with caution and a focused checklist.
- RED — Not viable right now.
There’s a concrete blocker or negative evidence (legal, technical, economic) that stops execution until fixed. Pause or pivot.
- GRAY — Unknown / unassessed.
You don’t have enough information to judge. Don’t guess—add a “first measurement” task to get out of uncertainty.

Interpretation & validation (spec — not emitted by the LLM)
- Enumerations
- status ∈ {"GREEN","YELLOW","RED","GRAY"}
- pillar ∈ PILLAR_ENUM (unknown pillar names → treated as GRAY)
- reason_codes must come from the whitelist for that pillar (enforced downstream)
- Score bands
- GREEN: 70–100
- YELLOW: 40–69
- RED: 0–39
- GRAY: score must be null
- Validator behavior
- If status ≠ GRAY and score is missing or outside the band, the validator snaps to the band midpoint (GREEN:85, YELLOW:55, RED:20).
- If status == GRAY, score must be null (validator will null it if present).
- Unknown/unsupported pillar values are coerced to { "status":"GRAY", "score":null }.
- Evidence gating
- GREEN requires no open evidence items: evidence_todo must be empty.
- YELLOW/RED may have evidence_todo entries.
- Recommendation: For GRAY, include at least one concrete “first measurement” in evidence_todo to exit unknown.
- Formatting & determinism
- Emit plain JSON (no Markdown).
- Keep field names stable and lowercase with underscores for arrays.
- Order pillars consistently (e.g., the canonical PILLAR_ENUM order).
- `strength_rationale` (string, optional): Only for `status: "GREEN"`. A one-sentence justification of why the pillar is green (e.g., what evidence shows it is strong). Omit or set to `null` for non-GREEN statuses.

⸻


## Step 2 — Emit Blockers (derived from Step 1)

**Goal:** From the Step 1 plan, emit up to **5** concrete blockers the team must resolve.  

### Output contract (LLM → orchestrator)
The model returns a JSON object with a single field:

```python
# Pydantic schema
from pydantic import BaseModel, conlist

class BlockersPayload(BaseModel):
    blockers: conlist(BlockerItem, max_length=5)
```

Where `BlockerItem` is defined elsewhere in this spec. The list can be empty **only** if there are truly no blockers; otherwise return the top 1–5.

### Validation rules (applied by the orchestrator)
- `1 ≤ len(blockers) ≤ 5` (unless explicitly allowed to be 0).
- Each blocker must be specific, actionable, and clearly derived from Step 1.
- (Optional) If you choose to attribute blockers to pillars **per item**, add that inside `BlockerItem` (e.g., a `pillar` or `pillars` field) — **do not** reintroduce a top-level `source_pillars` key.

### Example (LLM output)
```json
{
  "blockers": [
    {
      "title": "Data processing throughput is below SLA",
      "description": "Ingest pipeline caps at ~3k msgs/s; target is 10k msgs/s for peak events.",
      "owner_hint": "Platform",
      "severity": "high"
    },
    {
      "title": "Consent text lacks DSR workflow coverage",
      "description": "No documented process for access/erasure requests; risks non-compliance in launch regions.",
      "owner_hint": "Legal/Privacy",
      "severity": "medium"
    }
  ]
}
```

## Step 3 — Emit Fix Packs (cluster Step-2 blockers)

Goal: Provide execution bundles. FP0 is the pre-commit gate.

Algorithm (simple)
- FP0 = every blocker mapped to must-fix criteria:
- any blocker from a GRAY pillar, or
- any blocker whose reason_codes include a must-fix set you define (e.g., DPIA_GAPS, CONTINGENCY_LOW, ETHICS_VAGUE).
- Remaining blockers → group by theme for FP1..FPn.

Output (JSON)

```json
{
  "fix_packs": [
    {"id":"FP0","title":"Pre-Commit Gate","blocker_ids":["B1","B3"],"priority":"Immediate"},
    {"id":"FP1","title":"Governance Hardening","blocker_ids":["B2"],"priority":"High"}
  ]
}
```

Guardrails
- Every blocker_id must exist in Step 2.
- No new IDs allowed.

⸻

## Step 4 — Emit Overall & Viability Summary (mechanical roll-up)

Computation rules (do these outside the LLM, in code)
- Overall status: start with the worst pillar status; upgrade one notch if FP0 fully covers all RED/GRAY blockers.
- Recommendation:
- Any RED pillar → PROCEED_WITH_CAUTION
(If FP0 neutralizes all RED/GRAY, use GO_IF_FP0.)
- All pillars GREEN/YELLOW → GO.
- what_flips_to_go: union of acceptance_tests from all blockers in FP0 (dedup, ≤5).

Output (JSON)

```json
{
  "overall": {"score": 56, "status": "YELLOW", "confidence": "Medium"},
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
```

⸻

Validation & Auto-repair (run after each step)

Implement a tiny validator that:
	1.	Enum checks: drop unknown fields; coerce invalid enum values to GRAY/defaults.
	2.	Status/score sync: enforce status_to_score bands; if score missing, set to band midpoint.
	3.	Evidence gate: if status="GREEN" and evidence_todo not empty → downgrade to YELLOW.
	4.	ID integrity: verify blocker_ids exist; remove or flag extras.
	5.	Defaults: back-fill rom missing with {"cost_band":"LOW","eta_days":14}.

Pseudocode (Python):

```python
def band_mid(status): return {"GREEN":85,"YELLOW":55,"RED":20}.get(status)
def validate_pillars(pillars):
    out=[]
    for p in pillars:
        if p["pillar"] not in PILLAR_ENUM: p["pillar"]="Rights_Legality"; p["status"]="GRAY"
        if p["status"]=="GREEN" and p.get("evidence_todo"): p["status"]="YELLOW"
        if "score" not in p or not in_band(p["score"], p["status"]):
            p["score"]=band_mid(p["status"])
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
```

⸻

## Prompt Snippets (for weaker LLMs)

General header (prepend to every step):

Output JSON only with exactly the fields listed.
Use only these enums: … Do not invent new fields.
If unsure, use GRAY or leave list empty.

Step 1 (pillars):

Emit pillars array with 4 items (one per pillar).
GREEN requires evidence_todo empty.

Step 2 (blockers):

Create ≤5 blockers only from pillars where status ≠ GREEN.
reason_codes must be a subset of the pillar’s reason_codes.

Step 3 (fix packs):

Build FP0 from blockers tied to GRAY pillars or reason codes in {DPIA_GAPS, CONTINGENCY_LOW, ETHICS_VAGUE}.
Then group remaining blockers into FP1..FPn by theme.

Step 4 (overall & summary):

Provide overall and viability_summary.
Do not restate blockers; derive what_flips_to_go from FP0 acceptance tests (≤5).

⸻

## Interfaces (optional; keep loose for weaker models)

TypeScript (consuming side):

```typescript
type Status = "GREEN" | "YELLOW" | "RED" | "GRAY";
type Pillar = "HumanStability" | "EconomicResilience" | "EcologicalIntegrity" | "Rights_Legality";
type CostBand = "LOW" | "MEDIUM" | "HIGH";

interface PillarItem {
  pillar: Pillar; status: Status; score?: number;
  reason_codes?: string[]; evidence_todo?: string[];
}

interface Blocker {
  id: string; pillar: Pillar; title: string;
  reason_codes?: string[]; acceptance_tests?: string[];
  artifacts_required?: string[]; owner?: string;
  rom?: { cost_band: CostBand; eta_days: number };
}
```


⸻

## Design Rationale
- Pillars-first bounds the problem and gives deterministic derivations.
- Evidence-gated GREEN prevents “optimistic greenwashing.”
- Fix Packs with FP0 create a pre-commit gate that flips the recommendation without re-scoring everything.
- Roll-up in code (not in the LLM) keeps the final decision consistent and auditable.
