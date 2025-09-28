# Post-Prompt Flow Analysis: What Should Happen After User Enters Prompt

**Author**: Claude Code using Sonnet 4
**Date**: 2025-09-28
**PURPOSE**: Comprehensive analysis of the expected user flow after prompt submission, based on commits from past week and system architecture understanding

## 🎯 **Executive Summary**

After analyzing recent commits, documentation, and codebase architecture, this document provides a definitive analysis of what should happen when a user enters a prompt in the PlanExe UI, including current issues and expected behavior.

## 📋 **Current System Architecture Overview**

### **Three-Layer System**
1. **Next.js Frontend** (Port 3000 dev / served by FastAPI on 8080 in Railway)
2. **FastAPI Backend** (Port 8080)
3. **Luigi Pipeline** (61-task subprocess spawned by FastAPI)

### **Development vs Production Modes**
- **Development**: Next.js dev server (3000) + FastAPI (8080) + Luigi subprocess
- **Production (Railway)**: Single FastAPI server (8080) serves static UI + API + Luigi subprocess

## 🔄 **Expected Post-Prompt Flow (Step by Step)**

### **Phase 1: Form Submission & Plan Creation**

1. **User Action**: User fills out PlanForm.tsx with:
   - Plan prompt (required, min 10 chars)
   - LLM model selection (dropdown loads from `/api/models`)
   - Speed vs Detail setting (`fast_but_skip_details` or `all_details_but_slow`)
   - OpenRouter API key (if required by selected model)

2. **Frontend Processing**:
   - PlanForm validates input with Zod schema
   - Calls `fastApiClient.createPlan(CreatePlanRequest)`
   - Posts to `/api/plans` endpoint with snake_case field names

3. **Backend Processing**:
   - FastAPI receives POST request at `/api/plans`
   - Creates new plan record in database (SQLite/PostgreSQL)
   - Generates unique plan ID (e.g., `PlanExe_fe5f3ead-590e-4997-84e6-618724898b76`)
   - Creates run directory: `run/{plan_id}/`
   - Writes initial files:
     - `001-1-start_time.json` - Pipeline start timestamp
     - `001-2-plan.txt` - User prompt text
   - Returns PlanResponse with `plan_id` and `status: 'pending'`

4. **Frontend Response**:
   - Main page (`page.tsx`) receives plan_id
   - Sets `activePlanId` state
   - Automatically switches to "Monitor Progress" tab
   - Begins displaying ProgressMonitor component

### **Phase 2: Luigi Pipeline Execution**

5. **FastAPI Subprocess Spawn**:
   - FastAPI spawns subprocess: `python -m planexe.plan.run_plan_pipeline`
   - Working directory: Project root
   - Environment: Inherits API keys from FastAPI process
   - Command includes run_id_dir parameter

6. **Luigi Pipeline Initialization**:
   - Luigi reads from run directory (`run/{plan_id}/`)
   - Loads `001-1-start_time.json` and `001-2-plan.txt`
   - Initializes 109 expected output files (saved to `expected_filenames1.json`)
   - Begins dependency checking for 61+ Luigi tasks

7. **Task Execution Stages** (109 expected files across 61+ tasks):
   ```
   Stage 1 (Analysis): RedlineGate → PremiseAttack → IdentifyPurpose → PlanType
   Stage 2 (Strategy): PotentialLevers → Deduplicate → Enrich → VitalFew → Scenarios
   Stage 3 (Context): PhysicalLocations → CurrencyStrategy → IdentifyRisks
   Stage 4 (Assumptions): Make → Distill → Review → Consolidate
   Stage 5 (Planning): PreProjectAssessment → ProjectPlan → Governance(1-6)
   Stage 6 (Resources): RelatedResources → TeamBuilding → SWOT → ExpertReview
   Stage 7 (Structure): DataCollection → WBS(1-3) → Dependencies → Durations
   Stage 8 (Output): Pitch → Schedule → Review → ExecutiveSummary → Premortem
   Stage 9 (Report): FinalReportAssembler → HTML compilation
   ```

### **Phase 3: Real-Time Progress Monitoring**

8. **WebSocket Connection** (v0.2.0+ - replaced broken SSE):
   - Terminal.tsx establishes WebSocket to `/ws/plans/{plan_id}/progress`
   - Uses enterprise-grade architecture with:
     - Thread-safe WebSocketManager
     - Automatic heartbeat monitoring
     - Exponential backoff reconnection (5 attempts)
     - REST polling fallback if WebSocket fails completely

9. **Progress Updates**:
   - Luigi pipeline writes numbered output files (002-3-premise_attack.json, etc.)
   - WebSocket broadcasts real-time log messages to frontend
   - Terminal.tsx displays Luigi stdout/stderr in terminal-like UI
   - LuigiPipelineView.tsx shows visual progress through 61 tasks
   - Progress percentage calculated based on completed files vs expected files

10. **User Experience During Execution**:
    - Real-time terminal logs showing Luigi task execution
    - Visual task list with accordion UI showing 61 pipeline tasks
    - Connection status indicators (WebSocket/Polling/Disconnected)
    - Manual reconnect button if connection issues
    - Stop pipeline button (DELETE `/api/plans/{plan_id}`)

### **Phase 4: Completion & File Access**

11. **Pipeline Completion**:
    - Luigi writes final file: `999-pipeline_complete.txt`
    - All 109 expected output files generated
    - Final HTML report compiled: `029-report.html`
    - WebSocket sends completion message
    - Database updated with `status: 'completed'`

12. **Frontend Completion Handling**:
    - Terminal.tsx receives completion event
    - ProgressMonitor calls `onComplete()` callback
    - Main page automatically switches to "Details" tab
    - User can now access:
      - **Details Tab**: PipelineDetails.tsx shows plan metadata
      - **Files Tab**: FileManager.tsx browses all generated files
      - File downloads via `/api/plans/{plan_id}/files/{filename}`
      - HTML report download via `/api/plans/{plan_id}/report`

## 🚨 **Known Issues & Current Problems**

### **Issues from Recent Commits Analysis:**

1. **Railway Deployment Focus** (v0.2.2-0.2.3):
   - System optimized primarily for Railway deployment
   - Local Windows development has ongoing subprocess issues
   - Port confusion (some docs say 8001, actually 8080)

2. **WebSocket Reliability** (v0.2.0):
   - Major improvement over broken SSE, but still noted as having "known reliability issues"
   - Fallback to REST polling implemented
   - Multiple reconnection attempts required

3. **LLM Model Loading** (Recent fixes):
   - Models dropdown shows Railway-specific error handling
   - Fallback options when Railway API unavailable
   - Enhanced retry mechanisms with user-visible debugging

4. **Luigi Pipeline Complexity** (Ongoing):
   - 61+ tasks with complex dependency chains
   - Extremely difficult to modify without breaking dependencies
   - Memory usage can be significant during execution
   - Environment variable inheritance issues in subprocess

### **Critical Failure Points:**

1. **Luigi Subprocess Startup**:
   - If Python environment doesn't inherit API keys → tasks fail
   - If run directory not properly created → pipeline fails immediately
   - If LLM models not configured → all AI tasks fail

2. **WebSocket/SSE Connection**:
   - If WebSocket fails and polling fallback fails → no progress visibility
   - If network interruption → manual reconnection required
   - If Luigi subprocess dies silently → no completion signal

3. **File Generation**:
   - If any Luigi task fails → incomplete file set
   - If memory issues → partial file writes
   - If permissions issues → file access errors

## 📊 **Expected Timeline**

### **Fast Mode** (`fast_but_skip_details`):
- **Duration**: 10-20 minutes
- **Files Generated**: ~50-70 (subset of full pipeline)
- **LLM Calls**: Reduced set, essential tasks only

### **Full Mode** (`all_details_but_slow`):
- **Duration**: 45-90 minutes
- **Files Generated**: All 109 expected files
- **LLM Calls**: Complete 61+ task pipeline

## 🔧 **Technical Implementation Details**

### **Data Flow**:
```
User Input → PlanForm.tsx → fastApiClient → FastAPI → Database
                ↓
FastAPI spawns Luigi subprocess → 61+ Luigi tasks → File outputs
                ↓
WebSocket streams logs → Terminal.tsx → User sees progress
                ↓
Pipeline completion → WebSocket completion → Tab switch → File access
```

### **File Naming Convention**:
- Format: `{stage}-{task_number}-{task_name}.{extension}`
- Examples:
  - `001-1-start_time.json` - Pipeline start
  - `002-3-premise_attack.json` - Analysis stage, task 3
  - `018-2-wbs_level1.json` - Structure stage, WBS Level 1
  - `029-report.html` - Final compiled report
  - `999-pipeline_complete.txt` - Completion marker

### **Database Schema**:
- **Plans Table**: status, progress_percentage, progress_message, error_message
- **LLM Interactions**: All prompts/responses logged with metadata
- **Plan Files**: File checksums and metadata tracking
- **Plan Metrics**: Performance analytics

## 🎯 **Success Criteria**

A successful post-prompt flow should achieve:

1. ✅ **Immediate Response**: Plan created within 2-3 seconds
2. ✅ **Progress Visibility**: Real-time logs visible within 10 seconds
3. ✅ **Task Execution**: All 61+ Luigi tasks execute without failure
4. ✅ **File Generation**: All 109 expected files created
5. ✅ **Completion Signal**: WebSocket completion message sent
6. ✅ **File Access**: All files downloadable via API
7. ✅ **Report Generation**: HTML report compiled and accessible

## 🚧 **Areas Requiring Investigation**

Based on this analysis, key areas that may need attention:

1. **Luigi Environment Variables**: Ensure API keys properly inherited by subprocess
2. **WebSocket Stability**: Monitor connection reliability in production
3. **Memory Management**: Luigi pipeline memory usage during long runs
4. **Error Recovery**: Better handling of partial pipeline failures
5. **Progress Accuracy**: Ensure progress percentage reflects actual completion

## 🏁 **Conclusion**

The PlanExe system has a well-architected flow from prompt to completion, with significant improvements in v0.2.0+ for real-time monitoring. The main challenges remain in the Luigi pipeline complexity and ensuring reliable subprocess execution across different environments (Windows dev vs Railway production).

The system is designed to provide users with comprehensive visibility into the AI planning process, from initial prompt analysis through final report generation, with robust error handling and fallback mechanisms for network connectivity issues.