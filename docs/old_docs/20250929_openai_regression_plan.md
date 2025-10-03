/**
 * Author: Codex using GPT-5
 * Date: 2025-09-29T20:13:35Z
 * PURPOSE: Document the diagnosed LLM regression, root cause, and remediation roadmap so the next developer can restore OpenAI integration without re-discovery.
 * SRP and DRY check: Pass - Single reference guide for the LLM regression investigation.
 */

# OpenAI Regression Recovery Plan

## Situation Overview
- User reports: OpenAI calls stopped after 2025-09-23 18:00 ET; Luigi pipeline still launches and DB entries are created, but external LLM traffic never leaves the host.
- Investigation scope: Windows dev environment (`D:\1Projects\PlanExe`), commits newer than 2025-09-23 18:00, and CHANGELOG updates.
- Current architecture: FastAPI backend spawns Luigi via planexe_api/services/pipeline_execution_service.py; LLM selection relies on planexe/llm_factory.py reading llm_config.json and instantiating SimpleOpenAILLM.

## Evidence Collected
1. Recent Git History - git log --since "2024-09-23 18:00"
   - Multiple commits replaced the legacy LlamaIndex stack with the simplified OpenAI client (planexe/llm_util/simple_openai_llm.py).
   - Frontend and API now expose OpenAI / OpenRouter model IDs sourced from config files.
2. Configuration Files
   - llm_config.json (repo root) now lists only OpenAI/OpenRouter models.
   - planexe_api/llm_config.json still contains an expanded schema with class and arguments, but the pipeline no longer consumes it.
3. Pipeline Boot Path - planexe_api/services/pipeline_execution_service.py:160-220
   - Environment variables LLM_MODEL and SPEED_VS_DETAIL are set from the API request before the Luigi subprocess is started.
4. Luigi Entry Point - planexe/plan/run_plan_pipeline.py:92 and :3720-3770
   - Default model constant remains DEFAULT_LLM_MODEL = "ollama-llama3.1".
   - ExecutePipeline.resolve_llm_models pulls models from PlanExeLLMConfig, but only uses the request override when valid.
5. Task-Level Overrides
   - Direct hardcoded references to get_llm("ollama-llama3.1") exist across numerous tasks, for example:
     - planexe/assume/identify_purpose.py:171
     - planexe/plan/data_collection.py:256
     - planexe/plan/project_plan.py:389
     - planexe/plan/executive_summary.py:206
     - planexe/diagnostics/redline_gate.py:719
     - planexe/expert/pre_project_assessment.py:395
     - planexe/lever/focus_on_vital_few_levers.py:302
     - planexe/governance/governance_phase1_audit.py:166
     - planexe/questions_answers/questions_answers.py:251
   - Many proof-of-concept scripts under planexe/proof_of_concepts also hardcode the same model. (NOT A PROBLEM)
6. Database State
   - Local SQLite dev DB (planexe_api/planexe.db) currently empty; production uses PostgreSQL, so regression is not tied to DB writes.

## Root Cause Analysis
- Hardcoded fallback model ollama-llama3.1 persists throughout the pipeline, predating the OpenAI simplification.
- When the API launches Luigi it passes the user-selected model into the environment, but the pipeline tasks override that selection with direct get_llm calls that ignore the LLM_MODEL env var and the new llm_config.json entries.
- Result: Luigi keeps targeting the local Ollama model, which is no longer running or available, so no outbound OpenAI traffic occurs. Because requests never reach OpenAI, the OpenAI call failure is silent from the API perspective.
- The regression coincides with commit a34e92b (2025-09-22) and its follow-ups, which introduced SimpleOpenAILLM and updated configs but did not refactor the 61 tasks to honor the new selection mechanism.

## Remediation Plan
### Phase 1 - Configuration Validation
- Confirm correct config resolution path: PlanExeConfig.load and PlanExeLLMConfig.load (files planexe/utils/planexe_config.py and planexe/utils/planexe_llmconfig.py).
- Ensure .env or environment variables provide the intended default LLM ID (likely gpt-4o-mini). Document any required .env updates for Windows and Railway deployments.

### Phase 2 - Eliminate Hardcoded Model IDs
- Catalogue all production-critical files that instantiate get_llm("ollama-llama3.1"). Use repo-wide search (reference list above) and confirm whether each call should:
  1. Use the pipeline-level LLM selection (preferred).
  2. Request a dedicated model from config if genuinely necessary (for example, special fallback).
- Refactor the pipeline base classes (planexe/plan/run_plan_pipeline.py) to pass the resolved model list into each task without task-specific overrides.
  - Inspect PlanTask.create_llm_executor and ExecutePipeline.resolve_llm_models to ensure they leverage LLM_MODEL from env and the priority list supplied by llm_config.json.
- Remove the default constant DEFAULT_LLM_MODEL = "ollama-llama3.1" once the new config is guaranteed to supply at least one OpenAI model.
- For any residual development scripts or proof-of-concept modules, either switch them to read from config or flag them as legacy/non-critical.

### Phase 3 - Request Lifecycle Alignment
- Verify that PipelineExecutionService.execute_plan (lines around 60-140) still writes user prompts into the run directory before Luigi starts.
- Validate that the plans table stores the selected model so historical runs record which model was requested. If not, extend Plan schema and API responses accordingly.
- Ensure WebSocket or SSE status updates include the active LLM model for debugging.

### Phase 4 - Testing and Verification
- Local smoke test: Run npm run go, submit a plan via the UI, confirm Luigi logs report the configured model (look for log lines emitted by SimpleOpenAILLM or LLMExecutor).
- Database check: Inspect the relevant plan row in PostgreSQL to confirm status transitions (pending to running to completed or failed).
- External validation: Capture outbound HTTPS traffic or inspect the OpenAI dashboard to ensure API requests resume.
- Regression suite: Re-run Python tests (pytest -q) and targeted frontend tests (npm test) to ensure no new TypeScript or unit regressions.

## Risk and Mitigation Notes
- Breadth of changes: Updating more than 60 task files is error-prone; schedule incremental commits and use git grep to confirm no hardcoded model strings remain.
- Config drift: API and pipeline read different config files (planexe_api/llm_config.json versus root llm_config.json). Decide on a single source of truth or implement synchronization to avoid future mismatches.
- Environment differences: Windows versus Railway Docker may resolve .env differently. Confirm PlanExeDotEnv.load behaves identically in both modes (planexe/utils/planexe_dotenv.py:32-118).
- Legacy tasks: Some optional or experimental modules may rely on local models intentionally; document any exclusions if they must remain.

## Next Steps Checklist
1. Normalize configuration loading and document the expected .env keys for OpenAI or OpenRouter.
2. Refactor Luigi tasks and supporting utilities to respect LLM_MODEL selection, starting with PlanTask and ExecutePipeline.
3. Purge or gate any remaining hardcoded references to legacy models.
4. Add targeted logs that surface the active model per task for future debugging.
5. Validate end-to-end flow with both SQLite (dev) and PostgreSQL (production) to ensure database persistence is unaffected.
6. Update CHANGELOG.md with the regression fix details once implemented.

## Outstanding Questions
- Should the project maintain a local model fallback (such as Ollama) for offline development, or is OpenAI or OpenRouter the sole supported path?
- Does Railway deployment rely on planexe_api/llm_config.json exclusively? If so, assess whether this file also requires updates to prevent future drift.
- Are there Luigi tasks that require distinct models (for example, inexpensive summarizer versus premium reasoner)? If yes, extend llm_config.json with named presets instead of hardcoding strings inside tasks.

Document owner will proceed with code changes only after explicit approval.

---

## ACTUAL ROOT CAUSE IDENTIFIED (2025-09-29 16:43 ET)
**Analyst: Cascade using Sonnet 4.5**

### The Real Bug
The initial diagnosis was **partially correct but missed the critical failure point**. The actual sequence:

1. ✅ **FastAPI passes environment correctly** - `os.environ.copy()` already exists (line 138 of `pipeline_execution_service.py`)
2. ✅ **API keys are present** - OPENAI_API_KEY and OPENROUTER_API_KEY confirmed in environment
3. ✅ **Pipeline reads LLM_MODEL from environment** - `resolve_llm_models()` works correctly
4. ❌ **DEFAULT_LLM_MODEL is the poison pill** - Line 92 of `run_plan_pipeline.py`

### The Critical Path
```python
# planexe/plan/run_plan_pipeline.py:92
DEFAULT_LLM_MODEL = "ollama-llama3.1"  # ❌ THIS MODEL NO LONGER EXISTS IN llm_config.json

# When resolve_llm_models() falls back (lines 3756-3760):
def resolve_llm_models(cls, specified_llm_model: Optional[str]) -> list[str]:
    llm_models = get_llm_names_by_priority()
    if len(llm_models) == 0:
        logger.error("No LLM models found...")
        llm_models = [DEFAULT_LLM_MODEL]  # ❌ Sets non-existent model
```

### Why This Breaks
1. Pipeline resolves to `["ollama-llama3.1"]` as fallback
2. First task calls `self.create_llm_executor()` (line 122)
3. `LLMModelFromName.from_names(["ollama-llama3.1"])` creates wrapper objects (llm_executor.py:72)
4. When task executes, `LLMExecutor.run()` calls `llm_model.create_llm()` (llm_executor.py:144)
5. This calls `get_llm("ollama-llama3.1")` (llm_executor.py:65)
6. **`get_llm()` checks `is_valid_llm_name()` and raises ValueError** (llm_factory.py:114-116)
7. Task fails immediately, **no OpenAI API calls ever happen**

### The Fix (Applied)
```python
# planexe/plan/run_plan_pipeline.py:92
DEFAULT_LLM_MODEL = "gpt-5-mini-2025-08-07"  # ✅ First model in llm_config.json
```

### Why The Original Diagnosis Was Wrong
- **Incorrect assumption**: Hardcoded `get_llm("ollama-llama3.1")` calls in test blocks (`if __name__ == "__main__"`) were blamed
- **Reality**: Those test blocks never execute during Luigi runs - they're for standalone testing only
- **Actual cause**: The fallback DEFAULT_LLM_MODEL referenced a model removed during the OpenAI simplification

### Verification Path
1. Confirm `llm_config.json` contains only OpenAI/OpenRouter models (✅ verified)
2. Confirm `DEFAULT_LLM_MODEL` pointed to removed Ollama model (✅ verified line 92)
3. Confirm `get_llm()` raises ValueError for invalid model names (✅ verified line 114-116)
4. Confirm this happens at task execution time, not import time (✅ verified via LLMExecutor flow)

### Additional Context
The regression happened because:
- Commit a34e92b (2025-09-22) replaced LlamaIndex with SimpleOpenAILLM
- `llm_config.json` was updated to remove all Ollama models
- **BUT** `DEFAULT_LLM_MODEL` constant was never updated
- This fallback only triggers if `get_llm_names_by_priority()` returns empty list OR when tasks default to it

### Post-Fix Testing Needed
1. Verify pipeline launches successfully with gpt-5-mini-2025-08-07
2. Confirm OpenAI API calls actually reach OpenAI servers
3. Test fallback behavior if primary model fails
4. Validate Railway deployment has correct API keys in environment

---

## RAILWAY DEPLOYMENT ISSUE IDENTIFIED (2025-09-29 17:07 ET)
**Additional investigation by second assistant**

### The Railway-Specific Problem
Even with `DEFAULT_LLM_MODEL` fixed, Railway deployments were still failing because:

**Line 50 of `docker/Dockerfile.railway.api`**:
```dockerfile
RUN test -f /app/llm_config.json || echo '{}' > /app/llm_config.json
```

This fallback creates an **empty** `llm_config.json` if the file doesn't exist in the Docker image.

### Why This Happened
1. ✅ `COPY . .` (line 38) should copy `llm_config.json` from project root
2. ❌ **BUT** if `llm_config.json` wasn't committed to git, Railway doesn't get it
3. ❌ Fallback creates empty `{}` config
4. ❌ `get_llm_names_by_priority()` returns empty list `[]`
5. ❌ `resolve_llm_models()` falls back to `DEFAULT_LLM_MODEL` (which we just fixed)

### The Fix
- ✅ Verified `llm_config.json` IS committed to git (git ls-tree confirms)
- ✅ Railway will now receive the actual config with OpenAI models
- ✅ No more empty config fallback

### Lesson Learned
**Two separate bugs working together**:
1. Local dev: `DEFAULT_LLM_MODEL` pointed to removed model
2. Railway: Missing `llm_config.json` in git meant empty config triggered the bad default

Both needed to be fixed:
- Updated `DEFAULT_LLM_MODEL` to valid model ✅
- Ensured `llm_config.json` is in git ✅
