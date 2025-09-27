# PlanExe Codebase Index

**Generated**: 2025-09-27  
**Version**: 0.2.1  
**Purpose**: Comprehensive index and architectural overview of the PlanExe AI-powered planning system

## 🚨 **CRITICAL PORT INFORMATION - UPDATED v0.2.1**
- **Railway Production**: FastAPI runs on port **8080** (Railway's PORT environment variable)
- **Local Development**: FastAPI runs on port **8000** (development only)
- **Architecture**: Railway single-service deployment (FastAPI serves UI + API)
- **Development Workflow**: Railway-first deployment, no local Windows debugging

---

## 🏗️ System Architecture Overview

PlanExe is a **complex AI-powered planning system** that transforms vague ideas into comprehensive, multi-chapter execution plans using a sophisticated **Next.js frontend** connected to a **FastAPI backend** that orchestrates a **Luigi pipeline** with **62 interconnected tasks**.

### High-Level Data Flow

#### Railway Production (Primary)
```
User → Railway URL (8080) → FastAPI (serves UI + API) → Luigi Pipeline (62 Tasks) → Generated Files
   ↑                           ↓
   └── Real-time Progress (WebSocket/SSE) ←
```

#### Local Development (Legacy - Railway-First Workflow Now)
```
User → Next.js UI (3000) --CORS--> FastAPI (8000) → Luigi Pipeline (62 Tasks) → Generated Files
   ↑                                    ↓
   └── Real-time Progress (SSE) ←-------┘

⚠️ NOTE: Local development discouraged. Railway-first workflow recommended.
```

### Technology Stack

- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS + shadcn/ui + Zustand
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL/SQLite + Server-Sent Events
- **Pipeline**: Luigi (62 interconnected tasks) + LLM orchestration
- **AI**: OpenAI + OpenRouter + multiple model fallbacks
- **Deployment**: Railway single-service (FastAPI serves static UI + API)

---

## 📁 Directory Structure

### Root Level
```
PlanExe/
├── planexe/                 # Core Python pipeline (Luigi tasks)
├── planexe_api/             # FastAPI REST server
├── planexe-frontend/        # Next.js React application
├── docker/                  # Container orchestration
├── docs/                    # Documentation and plans
├── run/                     # Pipeline execution outputs
├── llm_config.json          # LLM model configuration
└── CLAUDE.md               # Development guidelines
```

### Core Pipeline (`planexe/`)
```
planexe/
├── plan/                    # Main pipeline orchestration
│   ├── run_plan_pipeline.py # 61 Luigi tasks definition
│   ├── project_plan.py      # Goal definition models
│   ├── pipeline_*.py        # Pipeline utilities
├── assume/                  # Assumption analysis tasks
├── diagnostics/             # Plan validation tasks
├── document/                # Document identification
├── expert/                  # Expert review system
├── governance/              # Governance framework
├── lever/                   # Strategic lever analysis
├── schedule/                # Gantt chart generation
├── swot/                    # SWOT analysis
├── team/                    # Team building
├── wbs/                     # Work Breakdown Structure
├── llm_factory.py           # LLM creation & management
└── llm_util/               # LLM execution utilities
```

### FastAPI Backend (`planexe_api/`)
```
planexe_api/
├── api.py                   # Main FastAPI application
├── models.py               # Pydantic request/response schemas
├── database.py             # SQLAlchemy models & service
├── migrations/             # Database schema migrations
└── requirements.txt        # Python dependencies
```

### Next.js Frontend (`planexe-frontend/`)
```
planexe-frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx        # Main application page
│   │   └── layout.tsx      # Root layout
│   ├── components/
│   │   ├── planning/       # Plan creation forms
│   │   ├── monitoring/     # Progress tracking
│   │   ├── files/          # File management
│   │   └── ui/            # shadcn/ui components
│   └── lib/
│       ├── api/           # FastAPI client
│       ├── stores/        # Zustand state management
│       └── types/         # TypeScript definitions
├── package.json           # Dependencies & scripts
└── next.config.ts         # Next.js configuration
```

---

## 🔄 Luigi Pipeline Architecture (61 Tasks)

The core of PlanExe is a sophisticated Luigi pipeline with **61 interconnected tasks** organized into logical phases:

### Task Dependency Layers

1. **Setup & Initialization**
   - `StartTimeTask`, `SetupTask` (pre-created by API)

2. **Early Analysis**
   - `RedlineGateTask`, `PremiseAttackTask`
   - `IdentifyPurposeTask`, `PlanTypeTask`

3. **Strategic Analysis**
   - `PotentialLeversTask` → `DeduplicateLeversTask` → `EnrichLeversTask`
   - `FocusOnVitalFewLeversTask` → `CandidateScenariosTask` → `SelectScenarioTask`
   - `StrategicDecisionsMarkdownTask`, `ScenariosMarkdownTask`

4. **Context & Environment**
   - `PhysicalLocationsTask`, `CurrencyStrategyTask`, `IdentifyRisksTask`

5. **Assumptions Framework**
   - `MakeAssumptionsTask` → `DistillAssumptionsTask` → `ReviewAssumptionsTask` → `ConsolidateAssumptionsMarkdownTask`

6. **Core Planning**
   - `PreProjectAssessmentTask` → `ProjectPlanTask`

7. **Governance Structure**
   - `GovernancePhase1AuditTask` through `GovernancePhase6ExtraTask` → `ConsolidateGovernanceTask`

8. **Team & Resources**
   - `FindTeamMembersTask` → `EnrichTeamMembersWithContractTypeTask` → `EnrichTeamMembersWithBackgroundStoryTask` → `EnrichTeamMembersWithEnvironmentInfoTask` → `ReviewTeamTask` → `TeamMarkdownTask`
   - `RelatedResourcesTask`

9. **Analysis & Validation**
   - `SWOTAnalysisTask`, `ExpertReviewTask`

10. **Documentation**
    - `DataCollectionTask`, `IdentifyDocumentsTask` → `FilterDocumentsToFindTask`/`FilterDocumentsToCreateTask` → `DraftDocumentsToFindTask`/`DraftDocumentsToCreateTask` → `MarkdownWithDocumentsToCreateAndFindTask`

11. **Work Breakdown Structure**
    - `CreateWBSLevel1Task` → `CreateWBSLevel2Task` → `WBSProjectLevel1AndLevel2Task` → `EstimateTaskDurationsTask` → `CreateWBSLevel3Task` → `WBSProjectLevel1AndLevel2AndLevel3Task`

12. **Project Presentation**
    - `CreatePitchTask` → `ConvertPitchToMarkdownTask`

13. **Scheduling**
    - `IdentifyTaskDependenciesTask`, `CreateScheduleTask` (generates Mermaid/DHTMLX/CSV)

14. **Review & Summary**
    - `ReviewPlanTask`, `ExecutiveSummaryTask`, `QuestionsAndAnswersTask`, `PremortemTask`

15. **Final Report**
    - `ReportTask` (compiles all artifacts into HTML)

### Key Pipeline Characteristics

- **File-based I/O**: Each task reads upstream files and writes numbered outputs (001-start_time.json, 018-wbs_level1.json, etc.)
- **LLM Integration**: Most tasks use `LLMExecutor` with fallback mechanisms and model retry logic
- **Progress Tracking**: Uses file completion percentage and expected filename counting
- **Resume Capability**: Can continue from interrupted runs
- **Speed Modes**: `FAST_BUT_SKIP_DETAILS` vs `ALL_DETAILS_BUT_SLOW`

---

## 🌐 FastAPI Backend Details

### Core Endpoints

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/health` | API health check |
| `GET` | `/api/models` | Available LLM models |
| `GET` | `/api/prompts` | Example prompts |
| `POST` | `/api/plans` | Create new plan (triggers Luigi) |
| `GET` | `/api/plans/{id}` | Get plan status |
| `GET` | `/api/plans/{id}/stream` | Real-time progress (SSE) |
| `GET` | `/api/plans/{id}/files` | List generated files |
| `GET` | `/api/plans/{id}/report` | Download HTML report |
| `DELETE` | `/api/plans/{id}` | Cancel running plan |

### Plan Execution Flow

1. **Plan Creation**: Generate `plan_id`, create `run_id_dir`, write `START_TIME` + `INITIAL_PLAN` files
2. **Database Persistence**: Store plan metadata in SQLite/PostgreSQL
3. **Subprocess Launch**: `python -m planexe.plan.run_plan_pipeline` with environment variables
4. **Progress Monitoring**: Parse subprocess stdout with regex for task completion
5. **Real-time Updates**: Send progress via Server-Sent Events (SSE) to frontend
6. **Completion Handling**: Index generated files, update status, enable downloads

### Database Schema

- **Plans**: Configuration, status, progress, metadata
- **LLMInteractions**: Raw prompts/responses with token counts
- **PlanFiles**: Generated files with checksums
- **PlanMetrics**: Analytics and performance data

---

## ⚛️ Next.js Frontend Details

### Key Components

- **`PlanForm`**: Plan creation with LLM model selection
- **`ProgressMonitor`**: Real-time SSE progress tracking
- **`TaskList`**: Accordion view of 61 pipeline tasks
- **`FileManager`**: Generated file browser and downloads
- **`PlansQueue`**: Plan management dashboard
- **`PipelineDetails`**: Execution logs and detailed view

### State Management

- **Local State**: React hooks for active plan, loading states
- **Zustand Stores**: Configuration and session management
- **Direct API**: No Next.js API routes, direct FastAPI client

### Data Flow

1. User submits plan via `PlanForm`
2. `fastApiClient.createPlan()` sends request to FastAPI
3. `ProgressMonitor` establishes SSE connection for real-time updates
4. UI updates progress bar and task list based on SSE events
5. On completion, user can access files via `FileManager` and download report

---

## 🔧 LLM System Architecture

### Simplified LLM Factory (v0.1.5)

The LLM system was completely overhauled in v0.1.5, replacing complex llama-index with a simple OpenAI client:

```python
# llm_config.json structure
{
    "gpt-5-mini-2025-08-07": {
        "comment": "Latest GPT-5 Mini model - primary choice",
        "priority": 1,
        "provider": "openai",
        "model": "gpt-5-mini-2025-08-07"
    },
    // ... 4 working models with fallback sequence
}
```

### Model Fallback Sequence

1. `gpt-5-mini-2025-08-07` (OpenAI primary)
2. `gpt-4.1-nano-2025-04-14` (OpenAI secondary)
3. `google/gemini-2.0-flash-001` (OpenRouter fallback 1)
4. `google/gemini-2.5-flash` (OpenRouter fallback 2)

### LLM Execution Pattern

```python
llm_executor = LLMExecutor(
    llm_models=model_instances,
    should_stop_callback=callback
)
result = llm_executor.run(lambda llm: task.execute(llm, query))
```

---

## 🚀 Development Workflow

### 🎯 **PRIMARY: Railway-First Development**

```bash
# 1. Make changes locally (Windows)
# 2. Commit immediately
git add .
git commit -m "descriptive message"
git push origin main

# 3. Railway auto-deploys from GitHub
# 4. Debug using Railway logs + robust UI
# 5. Iterate with rapid commit-push-deploy cycle
```

### 🔧 **LEGACY: Local Development (Discouraged)**

```bash
# Only use for quick testing - Railway is primary environment
cd planexe-frontend
npm install
npm run go  # Starts both FastAPI (port 8000) and Next.js (port 3000)

# ⚠️ NOTE: Luigi pipeline has Windows issues. Use Railway for real testing.
```

### Testing Strategy

- **Use Existing Data**: Test with old plans in `D:\1Projects\PlanExe\run` - do not create fake data!
- **No Over-Engineering**: Use real data from failed runs for testing
- **Integration Tests**: Both services running on correct ports
- **Frontend**: Component tests with React Testing Library
- **Backend**: FastAPI endpoint testing

---

## ⚠️ Critical Development Guidelines

### DO NOT

1. **Modify Luigi pipeline** without understanding the full 61-task dependency graph
2. **Create fake test data** - use existing plans in `/run` directory
3. **Debug Windows Luigi issues** - deploy to Railway instead
4. **Use local development for Luigi testing** - Railway is primary environment
5. **Over-engineer for hobbyist project** - keep solutions simple

### DO

1. **Use Railway-first development workflow** - rapid commit-push-deploy
2. **Make UI robust for debugging** - show all status without browser console
3. **Use snake_case** field names throughout (matches backend)
4. **Commit changes immediately** with verbose messages
5. **Focus on features, not Windows debugging**

### Architecture Decisions

- **Direct FastAPI Client**: No Next.js API proxy routes
- **Snake_case Fields**: Frontend uses backend field names exactly
- **Simplified State**: Removed complex Zustand planning store
- **SQLite Development**: No PostgreSQL dependency locally
- **File-based Contracts**: Luigi tasks communicate via numbered files

---

## 🔍 Key Files Reference

### Entry Points

- **`planexe_api/api.py`**: FastAPI server main entry point
- **`planexe/plan/run_plan_pipeline.py`**: Luigi pipeline with all 61 tasks
- **`planexe-frontend/src/app/page.tsx`**: Next.js main application page

### Configuration

- **`llm_config.json`**: LLM models and providers
- **`planexe-frontend/package.json`**: Development scripts and dependencies
- **`docker/docker-compose.yml`**: Container orchestration
- **`CLAUDE.md`**: Development guidelines and architecture notes

### Core Libraries

- **`planexe/llm_factory.py`**: Simplified LLM creation system
- **`planexe-frontend/src/lib/api/fastapi-client.ts`**: Direct API client
- **`planexe_api/database.py`**: SQLAlchemy models and database service

---

## 🐛 Known Issues & Troubleshooting

### Current Issues (v0.1.5)

1. **Environment Variable Access**: Luigi subprocess may not inherit .env variables
2. **SSE Reliability**: Real-time progress has reliability issues
3. **Port Documentation**: Some docs incorrectly mention port 8001 (actual: 8000)

### Common Debug Steps

```bash
# Check services are running
netstat -an | findstr :3000  # Next.js
netstat -an | findstr :8000  # FastAPI

# Test API connectivity
curl http://localhost:8000/health
curl http://localhost:8000/api/models
```

### Log Locations

- **Pipeline Logs**: `run/{run_id}/log.txt`
- **Activity Tracking**: `run/{run_id}/track_activity.jsonl`
- **API Debug**: Console output during development

---

## 📈 Performance Characteristics

- **Plan Creation**: ~200ms average response time
- **Luigi Pipeline**: 61 tasks, varies by complexity (minutes to hours)
- **Database Queries**: <50ms for typical plan lookups
- **File Downloads**: Direct file serving with range support
- **Real-time Updates**: <1s latency via SSE (when working)
- **Memory Usage**: ~100MB baseline, scales with concurrent plans

---

## 🔒 Security Considerations

- **API Keys**: Hashed storage, never logged in plaintext
- **File Access**: Path traversal protection for downloads
- **CORS**: Wide-open for development, should be restricted in production
- **Database**: Connection string security via environment variables
- **Input Validation**: Pydantic models ensure type safety

---

## 🚢 Deployment Options

1. **Development**: `npm run go` (both services)
2. **Docker Compose**: Full stack with PostgreSQL
3. **Production**: Separate FastAPI + Next.js deployments
4. **Container Registry**: Multi-stage builds available

---

*This index reflects the current state as of v0.1.5. The system has a working LLM integration, stable frontend forms, and a complex but reliable Luigi pipeline. Real-time progress monitoring has known issues but the core functionality is solid.*

PIPELINE:
# Luigi Pipeline Dependency Chain

1. StartTimeTask
   └── 2. SetupTask
       ├── 3. RedlineGateTask
       │   └── 4. PremiseAttackTask
       │       └── 5. IdentifyPurposeTask
       │           ├── 6. MakeAssumptionsTask
       │           │   └── 7. DistillAssumptionsTask
       │           │       └── 8. ReviewAssumptionsTask
       │           │           └── 9. IdentifyRisksTask
       │           │               ├── 57. RiskMatrixTask
       │           │               │   └── 58. RiskMitigationPlanTask
       │           │               └── (feeds into Governance & Report later)
       │           ├── 10. CurrencyStrategyTask
       │           └── 11. PhysicalLocationsTask
       │
       ├── 12. StrategicDecisionsMarkdownTask
       │   └── 13. ScenariosMarkdownTask
       │       └── 14. ExpertFinder
       │           └── 15. ExpertCriticism
       │               └── 16. ExpertOrchestrator
       │
       ├── 17. CreateWBSLevel1
       │   └── 18. CreateWBSLevel2
       │       └── 19. CreateWBSLevel3
       │           ├── 20. IdentifyWBSTaskDependencies
       │           ├── 21. EstimateWBSTaskDurations
       │           ├── 22. WBSPopulate
       │           ├── 23. WBSTaskTooltip
       │           └── (→ feeds into 24. WBSTask & 25. WBSProject)
       │               └── 26. ProjectSchedulePopulator
       │                   └── 27. ProjectSchedule
       │                       ├── 28. ExportGanttDHTMLX
       │                       ├── 29. ExportGanttCSV
       │                       └── 30. ExportGanttMermaid
       │
       ├── 31. FindTeamMembers
       │   ├── 32. EnrichTeamMembersWithContractType
       │   ├── 33. EnrichTeamMembersWithBackgroundStory
       │   ├── 34. EnrichTeamMembersWithEnvironmentInfo
       │   └── 35. TeamMarkdownDocumentBuilder
       │       └── 36. ReviewTeam
       │
       ├── 37. CreatePitch
       │   └── 38. ConvertPitchToMarkdown
       │
       ├── 39. ExecutiveSummary
       ├── 40. ReviewPlan
       ├── 41. ReportGenerator
       │
       ├── 42. GovernancePhase1AuditTask
       │   └── 43. GovernancePhase2InternalBodiesTask
       │       └── 44. GovernancePhase3ImplementationPlanTask
       │           └── 45. GovernancePhase4DecisionMatrixTask
       │               └── 46. GovernancePhase5MonitoringTask
       │                   └── 47. GovernancePhase6ExtraTask
       │                       └── 48. ConsolidateGovernanceTask
       │
       ├── 49. DataCollection
       ├── 50. ObtainOutputFiles
       ├── 51. PipelineEnvironment
       ├── 52. LLMExecutor
       │
       ├── 53. WBSJSONExporter
       ├── 54. WBSDotExporter
       ├── 55. WBSPNGExporter
       ├── 56. WBSPDFExporter
       │
       ├── 59. BudgetEstimationTask
       │   └── 60. CashflowProjectionTask
       │
       └── 61. FinalReportAssembler
           ├── merges Governance outputs
           ├── merges Risk outputs
           ├── merges WBS & Schedule exports
           ├── merges Team documents
           ├── merges Pitch & Executive Summary
           └── produces **Final Report**

           