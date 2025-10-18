# What this is / isn't

- **This is** the working spec for the ViabilityAssessor protocol: how domains, blockers, fix packs, and the overall verdict hang together so an LLM+validator pipeline can stay deterministic.
- **This is** guidance for engineers wiring PlanExe components or weaker LLMs into the viability workflow—expect JSON shapes, enums, and guardrails you can drop straight into code.
- **This isn't** a generic risk-management playbook, human-readable report, or policy doc; it assumes you are instrumenting software and already have domain experts feeding the inputs.

# Why this exists

Big plans die from two things: cognitive overload and fuzzy follow-through. A 20-page plan and a 200-row risk register can make a team feel like everything is broken, so nothing moves. In reality, most plans are a few fixes away from viable—yet a long, undifferentiated list of risks is demotivating and stalls execution.

This protocol turns that mess into a short, decision-ready path:

- Contain the scope first. We score four CAS domains so risk lives inside a clear frame, not as a free-for-all list.
- Convert weakness into action. Only non-green domains produce 3–5 blockers, each with acceptance tests and artifacts—no hand-wavy “mitigate later.”
- Bundle execution. We group blockers into Fix Packs, with FP0 (Pre-Commit Gate) capturing the minimal, high-leverage work that flips the recommendation.
- Make the verdict mechanical. The final Overall & Summary is a roll-up driven by rules, not vibes: worst domain status, upgraded only if FP0 closes the hard gaps.

It also solves a practical tooling problem: weaker LLMs struggle with rich schemas and will hallucinate fields. Splitting the task into four small steps with enums and guardrails keeps outputs stable, auditable, and easy to wire into CI/CD or dashboards.

Bottom line: this exists so teams don’t stall at the sight of a scary risk list. You get a tight set of must-do fixes, a clear pre-commit gate, and a repeatable verdict that tells you exactly what flips to GO.

⸻

## ViabilityAssessor — 4-Step, LLM-Friendly Protocol

A minimal, deterministic protocol that lets even a weaker LLM produce a useful viability assessment in four constrained steps:

```text
1) Domains → 2) Blockers → 3) Fix Packs → 4) Overall & Summary
```

This README defines purpose, data flow, enums, JSON shapes, guardrails, and validator rules so a programmer can wire it up without prior context.

⸻

TL;DR
- Order matters: Do Domains first (scope), then Blockers (derived), then Fix Packs (clusters), then Overall/Summary (mechanical roll-up).
- Keep outputs tiny, enum-driven, ID-stable.
- After each step, run a validator/auto-repair pass to fix status/score ranges, drop unknown fields, and back-fill defaults.

### CAS Domains — the Viability Backbone

The four domains we track come from complex adaptive systems (CAS) thinking: a plan only sticks if it can adapt within intertwined human, economic, environmental, and legal ecosystems. The canonical enum lives in `planexe/viability/model_domain.py`, but the intuition is:
- **Human Stability** — People readiness, stakeholder alignment, operating model, change management.
- **Economic Resilience** — Funding and runway, unit economics, supplier dependence, contingency buffers.
- **Ecological Integrity** — Environmental baselines, resource impacts, mitigation evidence, sustainability claims.
- **Rights & Legality** — Regulatory compliance, data/ethics posture, permits, governance safeguards.

Keeping the assessment anchored to these four domains gives every downstream step (blockers, fix packs, overall verdict) a common language and CAS-informed scope.

⸻

## Overall Purpose

The ViabilityAssessor turns a plan snapshot into a decision-ready assessment. It does this by:

- scoring the plan on four CAS domains (HumanStability, EconomicResilience, EcologicalIntegrity, Rights_Legality),
- turning weak domains into a short list of blockers with acceptance tests and artifacts,
- bundling them into Fix Packs (with FP0 = Pre-Commit Gate),
- and producing an executive summary with a crisp recommendation and a small “what flips to GO” checklist.

Why four steps? Weak LLMs often fail strict schemas. Breaking the task into sequenced, derivation-based steps limits hallucination and keeps the JSON stable.

## Design Rationale
- Domains-first bounds the problem and gives deterministic derivations.
- Evidence-gated GREEN prevents “optimistic greenwashing.”
- Fix Packs with FP0 create a pre-commit gate that flips the recommendation without re-scoring everything.
- Roll-up in code (not in the LLM) keeps the final decision consistent and auditable.

## Viability Scoring — Likert, Rule‑Based (No Hidden Weights)

The system is **simple, auditable, and deterministic**. Every downgrade is tied to an explicit rule and logged.


### Core Idea

Each domain is assessed on **three factors**, each on a 1–5 Likert scale (1=bad, 5=good):

- **evidence** — strength of supporting docs/artifacts

- **risk** — residual risk posture after mitigations

- **fit** — alignment/coherence with the domain’s aims


The model (LLM) proposes **reason_codes** and mentions **artifacts**; the **scoring is pure Python** and rule-based. No YAML weights; no hidden multipliers.

### Factor Rubric (make the mapping non-arguable)

| Domain               | evidence (1–5) — “Do we have proof?”                           | risk (1–5) — “Residual downside?”                         | fit (1–5) — “Does this design address the domain’s goals?” |
|----------------------|-----------------------------------------------------------------|-----------------------------------------------------------|------------------------------------------------------------|
| HumanStability       | Org charts, RACI, training plans, comms plan                    | Stakeholder conflict, turnover risk, change fatigue       | Governance clarity, incentives aligned to outcomes         |
| EconomicResilience   | Budget, unit economics, funding letters, signed contracts       | Sensitivity to shocks, supplier concentration, FX/rate    | Cost/benefit logic, ramp plan realism, buffer integration  |
| EcologicalIntegrity  | EIA/EIS, baseline studies, third-party audits                   | Biodiversity/water/air risks after mitigations            | Mitigation hierarchy applied, circularity/waste design     |
| Rights_Legality      | DPIA, legal opinions, permits/licenses                          | Compliance failure, infosec/privacy breach, sanctions     | Ethical framework, data rights alignment, due process      |

### Status Derivation (Deterministic)

- If **any factor ≤ 2** → **RED**

- Else if **worst factor == 3** → **YELLOW**

- Else (all 4–5) → **GREEN**

- Missing factors → **GRAY**


**Overall status** is the **worst domain**. Optionally, we compute a display-only number: 

`overall_likert = mean(domain_avg_likert)` for dashboards that want a single roll-up indicator.


### How rules work (transparent caps)

Rules map **reason_codes → factor caps** (and are gated by artifacts). Examples:

- **HumanStability**: `GOVERNANCE_WEAK → fit ≤ 2`; `STAKEHOLDER_CONFLICT → risk ≤ 2`; `CHANGE_MGMT_GAPS → evidence ≤ 2` unless a `Change_Mgmt_Plan` artifact exists.

- **EconomicResilience**: `CONTINGENCY_LOW → risk ≤ 2` until **≥10% contingency** is evidenced; `UNIT_ECON_UNKNOWN → evidence ≤ 2`; `SUPPLIER_CONCENTRATION → risk ≤ 3`.

- **EcologicalIntegrity**: `EIA_MISSING → evidence = 1` (hard stop); `BIODIVERSITY_RISK_UNSET → risk ≤ 2`; `WASTE_MANAGEMENT_GAPS → fit ≤ 3`.

- **Rights_Legality**: `DPIA_GAPS → evidence ≤ 2` until **DPIA** artifact present; `INFOSEC_GAPS → risk ≤ 3`; `ETHICS_VAGUE → fit ≤ 3`.


Each applied rule is **logged** (e.g., `EIA_MISSING: evidence 3→1 (hard stop)`), making audits trivial.


### “What flips to GO” becomes measurable

Fix-packs/actions add artifacts or close reason codes → we **re-score** and show the **Δ uplift**.

Example in the report:

- **DPIA completed** → Rights_Legality.evidence `2→4` → domain avg +0.67 → overall +Δ.

- **≥10% contingency approved** → EconomicResilience.risk `2→4` → domain avg +0.67 → overall +Δ.


### Stop Rules & Governance

- Certain codes (e.g., `EIA_MISSING`) enforce **hard RED**. If any domain is RED, default **Recommendation = PAUSE** unless an explicit override flag is set.


### Integration (minimal changes)

1) Add a small scorer module (see `likert_score.py`).

2) In `domains_assessment.py`, **do not accept LLM status**; call the scorer with `reason_codes` and detected artifacts; overwrite `status` and `factors`.

3) In `overall_summary.py`, compute overall via **worst-win** + optional Likert number; set **PAUSE** on RED.

4) In `fixpack.py`, simulate actions by adding artifacts/removing codes and re-score to compute **uplift**; sort by uplift per ROM day.


### Why this is better

- **Auditable**: Every number is justified by a rule you can print.

- **Deterministic**: Same input → same score. No LLM vibes.

- **Maintainable**: Add/modify a rule in Python, not a weight stew in YAML.

- **LLM-friendly**: The model only proposes structured facts (codes/artifacts). Math lives in code.

- **Safe defaults**: Worst-domain wins; hard stops wire directly to governance.


### Example (pseudo-code)

```python
from likert_score import DomainInput, score_domain, score_overall

p = DomainInput(
    domain="EcologicalIntegrity",
    reason_codes=["EIA_MISSING", "BIODIVERSITY_RISK_UNSET"],

    provided_artifacts=[],
)

res = score_domain(p)

# res.status == "RED"; res.factors.evidence == 1

```


### Tests to keep us honest

1. `EIA_MISSING` sets `evidence=1` (hard).

2. Artifact gating: with `DPIA_GAPS` + `DPIA` artifact, the cap does **not** apply.

3. Status mapping: any factor ≤2 ⇒ RED.

4. Overall: any domain RED ⇒ overall RED.

5. Monotonicity: adding an artifact never lowers a factor.

With the philosophy and scoring locked in, the rest of this README dives into the data flow, JSON payloads, and validator rules that make it executable.

⸻

## Data Flow

```
Plan text ──> Step 1: DOMAINS ──> Step 2: BLOCKERS ──> Step 3: FIX_PACKS ──> Step 4: OVERALL+SUMMARY
                     ▲                  ▲                      ▲
                     │                  │                      │
                 validator           validator               validator
```

- Each step consumes the prior step’s JSON and emits its own small JSON.
- Your backend runs a validator after each step (see “Validation & Auto-repair”).

⸻

## Step 0 — Constants & Enums (used in all steps)

DOMAIN_ENUM
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

## Step 1 — Emit Domains

Goal: Establish the authoritative scope and evidence gates. No blockers yet.

Input
- Plan synopsis (text)
- Domain and reason-code enums

Output (JSON) — what the LLM must emit

```json
{
  "domains": [
    {
      "domain": "HumanStability",
      "status": "YELLOW",
      "score": {
        "evidence": 2,
        "risk": 3,
        "fit": 3
      },
      "reason_codes": ["STAFF_AVERSION"],
      "evidence_todo": ["Stakeholder survey baseline"]
    }
  ]
}
```

The nested `score` object must follow `DomainLikertScoreSchema` (per-factor Likert 1–5).

**Example (GREEN with strength rationale):**
```json
{
  "domains": [
    {
      "domain": "HumanStability",
      "status": "GREEN",
      "score": {
        "evidence": 4,
        "risk": 4,
        "fit": 5
      },
      "reason_codes": ["STAKEHOLDER_ALIGNMENT"],
      "evidence_todo": [],
      "strength_rationale": "Strong stakeholder buy-in evidenced by baseline survey ≥80% support"
    }
  ]
}
```
Note: The model outputs only the domains array. No inline rule metadata.

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
- domain ∈ DOMAIN_ENUM (unknown domain names → treated as GRAY)
- reason_codes must come from the whitelist for that domain (enforced downstream)
- Likert factors (`score` follows `DomainLikertScoreSchema` from `domains_assessment.py`)
  - Factors are integers 1–5 (or null when unknown) for `evidence`, `risk`, `fit`.
  - Status is deterministic: any factor ≤2 ⇒ RED; else worst factor ==3 ⇒ YELLOW; all factors ≥4 ⇒ GREEN; missing factors ⇒ GRAY.
- Validator behavior
- Normalizes the per-factor Likert scores (clamps 1–5, fills defaults per status).
- Aligns status with the factor rule.
- If status == GRAY, factors are nulled out.
- Unknown/unsupported domain values are coerced to { "status":"GRAY", "score":{"evidence":null,"risk":null,"fit":null} }.
- Evidence gating
- GREEN requires no open evidence items: evidence_todo must be empty.
- YELLOW/RED may have evidence_todo entries.
- Recommendation: For GRAY, include at least one concrete “first measurement” in evidence_todo to exit unknown.
- Formatting & determinism
- Emit plain JSON (no Markdown).
- Keep field names stable and lowercase with underscores for arrays.
- Order domains consistently (e.g., the canonical DOMAIN_ENUM order).
- `strength_rationale` (string, optional): Only for `status: "GREEN"`. A one-sentence justification of why the domain is green (e.g., what evidence shows it is strong). Omit or set to `null` for non-GREEN statuses.

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
- (Optional) If you choose to attribute blockers to domains **per item**, add that inside `BlockerItem` (e.g., a `domain` or `domains` field) — **do not** reintroduce a top-level `source_domains` key.

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
- any blocker from a GRAY domain, or
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

Computation rules

Overall status
- Compute the baseline as the worst (most severe) domain status using this order:
RED > GRAY > YELLOW > GREEN.
- If and only if every RED/GRAY finding is covered by FP0 (red_gray_covered=True), upgrade the baseline one notch using your STATUS_UPGRADE_MAP. (Do not upgrade more than once.)

Recommendation

Return a RecommendationEnum:
- HOLD — At least one RED finding exists and it is not covered by FP0. Do not proceed.
- GO_IF_FP0 — There are RED and/or GRAY findings, but all of them are covered by FP0. Proceed only if FP0 is accepted and treated as a gate (owned, time-bound tasks with clear acceptance criteria).
- PROCEED_WITH_CAUTION — No RED remains, but at least one GRAY (unknown/insufficient signal) exists that is not covered by FP0.
- GO — No RED/GRAY findings remain (i.e., all domains are GREEN/YELLOW).

What does “covered by FP0” mean?
- The finding is explicitly addressed by an FP0 task that has:
- a clear owner,
- a near-term target date,
- acceptance criteria that, when met, neutralize the risk/unknown.

red_gray_covered=True means all RED and GRAY items are covered as above. If there are no RED/GRAY items, the flag is irrelevant.

what_flips_to_go
- Build as the deduplicated union of acceptance_tests from all FP0 blockers, capped at ≤ 5 items.

Output (JSON)

```json
{
  "overall": { "status": "GRAY", "confidence": "Medium" },
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

Notes:
- In this example, at least one GRAY exists and is not covered by FP0, so the recommendation is PROCEED_WITH_CAUTION and the overall baseline stays GRAY (no FP0 upgrade applies).
- When serializing, emit the enum’s string value (e.g., RecommendationEnum.GO.value == "GO").

⸻

Validation & Auto-repair (run after each step)

Implement a tiny validator that:
	1.	Enum checks: drop unknown fields; coerce invalid enum values to GRAY/defaults.
	2.	Status/factor sync: normalize to the Likert schema (1–5) and derive status from factors.
	3.	Evidence gate: if status="GREEN" and evidence_todo not empty → downgrade to YELLOW (and re-sync factors).
	4.	ID integrity: verify blocker_ids exist; remove or flag extras.
	5.	Defaults: back-fill rom missing with {"cost_band":"LOW","eta_days":14}.

Pseudocode (Python):

```python
LIKERT_KEYS = ("evidence", "risk", "fit")

def normalize_likert(score):
    factors = {key: None for key in LIKERT_KEYS}
    if isinstance(score, dict):
        for key in LIKERT_KEYS:
            value = score.get(key)
            if isinstance(value, (int, float)):
                clamped = max(1, min(5, int(value)))
                factors[key] = clamped
    return factors

def derive_status(factors):
    values = [factors[key] for key in LIKERT_KEYS if factors[key] is not None]
    if len(values) < len(LIKERT_KEYS):
        return "GRAY"
    if min(values) <= 2:
        return "RED"
    if min(values) == 3:
        return "YELLOW"
    return "GREEN"

def validate_domains(domains):
    out=[]
    for p in domains:
        if p["domain"] not in DOMAIN_ENUM: p["domain"]="Rights_Legality"; p["status"]="GRAY"
        if p["status"]=="GREEN" and p.get("evidence_todo"): p["status"]="YELLOW"
        p["score"]=normalize_likert(p.get("score", {}))
        p["status"]=derive_status(p["score"])
        if p["status"]=="GRAY":
            for key in LIKERT_KEYS:
                p["score"][key]=None
        out.append(p)
    return out

def validate_blockers(blockers, domains):
    valid_domains={p["domain"] for p in domains}
    out=[]
    for b in blockers[:5]:
        if b["domain"] not in valid_domains: continue
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

Step 1 (domains):

Emit domains array with 4 items (one per domain).
GREEN requires evidence_todo empty.

Step 2 (blockers):

Create ≤5 blockers only from domains where status ≠ GREEN.
reason_codes must be a subset of the domain’s reason_codes.

Step 3 (fix packs):

Build FP0 from blockers tied to GRAY domains or reason codes in {DPIA_GAPS, CONTINGENCY_LOW, ETHICS_VAGUE}.
Then group remaining blockers into FP1..FPn by theme.

Step 4 (overall & summary):

Provide overall and viability_summary.
Do not restate blockers; derive what_flips_to_go from FP0 acceptance tests (≤5).

⸻

## Interfaces (optional; keep loose for weaker models)

TypeScript (consuming side):

```typescript
type Status = "GREEN" | "YELLOW" | "RED" | "GRAY";
type Domain = "HumanStability" | "EconomicResilience" | "EcologicalIntegrity" | "Rights_Legality";
type CostBand = "LOW" | "MEDIUM" | "HIGH";

interface DomainLikertScore {
  evidence?: number | null;
  risk?: number | null;
  fit?: number | null;
}

interface DomainItem {
  domain: Domain; status: Status; score?: DomainLikertScore;
  reason_codes?: string[]; evidence_todo?: string[];
}

interface Blocker {
  id: string; domain: Domain; title: string;
  reason_codes?: string[]; acceptance_tests?: string[];
  artifacts_required?: string[]; owner?: string;
  rom?: { cost_band: CostBand; eta_days: number };
}
```


⸻
