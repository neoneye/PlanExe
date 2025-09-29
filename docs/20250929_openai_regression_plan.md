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
   - Many proof-of-concept scripts under planexe/proof_of_concepts also hardcode the same model.
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
