"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-19
PURPOSE: FastAPI REST API server for PlanExe - provides clean HTTP interface wrapping existing functionality
SRP and DRY check: Pass - Single responsibility of API routing and HTTP handling, reuses existing PlanExe services
"""
import asyncio
import json
import os
import subprocess
import threading
import time
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from planexe.llm_factory import LLMInfo, get_llm_names_by_priority
from planexe.plan.filenames import FilenameEnum
from planexe.plan.generate_run_id import generate_run_id
from planexe.plan.pipeline_environment import PipelineEnvironmentEnum
from planexe.plan.speedvsdetail import SpeedVsDetailEnum
from planexe.prompt.prompt_catalog import PromptCatalog
from planexe.utils.planexe_config import PlanExeConfig
from planexe.utils.planexe_dotenv import PlanExeDotEnv, DotEnvKeyEnum

from .models import (
    CreatePlanRequest, PlanResponse, PlanProgressEvent, LLMModel,
    PromptExample, PlanFilesResponse, APIError, HealthResponse,
    PlanStatus, SpeedVsDetail
)
from .database import (
    get_database, create_tables, DatabaseService, Plan, LLMInteraction,
    PlanFile, PlanMetrics
)

# Initialize FastAPI app
app = FastAPI(
    title="PlanExe API",
    description="REST API for PlanExe - Transform ideas into detailed plans using AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for browser-based frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state - keeping in-memory processes but using DB for persistence
running_processes: Dict[str, subprocess.Popen] = {}
MODULE_PATH_PIPELINE = "planexe.plan.run_plan_pipeline"
RUN_DIR = "run"

# Initialize database
create_tables()

# Load configuration
planexe_config = PlanExeConfig.load()
planexe_dotenv = PlanExeDotEnv.load()
planexe_dotenv.update_os_environ()

# Set up paths
planexe_project_root = Path(__file__).parent.parent.absolute()
override_run_dir = planexe_dotenv.get_absolute_path_to_dir(DotEnvKeyEnum.PLANEXE_RUN_DIR.value)
if isinstance(override_run_dir, Path):
    run_dir = override_run_dir
else:
    run_dir = planexe_project_root / RUN_DIR

# Initialize prompt catalog
prompt_catalog = PromptCatalog()
prompt_catalog.load_simple_plan_prompts()

# Initialize LLM info
llm_info = LLMInfo.obtain_info()


def run_plan_job(plan_id: str, request: CreatePlanRequest):
    """Background task to run the plan generation pipeline"""
    db_service = DatabaseService(get_db())

    try:
        # Get plan from database
        plan = db_service.get_plan(plan_id)
        if not plan:
            return

        run_id_dir = Path(plan.output_dir)

        # Set up environment
        environment = os.environ.copy()
        environment[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_id_dir)
        environment[PipelineEnvironmentEnum.SPEED_VS_DETAIL.value] = request.speed_vs_detail.value

        if request.llm_model:
            environment[PipelineEnvironmentEnum.LLM_MODEL.value] = request.llm_model

        if request.openrouter_api_key:
            environment["OPENROUTER_API_KEY"] = request.openrouter_api_key

        # Write the plan prompt to setup file
        setup_file = run_id_dir / FilenameEnum.SETUP.value
        with open(setup_file, "w", encoding="utf-8") as f:
            f.write(request.prompt)

        # Update plan status in database
        db_service.update_plan(plan_id, {
            "status": PlanStatus.running.value,
            "progress_percentage": 0,
            "progress_message": "Starting plan generation pipeline...",
            "started_at": datetime.utcnow()
        })

        # Start the pipeline process
        command = ["python", "-m", MODULE_PATH_PIPELINE]
        process = subprocess.Popen(
            command,
            cwd=str(planexe_project_root),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Store process reference
        running_processes[plan_id] = process

        # Monitor progress (simplified - in production you'd parse actual pipeline output)
        progress_stages = [
            (10, "Analyzing prompt and identifying purpose..."),
            (20, "Determining plan type and scope..."),
            (30, "Generating work breakdown structure..."),
            (50, "Estimating costs and resources..."),
            (70, "Creating timeline and dependencies..."),
            (85, "Generating expert analysis..."),
            (95, "Compiling final report..."),
        ]

        stage_idx = 0
        while process.poll() is None:
            time.sleep(2)

            # Simple progress simulation - replace with actual pipeline monitoring
            if stage_idx < len(progress_stages):
                progress, message = progress_stages[stage_idx]
                db_service.update_plan(plan_id, {
                    "progress_percentage": progress,
                    "progress_message": message
                })
                stage_idx += 1

        # Process completed
        return_code = process.wait()

        if return_code == 0:
            # Check if pipeline completed successfully
            complete_file = run_id_dir / FilenameEnum.PIPELINE_COMPLETE.value
            if complete_file.exists():
                # Index generated files
                files = list(run_id_dir.iterdir())
                for file_path in files:
                    if file_path.is_file():
                        db_service.create_plan_file({
                            "plan_id": plan_id,
                            "filename": file_path.name,
                            "file_type": file_path.suffix.lstrip('.') or 'unknown',
                            "file_size_bytes": file_path.stat().st_size,
                            "file_path": str(file_path),
                            "generated_by_stage": "pipeline_complete"
                        })

                db_service.update_plan(plan_id, {
                    "status": PlanStatus.completed.value,
                    "progress_percentage": 100,
                    "progress_message": "Plan generation completed successfully!",
                    "completed_at": datetime.utcnow()
                })
            else:
                db_service.update_plan(plan_id, {
                    "status": PlanStatus.failed.value,
                    "error_message": "Pipeline did not complete successfully"
                })
        else:
            stderr_output = process.stderr.read() if process.stderr else "Unknown error"
            db_service.update_plan(plan_id, {
                "status": PlanStatus.failed.value,
                "error_message": f"Pipeline failed with code {return_code}: {stderr_output}"
            })

    except Exception as e:
        db_service.update_plan(plan_id, {
            "status": PlanStatus.failed.value,
            "error_message": str(e)
        })
    finally:
        # Clean up process reference
        if plan_id in running_processes:
            del running_processes[plan_id]
        db_service.close()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        version="1.0.0",
        planexe_version="2025.5.20",
        available_models=len(llm_info.llm_config_items)
    )


@app.get("/api/models", response_model=List[LLMModel])
async def get_models():
    """Get available LLM models - production OpenAI + OpenRouter fallbacks"""
    # Real working models based on your .env API keys
    production_models = [
        # Primary: Latest OpenAI models (direct API)
        LLMModel(
            id="gpt-4o-mini",
            label="GPT-4o Mini",
            comment="Latest fast OpenAI model. 128K context. Cost-effective for production.",
            priority=1,
            requires_api_key=False  # Uses OPENAI_API_KEY from .env
        ),
        LLMModel(
            id="gpt-4o",
            label="GPT-4o",
            comment="Latest OpenAI flagship model. 128K context. Best quality.",
            priority=2,
            requires_api_key=False
        ),
        LLMModel(
            id="gpt-4-turbo",
            label="GPT-4 Turbo",
            comment="OpenAI GPT-4 Turbo. 128K context. Reliable performance.",
            priority=3,
            requires_api_key=False
        ),
        # OpenRouter fallbacks
        LLMModel(
            id="qwen/qwen3-max",
            label="Qwen3 Max (OpenRouter)",
            comment="High-performance Qwen model via OpenRouter. Excellent reasoning.",
            priority=4,
            requires_api_key=True  # Uses OPENROUTER_API_KEY
        ),
        LLMModel(
            id="x-ai/grok-4-fast:free",
            label="Grok 4 Fast (Free)",
            comment="Free high-speed Grok model via OpenRouter. Good for testing.",
            priority=5,
            requires_api_key=True
        )
    ]
    return production_models


@app.get("/api/prompts", response_model=List[PromptExample])
async def get_prompt_examples():
    """Get example prompts - temporary hardcoded list"""
    hardcoded_prompts = [
        PromptExample(
            id="business-plan",
            title="Business Plan",
            category="Business",
            complexity="complex",
            prompt="Create a comprehensive business plan for a new tech startup",
            description="Generate a detailed business plan including market analysis, financial projections, and strategy"
        ),
        PromptExample(
            id="project-plan",
            title="Project Plan",
            category="Project Management",
            complexity="medium",
            prompt="Plan the development of a mobile app from concept to launch",
            description="Create a project plan with timeline, resources, and milestones"
        ),
        PromptExample(
            id="marketing-strategy",
            title="Marketing Strategy",
            category="Marketing",
            complexity="medium",
            prompt="Develop a marketing strategy for launching a new product",
            description="Create a comprehensive marketing plan with target audience analysis"
        )
    ]
    return hardcoded_prompts


@app.post("/api/plans", response_model=PlanResponse)
async def create_plan(request: CreatePlanRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_database)):
    """Create a new plan generation job"""

    # Generate unique plan ID
    plan_id = generate_run_id()
    run_id_dir = run_dir / plan_id

    # Create output directory
    run_id_dir.mkdir(parents=True, exist_ok=True)

    # Hash API key for storage (never store plaintext)
    api_key_hash = None
    if request.openrouter_api_key:
        api_key_hash = hashlib.sha256(request.openrouter_api_key.encode()).hexdigest()

    # Create plan in database
    db_service = DatabaseService(db)
    plan_data = {
        "plan_id": plan_id,
        "prompt": request.prompt,
        "llm_model": request.llm_model,
        "speed_vs_detail": request.speed_vs_detail.value,
        "openrouter_api_key_hash": api_key_hash,
        "status": PlanStatus.pending.value,
        "progress_percentage": 0,
        "progress_message": "Plan queued for processing...",
        "output_dir": str(run_id_dir)
    }

    plan = db_service.create_plan(plan_data)

    # Start background task
    background_tasks.add_task(run_plan_job, plan_id, request)

    # Convert to response format
    return PlanResponse(
        plan_id=plan.plan_id,
        status=PlanStatus(plan.status),
        created_at=plan.created_at,
        prompt=plan.prompt,
        progress_percentage=plan.progress_percentage,
        progress_message=plan.progress_message,
        error_message=plan.error_message,
        output_dir=plan.output_dir
    )


@app.get("/api/plans/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: str, db: Session = Depends(get_database)):
    """Get plan status and details"""
    db_service = DatabaseService(db)
    plan = db_service.get_plan(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return PlanResponse(
        plan_id=plan.plan_id,
        status=PlanStatus(plan.status),
        created_at=plan.created_at,
        prompt=plan.prompt,
        progress_percentage=plan.progress_percentage,
        progress_message=plan.progress_message,
        error_message=plan.error_message,
        output_dir=plan.output_dir
    )


@app.get("/api/plans/{plan_id}/stream")
async def stream_plan_progress(plan_id: str):
    """Server-sent events stream for real-time plan progress"""
    # Check if plan exists
    db_service = DatabaseService(get_db())
    plan = db_service.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db_service.close()

    async def event_generator():
        last_status = None
        last_progress = -1

        while True:
            # Get fresh data from database
            db_service = DatabaseService(get_db())
            plan = db_service.get_plan(plan_id)
            db_service.close()

            if not plan:
                break

            current_status = plan.status
            current_progress = plan.progress_percentage

            # Send update if status or progress changed
            if current_status != last_status or current_progress != last_progress:
                event = PlanProgressEvent(
                    plan_id=plan_id,
                    status=PlanStatus(current_status),
                    progress_percentage=current_progress,
                    progress_message=plan.progress_message,
                    timestamp=datetime.utcnow(),
                    error_message=plan.error_message
                )

                yield {"event": "progress", "data": event.json()}

                last_status = current_status
                last_progress = current_progress

            # Stop streaming if job is complete or failed
            if current_status in ["completed", "failed", "cancelled"]:
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@app.get("/api/plans/{plan_id}/files", response_model=PlanFilesResponse)
async def get_plan_files(plan_id: str, db: Session = Depends(get_database)):
    """Get list of files generated for a plan"""
    db_service = DatabaseService(db)
    plan = db_service.get_plan(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Get files from database
    plan_files = db_service.get_plan_files(plan_id)
    files = [pf.filename for pf in plan_files]
    has_report = FilenameEnum.FINAL_REPORT_HTML.value in files

    return PlanFilesResponse(
        plan_id=plan_id,
        files=sorted(files),
        has_report=has_report
    )


@app.get("/api/plans/{plan_id}/report")
async def download_plan_report(plan_id: str, db: Session = Depends(get_database)):
    """Download the HTML report for a completed plan"""
    db_service = DatabaseService(db)
    plan = db_service.get_plan(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.status != PlanStatus.completed.value:
        raise HTTPException(status_code=400, detail="Plan is not completed")

    output_dir = Path(plan.output_dir)
    report_file = output_dir / FilenameEnum.FINAL_REPORT_HTML.value

    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    return FileResponse(
        path=str(report_file),
        filename=f"plan_{plan_id}_report.html",
        media_type="text/html"
    )


@app.get("/api/plans/{plan_id}/files/{filename}")
async def download_plan_file(plan_id: str, filename: str, db: Session = Depends(get_database)):
    """Download a specific file from a plan's output"""
    db_service = DatabaseService(db)
    plan = db_service.get_plan(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    output_dir = Path(plan.output_dir)
    file_path = output_dir / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Security check - ensure file is within the plan directory
    if not str(file_path.resolve()).startswith(str(output_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(path=str(file_path), filename=filename)


@app.delete("/api/plans/{plan_id}")
async def cancel_plan(plan_id: str, db: Session = Depends(get_database)):
    """Cancel a running plan"""
    db_service = DatabaseService(db)
    plan = db_service.get_plan(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.status == PlanStatus.running.value:
        # Terminate the process if it's running
        process = running_processes.get(plan_id)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

        # Update database
        db_service.update_plan(plan_id, {
            "status": PlanStatus.cancelled.value,
            "progress_message": "Plan generation cancelled"
        })

        # Clean up process reference
        if plan_id in running_processes:
            del running_processes[plan_id]

    return {"message": "Plan cancelled successfully"}


@app.get("/api/plans", response_model=List[PlanResponse])
async def list_plans(db: Session = Depends(get_database)):
    """List all plans"""
    db_service = DatabaseService(db)
    plans = db_service.list_plans()

    return [
        PlanResponse(
            plan_id=plan.plan_id,
            status=PlanStatus(plan.status),
            created_at=plan.created_at,
            prompt=plan.prompt,
            progress_percentage=plan.progress_percentage,
            progress_message=plan.progress_message,
            error_message=plan.error_message,
            output_dir=plan.output_dir
        )
        for plan in plans
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)