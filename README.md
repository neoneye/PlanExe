<!--
 * Author: Cascade
 * Date: 2025-09-19
 * PURPOSE: Comprehensive technical documentation for PlanExe. Provides architecture overview, setup instructions, development guidelines, and project structure.
 * SRP and DRY check: Pass - This file solely documents the project and avoids duplicating code logic.
-->

# PlanExe

What if you could plan a dystopian police state from a single prompt?

That's what PlanExe does. It took a two-sentence idea about deploying police robots in Brussels and generated a multi-faceted, 50-page strategic and tactical plan.

[See the "Police Robots" plan here →](https://neoneye.github.io/PlanExe-web/20250824_police_robots_report.html)

---

<details>
<summary><strong> Try it out now (Click to expand)</strong></summary>
<br>

If you are not a developer. You can generate 1 plan for free, beyond that it cost money.

[Try it here →](https://app.mach-ai.com/planexe_early_access)

</details>

---

<details>
<summary><strong> Installation (Click to expand)</strong></summary>

<br>

**Prerequisite:** You are a python developer with machine learning experience.

# Installation

Typical python installation procedure:

```bash
git clone https://github.com/neoneye/PlanExe.git
cd PlanExe
python3 -m venv venv
source venv/bin/activate
(venv) pip install '.[gradio-ui]'
```

# Configuration

**Config A:** Run a model in the cloud using a paid provider. Follow the instructions in [OpenRouter](extra/openrouter.md).

**Config B:** Run models locally on a high-end computer. Follow the instructions for either [Ollama](extra/ollama.md) or [LM Studio](extra/lm_studio.md).

Recommendation: I recommend **Config A** as it offers the most straightforward path to getting PlanExe working reliably.

# Usage

PlanExe comes with a Gradio-based web interface. To start the local web server:

```bash
(venv) python -m planexe.plan.app_text2plan
```

This command launches a server at http://localhost:7860. Open that link in your browser, type a vague idea or description, and PlanExe will produce a detailed plan.

To stop the server at any time, press `Ctrl+C` in your terminal.

</details>

---

<details>
<summary><strong> Screenshots (Click to expand)</strong></summary>

<br>

You input a vague description of what you want and PlanExe outputs a plan. [See generated plans here](https://neoneye.github.io/PlanExe-web/use-cases/).

![Video of PlanExe](/extra/planexe-humanoid-factory.gif?raw=true "Video of PlanExe")

[YouTube video: Using PlanExe to plan a lunar base](https://www.youtube.com/watch?v=7AM2F1C4CGI)

![Screenshot of PlanExe](/extra/planexe-humanoid-factory.jpg?raw=true "Screenshot of PlanExe")

</details>

---

<details>
<summary><strong> Help (Click to expand)</strong></summary>

<br>

For help or feedback.

Join the [PlanExe Discord](https://neoneye.github.io/PlanExe-web/discord).

</details>

---

## Technical Architecture

PlanExe transforms a vague idea into a fully-fledged, multi-chapter execution plan. Internally it is organised as a **loosely coupled, layered architecture**:

```mermaid
flowchart TD
    subgraph Presentation
        A1[Gradio UI (Python)]
        A2[Flask UI (Python)]
        A3[Vite / React UI (nodejs-ui)]
    end
    subgraph API
        B1[FastAPI Server (planexe_api)]
    end
    subgraph Application
        C1[Plan Pipeline Orchestrator
(planexe.plan.*)]
        C2[Prompt Catalog]
        C3[Expert Systems]
    end
    subgraph Infrastructure
        D1[LLM Factory
(OpenRouter / Ollama / LM Studio)]
        D2[PostgreSQL (SQLAlchemy ORM)]
        D3[Filesystem Run Artifacts]
    end
    A1 --HTTP--> B1
    A2 --HTTP--> B1
    A3 --HTTP--> B1
    B1 --Sub-process--> C1
    C1 --Reads/Writes--> D3
    C1 --Persists--> D2
    C1 --Calls--> D1
    C1 --Uses--> C2
    C1 --Uses--> C3
```

For detailed documentation on the plan pipeline orchestrator (`run_plan_pipeline.py`), see [run_plan_pipeline_documentation.md](docs/run_plan_pipeline_documentation.md).

### Key Components
1. **planexe.plan** – Pure-Python pipeline that breaks the prompt into phases such as SWOT, WBS, cost estimation, report rendering.
2. **planexe_api** – FastAPI micro-service exposing a clean REST interface for creating and monitoring plan jobs.
3. **planexe.ui_flask** – Developer-friendly Flask server showcasing SSE progress streaming.
4. **nodejs-ui** – Optional modern browser client built with Vite + React; consumes the REST API.
5. **LLM Factory** – `planexe.llm_factory` selects the best available model (OpenRouter or local) at runtime.
6. **Database Layer** – `planexe_api.database` provides Postgres persistence for plans, files, and metrics.

## Directory Structure (simplified)

```text
PlanExe/
├── planexe/             # Core business & pipeline logic (Python pkg)
│   ├── plan/            # Orchestration & pipeline stages
│   ├── ui_flask/        # Lightweight Flask UI
│   └── ...
├── planexe_api/         # Production-grade FastAPI server
├── nodejs-ui/           # Vite + React single-page frontend
├── nodejs-client/       # Example JS/TS client for API consumption
├── docs/                # Additional markdown docs & ADRs
├── extra/               # Provider-specific setup guides (Ollama, LM Studio, OpenRouter)
├── run/                 # Generated artefacts (<run_id>) during execution
├── pyproject.toml       # project metadata
└── README.md            # You are here
```

## Current Development Workflow (v0.1.6)

**CRITICAL NOTE**: The system is currently not usable for end users due to progress monitoring bugs. See CHANGELOG.md v0.1.6 for details.

### Setup Environment
1. Clone & create virtual env:
   ```powershell
   git clone https://github.com/neoneye/PlanExe.git
   cd PlanExe
   python -m venv .venv
   .venv\Scripts\Activate
   pip install -e ".[dev,gradio-ui]"
   ```

2. **REQUIRED**: Copy `.env.example` to `.env` and add your API keys:
   ```
   OPENAI_API_KEY=your_key_here
   OPENROUTER_API_KEY=your_key_here
   ```

### Running the Full System (3 Components Required)

**You need ALL 3 components running for the system to work:**

```powershell
# Terminal 1 – FastAPI Backend (port 8080)
python -m planexe_api.api

# Terminal 2 – Next.js Frontend (port 3000)
cd planexe-frontend
npm install
npm run dev

# Terminal 3 – Luigi Pipeline Execution
# (Automatically triggered when plans are created via API)
# NO separate command needed - pipeline runs as subprocess
```

### How Plan Generation Actually Works

1. **User submits plan** via frontend (http://localhost:3000)
2. **FastAPI creates plan** and launches Luigi pipeline as subprocess
3. **Luigi pipeline executes 61 tasks** (python -m planexe.plan.run_plan_pipeline)
4. **Progress monitoring** streams updates back to frontend via SSE
5. **Generated files** stored in `run/{plan_id}/` directory

### Simplified One-Command Setup

```powershell
# Start both backend and frontend together
cd planexe-frontend
npm run go
```

### Testing Plan Generation

```bash
# Create a plan via API
curl -X POST "http://localhost:8080/api/plans" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test plan", "llm_model": "gpt-5-mini-2025-08-07", "speed_vs_detail": "fast_but_skip_details"}'

# Check plan status
curl "http://localhost:8080/api/plans/{plan_id}"

# Monitor progress (note: currently shows false completion)
curl "http://localhost:8080/api/plans/{plan_id}/stream"
```

### Known Issues (v0.1.6)
- ❌ Progress monitoring shows false "95% complete" immediately
- ❌ File access API crashes with Internal Server Error
- ❌ Users cannot download generated reports
- ❌ No reliable way to know when plans actually complete

See `docs/24SeptUXBreakdownHandover.md` for detailed issue analysis.

## Automated Tests

```powershell
pytest -q
```

Current coverage focuses on utility functions; contributions of pipeline unit tests are welcome.

## Deployment

Production deployments use **Railway** for Postgres + container hosting. A sample Dockerfile lives in `docker/` and sets up Gunicorn + Uvicorn workers for `planexe_api`. Refer to `docker/README.md` for step-by-step instructions.

## Extending the Pipeline

Add a new stage by implementing `planexe.plan.<your_stage>.py`, then register it in `planexe.plan.run_plan_pipeline`. The pipeline will automatically stream progress updates via SSE to all UIs.

---

*This section was generated on 2025-09-19 and will evolve as the codebase grows.*
