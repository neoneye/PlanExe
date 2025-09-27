"""
Why long risk lists demotivate—and why 3–5 targeted recommendations boost morale

Purpose (blunt)
---------------
Long, unranked risk lists **demotivate**. They dilute signal, kill agency, and make
feasible projects look doomed. This module converts a raw plan + candidate risks into a
**decision-ready** package people will actually act on:
- A traffic-light dashboard across key pillars
- **3–5** prioritized “serious things” (not 20+ vague risks)
- Concrete Path-to-Green steps (owner, ETA, binary acceptance, artifacts)
- Fix Packs to batch work (e.g., **Fix Pack 0** for quick wins / pre-commit gate)
- Explicit **GO / PROCEED_WITH_CAUTION / NO_GO** recommendation

What’s in this file
-------------------
• **Schema (Pydantic)** — stable, typed contracts between LLM and engine:
  - `PlanSnapshot`, `PillarSignals` (inputs; includes `risk_appetite`)
  - `PillarScore` (with `reason_codes`, `drivers`, and `evidence_todo` for GRAY)
  - `SeriousThingCandidate` → `SeriousThing` (with `quick_win_step_ids`)
  - `Step` (owner, acceptance, ETA, cost band, artifacts_required/attached)
  - `FixPack` (themed, prioritized bundle executed as a unit of work)
  - `ViabilityPayload` / `ViabilityReport` / `ViabilitySummary`
  - **Optional metadata (recommended):** `prompt_id`, `config_version`,
    and `rom_dependencies` (e.g., ["FinancialModel v2.1","RiskRegister v4"])

• **Engine (`ViabilityAssessor`)** — opinionated selection & gating:
  - Scores pillars; marks **GRAY** when evidence is thin and proposes `evidence_todo`
  - Filters for **actionability first** (no owner/acceptance/ETA → deprioritize)
  - Ranks by **blocker score** and **ROM**; caps list to the top **3–5**
  - Auto-tags **quick wins** (ETA ≤ 14d, Low/Med cost) to build momentum
  - **Evidence-gated GREEN** (no artifacts → cap at YELLOW; limited upgrades/run)
  - Assembles Fix Packs (Fix Pack 0 = quick wins & pre-commit must-dos)

• **System prompt (`VIABILITY_SYSTEM_PROMPT`)** — JSON-only instructions for the LLM
  to extract candidates and synthesize steps with strict acceptance tests, artifacts,
  quick-win bias, and GRAY handling for unknowns.
  **Reality note:** LLM output quality is a major dependency; keep the prompt versioned,
  tested on a gold set, and evolve it deliberately.

Key mechanics (short, concrete, auditable)
------------------------------------------
- **Pillar lights:** map a 0–100 score → RED (0–39), YELLOW (40–69), GREEN (≥70),
  slightly adjusted by **risk appetite** (`conservative` tightens thresholds; `aggressive`
  relaxes them). Low evidence → **GRAY** with `evidence_todo`.

- **Blocker score (selection):**
      impact × likelihood × dependency_centrality × (1 − solvability)
  *Micro-example (ethics risk like “regulatory capture”):*
      0.9 (impact) × 0.8 (likelihood) × 0.7 (centrality) × (1−0.4) = **0.3024**.
  (Domain weights/normalization can be introduced via `EngineConfig`.)

- **ROM (Return on Mitigation):**
      (ΔP_success × Project_EV + Σ risk_reduction_i × impact_i) / (effort_days + direct_cost)
  Used to sort serious things **after** actionability checks.
  **Input dependency:** ROM quality depends on upstream EV/risk models; garbage in → garbage out.

- **Anti-greenwashing:** GREEN requires artifacts; cap color upgrades per run to prevent
  cosmetic flips. Partial evidence remains **YELLOW** until all required artifacts are present.

- **FixPack lifecycle:** a themed bundle executed end-to-end (e.g., Quick Wins, Regulatory
  Hardening). **Fix Pack 0** acts as a pre-commit gate.

Calibration & reality checks
----------------------------
- Thresholds and weights here are **starting points**. Calibrate on a benchmark set of plans;
  instrument and tune via `EngineConfig`.
- LLM outputs are **non-deterministic**. Hash-based tie-breakers can steady ordering within a run,
  but exact reproducibility is not guaranteed.
- **Phased rollout:** ship **V1** ranking by blocker score only; add ROM once EV/risk inputs are trustworthy.

Edge cases & safeguards
-----------------------
- **All GRAY pillars:** switch to **Gather-Data Mode** (Fix Pack 0 populated with `evidence_todo`);
  default recommendation = **PROCEED_WITH_CAUTION**.
- **<3 actionable candidates:** include best GRAY-resolver tasks as provisional steps to reach
  actionable state; keep total ≤5.
- **Conflicting fixes or trade-offs:** flag in `ViabilitySummary` with a short trade-off note
  (e.g., “Budget ↑ vs. timeline ↑”); prefer higher ROM unless domain rules state otherwise.
- **User overrides:** allow a caller to pin/include a SeriousThing; still apply evidence gating.

Governance & versioning (operational discipline)
------------------------------------------------
- Treat `EngineConfig` and the prompt as **versioned, review-gated assets**:
  - Bump `config_version` on parameter changes; require a calibration report in PRs.
  - Keep prompts under `prompts/` with semantic versions and a gold test set.
  - Record `prompt_id`, `config_version`, and `rom_dependencies` in report metadata.

Intended flow
-------------
1) Upstream LLM (using `VIABILITY_SYSTEM_PROMPT`) emits ≤15 `SeriousThingCandidate`s with draft `Step`s.
2) `ViabilityAssessor.assess()` scores pillars, filters/ranks candidates, tags quick wins, builds Fix Packs,
   gates GREENs by evidence, and returns a `ViabilityReport` with a recommendation and explicit “what flips to GO”.

Design promises
---------------
- **Focus over frenzy:** never more than five serious things.
- **Evidence over optimism:** GREEN only with artifacts.
- **Momentum over despair:** quick wins surfaced and bundled first.
- **Clarity over noise:** unknowns are **GRAY** with concrete evidence tasks.

Quick start
-----------
    plan = PlanSnapshot(...); report = ViabilityAssessor().assess(plan)
    print(report.json(indent=2))

Tests to run (minimum)
----------------------
- GRAY-only inputs → Gather-Data Mode with Fix Pack 0 evidence tasks.
- Mixed evidence → no GREENs without artifacts; YELLOW upgrades after attaching proofs.
- Sparse candidates (<3) → pulls GRAY resolvers, still ≤5 items total.
- “Pinned” candidate respected even if low ROM; trade-off note emitted.

PROMPT> python -m planexe.plan.viability_assessor5
"""
