This document outlines the technical specifications, architecture, and development guidelines for the PlanExe repository.

### Python File Header Template

All new or modified Python files must include the following header:

```python
# Author: {model name}
# Date: {timestamp}
# PURPOSE: {Detailed description of file functionality and its interactions with other components.}
# SRP and DRY check: Pass/Fail. Justification for the check result, including verification that functionality does not already exist elsewhere in the project.
```

---

## 1. System Overview

PlanExe is an AI-powered planning system that generates execution plans from user prompts.

**Core Components:**
1.  **Next.js Frontend**: User interface for plan creation and monitoring.
2.  **FastAPI Backend**: API server that orchestrates the planning process.
3.  **Luigi Pipeline**: Core task engine for plan generation.
4.  **Data Storage**: PostgreSQL/SQLite database and a file system for generated artifacts.

**Data Flow:**
1.  Frontend sends a plan request to the FastAPI backend.
2.  Backend initiates a Luigi pipeline as a subprocess.
3.  The pipeline executes a graph of tasks, interacting with LLMs and writing results to the database in real-time.
4.  Frontend uses a WebSocket connection to the backend to display live progress by querying the database state.
5.  All generated content (artifacts, reports) is served by the backend directly from the database or filesystem.

---

## 2. Architecture Details

### 2.1. Frontend (`planexe-frontend/`)

*   **Technology**: Next.js 15, TypeScript, Tailwind CSS, shadcn/ui.
*   **Local Dev Port**: `3000`.
*   **State Management**: Zustand stores and local React hooks.
*   **API Communication**:
    *   Connects directly to the FastAPI backend via a dedicated client at `src/lib/api/fastapi-client.ts`.
    *   **Rule**: Do not use Next.js API routes (API proxy).
*   **Data Convention**: Field names are `snake_case` to match the backend API schema exactly.
*   **Key Components**:
    *   `PlanForm`: Plan creation UI.
    *   `ProgressMonitor`: Real-time progress tracking via WebSocket.
    *   `TaskList`: Displays the status of all 61 pipeline tasks.
    *   `FileManager`: Browser for generated files and database artifacts.
    *   `Terminal`: Live log streaming via WebSocket.

### 2.2. Backend (`planexe_api/`)

*   **Technology**: FastAPI, SQLAlchemy.
*   **Local Dev Port**: `8080`.
*   **Database**: PostgreSQL or SQLite.
*   **Primary Function**: Provides a REST and WebSocket API to control and monitor the Luigi pipeline.
*   **Key Features**:
    *   **WebSocket Manager**: A thread-safe manager (`RLock` synchronization) for real-time progress updates, with heartbeat monitoring and automatic connection cleanup.
    *   **Process Registry**: Thread-safe management of Luigi subprocesses.
    *   **Responses API Integration**: Uses structured outputs with a schema registry for LLM interactions.
*   **Database Schema (`planexe_api/database.py`)**:
    *   `Plans`: Stores plan configuration, status, and progress metadata.
    *   `LLMInteractions`: Logs raw prompts and structured responses from the LLM.
    *   `PlanFiles`: Metadata for generated files.
    *   `PlanContent`: Stores all task outputs. This table enables the database-first architecture.
    *   `PlanMetrics`: Performance and analytics data.

### 2.3. Pipeline (`planexe/`)

*   **Technology**: Python, Luigi.
*   **Architecture**: A directed acyclic graph (DAG) of 61 interconnected tasks.
*   **I/O Model**:
    1.  **Database-First**: **This is a critical constraint.** Every task must write its output content to the `plan_content` database table *during* its execution, not upon completion.
    2.  **File-based**: Tasks also output numbered JSON files (e.g., `001-start_time.json`, `018-wbs_level1.json`).
*   **Key Features**:
    *   **Resumability**: Can resume interrupted runs by recovering state from the database.
    *   **LLM Orchestration**: Manages calls to multiple LLM models with retry logic and fallbacks.
*   **Pipeline Stages**:
    1.  Setup
    2.  Analysis
    3.  Strategic
    4.  Context
    5.  Assumptions
    6.  Planning
    7.  Execution
    8.  Structure (WBS)
    9.  Output
    10. Report

---

## 3. API Endpoints

The API is served from the FastAPI backend on port `8080`.

| Method | Path                                   | Description                                                               |
| :----- | :------------------------------------- | :------------------------------------------------------------------------ |
| `POST` | `/api/plans`                           | Create a new plan and trigger the Luigi pipeline.                         |
| `GET`  | `/api/plans/{id}/stream`               | Establishes a WebSocket connection for real-time progress updates.        |
| `GET`  | `/api/plans/{id}/files`                | List generated files for a plan.                                          |
| `GET`  | `/api/plans/{id}/report`               | Download the final HTML report.                                           |
| `GET`  | `/api/plans/{id}/artefacts`            | Get database-driven artifact metadata, grouped by pipeline stage.         |
| `GET`  | `/api/plans/{id}/fallback-report`      | API-driven recovery path to assemble a report if the primary one fails.   |
| `GET`  | `/api/models`                          | List available LLM models, including those from the Responses API.        |
| `GET`  | `/api/prompts`                         | List example prompts.                                                     |
| `GET`  | `/health`                              | Health check endpoint.                                                    |

---

## 4. Development Rules

### 4.1. General
*   **File Modifications**: Prefer editing existing files over creating new ones.
*   **Documentation**: Create or update `.md` files in the `/docs` directory to document significant changes or plans.
*   **Local Environment**: Run both the Next.js (`port 3000`) and FastAPI (`port 8080`) services concurrently for development.

### 4.2. Frontend (`planexe-frontend/`)
*   **API Fields**: Always use `snake_case` for fields in API payloads to match the backend.
*   **API Routes**: Do not create Next.js API routes. All communication must go directly to the FastAPI server.
*   **State & Components**: Follow existing patterns using shadcn/ui, TypeScript, and Zustand.

### 4.3. Backend (`planexe_api/`)
*   **API Compatibility**: Do not make breaking changes to FastAPI endpoints consumed by the frontend.
*   **Database**: For any schema changes in `SQLAlchemy` models, ensure database migrations are created and updated.
*   **Architecture**: Preserve the existing thread-safe WebSocket and process management implementations.

### 4.4. Pipeline (`planexe/`)
*   **Modification Constraint**: **Do not modify the Luigi pipeline task dependency graph without a full understanding of its structure.**
*   **Database-First Mandate**: All task modifications must adhere to the database-first principle: write results to the database during execution.
*   **Development Mode**: Use the `FAST_BUT_SKIP_DETAILS` environment variable for faster, less detailed test runs.
*   **LLM Outputs**: Use the Responses API models to ensure structured outputs.

---

## 5. Testing
*   **Constraint**: Do not use mocking, faking, or simulated data for testing.
*   **Test Data**: Use data from previously executed plans for all tests.
*   **Frontend**: Write component tests using React Testing Library.
*   **Backend**: Write endpoint tests for the FastAPI application.
*   **Pipeline**: Limited to Luigi task validation.

---

## 6. Debugging

### 6.1. Common Issues & Solutions
*   **Symptom**: "Connection refused" errors in the frontend.
    *   **Check**: Verify the FastAPI backend process is running on `port 8080`.
*   **Symptom**: WebSocket connection fails.
    *   **Check**: Ensure the backend is running and the path `/ws/plans/{plan_id}/progress` is accessible.
*   **Symptom**: A Luigi task fails.
    *   **Check**: Inspect logs in the `run/` directory and query the `plan_content` table in the database for the last successful write.
*   **Symptom**: Artifacts are not loading in the UI.
    *   **Check**: Test the `/api/plans/{id}/artefacts` endpoint directly for metadata.
*   **Symptom**: HTML report generation fails.
    *   **Check**: Use the `/api/plans/{id}/fallback-report` endpoint as a recovery mechanism.

### 6.2. Debugging Commands

```bash
# Check for running services on correct ports
netstat -an | findstr ":3000|:8080"

# Test API health and model endpoints
curl http://localhost:8080/health
curl http://localhost:8080/api/models

# Test plan creation
curl -X POST http://localhost:8080/api/plans \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Create a plan", "model": "llm-1"}'

# Test artefact endpoint for a given plan ID
curl http://localhost:8080/api/plans/{plan_id}/artefacts

# Query the database for the last 5 content writes for a plan
sqlite3 planexe.db "SELECT * FROM plan_content WHERE plan_id='{plan_id}' ORDER BY created_at DESC LIMIT 5;"
```

---

## 7. Key File Index

### 7.1. Documentation
*   `CHANGELOG.md`: Project status and recent change history.
*   `docs/run_plan_pipeline_documentation.md`: In-depth guide to the Luigi pipeline.
*   `docs/LUIGI.md`: Luigi framework documentation.
*   `docs/CODEBASE-INDEX.md`: Index of the codebase.

### 7.2. Frontend
*   `planexe-frontend/src/lib/api/fastapi-client.ts`: The API client.
*   `planexe-frontend/src/lib/types/forms.ts`: TypeScript schemas for API data structures.
*   `planexe-frontend/src/app/page.tsx`: Main application component.

### 7.3. Backend
*   `planexe_api/api.py`: FastAPI application entrypoint, routes, and WebSocket logic.
*   `planexe_api/models.py`: Pydantic schemas for API requests and responses.
*   `planexe_api/database.py`: SQLAlchemy database models.