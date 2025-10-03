/**
 * Author: Codex using GPT-5
 * Date: 2025-10-02T15:35:00Z
 * PURPOSE: Capture Sept 22-23 commit analysis, highlight high-risk changes, and recommend a stable rollback point for branch preservation
 * SRP and DRY check: Pass - standalone investigation summary; references existing commits/docs without duplicating logic
 */
# Sept 2025 Regression Investigation

## Overview
- Goal: identify which Sept 22-23 commits destabilized plan execution and produced OpenAI activity spikes.
- Baseline: mid-morning Sept 23 builds worked; later that day regressions appeared alongside emergency debugging commits.

## Timeline Highlights (Eastern Time)
- 2025-09-22 21:07 `61376b8` through 23:05 `a34e92b`: polishing + LLM system swap; pipeline still relied on subprocess execution and legacy progress parsing.
- 2025-09-23 00:00 `1b940c5` through 07:50 `4e3207b`: documentation and LlamaIndex compatibility; functionality intact.
- 2025-09-23 10:38 `03359a5`: docs handover—the last known "safe" commit before major runtime rewrites.
- 2025-09-23 14:18 `280cde7`: replaced progress parser with new `Terminal.tsx`, rewired API to stream raw Luigi stdout/stderr; large diff touching frontend + backend.
- 2025-09-23 14:39 `438db2a`: retry architecture overhaul, new `/stream-status`, and more API changes.
- 2025-09-23 15:16 `c3c282e`, 15:20 `f42ae6d`, 15:33 `e206124`: rapid-fire subprocess tweaks culminating in in-process Luigi execution.
- 2025-09-23 17:38 `36b11ea`, 17:44 `b26bd28`, 17:49 `b06c24c`, 17:49 `23666a0`: partial reverts/tweaks attempting to undo the in-process change but leaving new structures behind.

## High-Risk Changes Identified
- `280cde7` (Terminal + API streaming): removed deterministic progress parsing, introduced new SSE payloads, and changed README/env expectations. Coupled with `Terminal.tsx` client that assumes SSE stability.
- `438db2a` (retry refactor): adds `stream-status` polling loop, reuses refactored helper `_create_and_run_plan`; increases coupling between retries and streaming status.
- `e206124` (in-process Luigi execution): eliminates subprocess boundary; later reverts (`36b11ea`, `23666a0`) undo portions but code churn remains.
- `b26bd28` and `b06c24c`: introduce emergency handling, new documentation (`docs/EMERGENCY-DIAGNOSIS-AND-FIX-PLAN.md`), plus `test_plan_creation.py` which hits the API and can drive OpenAI usage.
- `test_plan_creation.py`: POSTs to `http://localhost:8000/api/plans` with real LLM selections; running it can generate OpenAI traffic even if backend should be on 8080.

## Recommendation
- Use commit `03359a5` (2025-09-23 10:38) as the last stable reference: pre-Terminal rewrite, pre-in-process execution experiments, simple subprocess model intact.
- If you specifically need the "morning" state prior to handover docs, use commit `4e3207b` (2025-09-23 07:50) which contains LlamaIndex compatibility but predates larger architectural changes.
- Create branch `Sept23` from the chosen commit (likely `4e3207b` for morning baseline) to compare against current `ui` state.

## Next Steps
1. `git branch Sept23 4e3207b` to snapshot the morning state.
2. `git push -u origin Sept23` for GitHub comparison.
3. Use `git diff Sept23..ui` or GitHub compare view to review regressions.
4. Remove or gate `test_plan_creation.py` before production if automated jobs trigger unintended LLM calls.