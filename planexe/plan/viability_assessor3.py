"""
Why long risk lists demotivate—and why 3–5 targeted recommendations boost morale

Purpose (blunt version)
-----------------------
Long, unranked risk lists **demotivate**. They dilute signal, kill agency, and make
feasible projects look doomed. This module converts a raw plan + candidate risks into
a **decision-ready** package people will actually act on:
- A traffic-light dashboard across key pillars
- **3–5** prioritized “serious things” (not 20+ hand-wavy risks)
- Concrete Path-to-Green steps (owner, ETA, binary acceptance, artifacts)
- Fix Packs to batch work (e.g., “Fix Pack 0” quick wins)
- An explicit **GO / PROCEED_WITH_CAUTION / NO_GO** recommendation

What’s in this file
-------------------
• **Schema (Pydantic)** – Stable, typed contracts between LLM and engine:
  - `PlanSnapshot`, `PillarSignals` (inputs)
  - `PillarScore` (with `reason_codes`, `drivers`, and `evidence_todo` for GRAY)
  - `SeriousThingCandidate` → `SeriousThing` (with `quick_win_step_ids`)
  - `Step` (owner, acceptance, ETA, cost band, artifacts_required/attached)
  - `FixPack` (themed, prioritized bundles of steps)
  - `ViabilityPayload` / `ViabilityReport` / `ViabilitySummary`

• **Engine (`ViabilityAssessor`)** – Opinionated selection & gating:
  - Scores pillars; marks **GRAY** when evidence is thin and proposes `evidence_todo`
  - Filters for **actionability first** (no owner/acceptance/ETA → deprioritize)
  - Ranks by blocker score and ROM; caps list to the top **3–5**
  - Auto-tags **quick wins** (ETA ≤ 14d, Low/Med cost) to build momentum
  - **Evidence-gated GREEN** (no artifacts → cap at YELLOW; limited upgrades/run)
  - Assembles Fix Packs (Fix Pack 0 pulls quick wins & pre-commit must-dos)

• **System prompt (`VIABILITY_SYSTEM_PROMPT`)** – JSON-only instructions for the LLM
  to extract candidates and synthesize steps with strict acceptance tests, artifacts,
  quick-win bias, and GRAY handling for unknowns.
  **Note:** output quality depends heavily on the LLM and ongoing prompt refinement.

Key mechanics (short and concrete)
----------------------------------
- **Pillar lights:** map a 0–100 score → RED (0–39), YELLOW (40–69), GREEN (≥70),
  adjusted slightly by **risk appetite**. Low evidence → **GRAY** with `evidence_todo`.
- **Blocker score (selection):**
      impact × likelihood × dependency_centrality × (1 − solvability)
  (Weights can be added via config if a domain needs different emphasis.)
- **ROM (Return on Mitigation):**
      (ΔP_success × Project_EV + Σ risk_reduction_i × impact_i) / (effort_days + direct_cost)
  Used to sort serious things (after actionability).
- **Anti-greenwashing:** GREEN requires artifacts; cap color upgrades per run to avoid
  cosmetic flips.
- **FixPack definition & lifecycle:** a themed, prioritized bundle of Steps intended
  to be executed as a unit (e.g., quick wins; regulatory hardening). By default,
  **Fix Pack 0** is a pre-commit gate; others map to pre-MVP / post-MVP phases.

Calibration & reality checks
----------------------------
- Thresholds and weights here are **starting points**. Calibrate against a benchmark
  set of plans; instrument and adjust in `EngineConfig`.
- LLM outputs are **non-deterministic**. Ordering heuristics and tie-breaks may use
  hashes for stability within a run, but **exact reproducibility is not guaranteed**.
- Expect to iterate on the prompt, acceptance tests, and artifact definitions as you
  see real plans.

Intended flow
-------------
1) Upstream LLM (using `VIABILITY_SYSTEM_PROMPT`) emits ≤15 `SeriousThingCandidate`s
   with draft `Step`s.
2) `ViabilityAssessor.assess()` scores pillars, filters/ranks candidates, tags quick
   wins, builds Fix Packs, gates GREENs by evidence, and returns a `ViabilityReport`
   with a recommendation and “what flips to GO”.

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

Out of scope (by design)
------------------------
Deep financial/risk modeling (plug your EV/loss models), UI rendering, and any claim
of deterministic LLM behavior.

PROMPT> python -m planexe.plan.viability_assessor3
"""
