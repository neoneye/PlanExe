"""
Why long risk lists demotivate—and why 3–5 targeted recommendations boost morale

Purpose
-------
Turn a raw plan + candidate risks into a **decision-ready** package that users will
actually act on: a traffic-light dashboard, 3–5 prioritized “serious things,”
concrete Path-to-Green steps, Fix Packs, and an explicit GO / PROCEED_WITH_CAUTION / NO_GO.

Why this exists (tell it like it is)
------------------------------------
Long, unranked risk lists **demotivate**. They dilute signal, kill agency, and make
feasible projects look doomed. This module enforces focus:
- Show only the few fixes that move the needle (**3–5 max**).
- Make every fix **actionable** (owner, ETA, binary acceptance, artifacts).
- Mark unknowns **GRAY** and give data-collection tasks instead of screaming RED.

What this module provides
-------------------------
• **Schema (Pydantic)** — stable, render-friendly models:
  - PlanSnapshot, PillarSignals → inputs
  - PillarScore (with reason_codes, drivers, **evidence_todo** for GRAY)
  - SeriousThingCandidate → SeriousThing (ranked, with **quick_win_step_ids**)
  - Step (owner, acceptance, ETA, cost band, artifacts_required/attached)
  - FixPack (e.g., **Fix Pack 0** for quick wins and pre-commit must-dos)
  - ViabilityPayload / ViabilityReport / ViabilitySummary

• **Engine (ViabilityAssessor)** — assessor logic:
  - Pillar scoring from weighted signals; **GRAY** when evidence is thin.
  - **Actionability-first** selection: candidates without real steps are deprioritized.
  - Ranking by blocker_score and ROM; cap output to top 3–5.
  - **Quick wins** auto-tagged (ETA ≤14d, Low/Med cost) to build momentum.
  - **Evidence-gated GREEN**: no artifacts → cap at YELLOW; limit upgrades/run to
    prevent color-washing.
  - Fix Packs assembled automatically; **Fix Pack 0** pulls quick wins first.

• **System prompt (VIABILITY_SYSTEM_PROMPT)** — JSON-only instructions for the LLM
  that extracts candidates and synthesizes steps with strict acceptance tests,
  artifacts, quick-win bias, and GRAY handling for unknowns.

Key mechanics (no hand-waving)
------------------------------
- Pillar light mapping: 0–39 RED, 40–69 YELLOW, ≥70 GREEN (slightly adjusted by
  risk appetite). Low evidence → GRAY with **evidence_todo** checklist.
- Blocker score: impact × likelihood × dependency_centrality × (1 − solvability).
- ROM (Return on Mitigation): lift in success EV + risk reduction, normalized by
  (effort_days + direct_cost). Used to sort serious things after actionability.
- Ordering heuristics: local tie-breaking can use a hash of inputs, but **LLM outputs
  are inherently non-deterministic** and may vary across runs; do not rely on exact
  reproducibility.

Intended data flow
------------------
1) Upstream LLM (using VIABILITY_SYSTEM_PROMPT) emits ≤15 SeriousThingCandidate items
   with draft Steps.
2) ViabilityAssessor.assess() scores pillars, filters for actionability, ranks by
   blocker/ROM, tags quick wins, builds Fix Packs, gates GREENs by evidence, and
   returns a ViabilityReport with an explicit recommendation and “flip-to-GO”.

Quick start
-----------
    plan = PlanSnapshot(
        plan_title="Example",
        plan_text="…",
        pillars=["Financial","Operational","Market","Regulatory","Technical"],
        signals_by_pillar={ "Financial": PillarSignals(0.6,0.4,0.5,0.35,0.5,0.6) },
        candidates=[ ... from LLM ... ],
    )
    report = ViabilityAssessor().assess(plan)
    print(report.json(indent=2))

Design promises
---------------
- **Focus over frenzy**: never more than five serious things.
- **Evidence over optimism**: GREEN only with artifacts.
- **Momentum over despair**: quick wins surfaced and bundled first.
- **Clarity over noise**: unknowns are GRAY with concrete evidence tasks.

PROMPT> python -m planexe.plan.viability_assessor2
"""
