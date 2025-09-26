"""
Author: Claude Code using Sonnet 4
Date: 2025-09-24
PURPOSE: Clean FastAPI REST API for PlanExe - proper service architecture following SRP
SRP and DRY check: Pass - Single responsibility of HTTP routing, delegates execution to services
"""
import asyncio
import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette import EventSourceResponse

from planexe.plan.filenames import FilenameEnum
from planexe.plan.generate_run_id import generate_run_id
from planexe.plan.pipeline_environment import PipelineEnvironmentEnum
from planexe.plan.speedvsdetail import SpeedVsDetailEnum
from planexe.prompt.prompt_catalog import PromptCatalog
from planexe.utils.planexe_config import PlanExeConfig
from planexe.utils.planexe_dotenv import PlanExeDotEnv, DotEnvKeyEnum
from planexe.llm_factory import LLMInfo

from planexe_api.models import (
    CreatePlanRequest, PlanResponse, PlanProgressEvent, LLMModel,
    PromptExample, PlanFilesResponse, APIError, HealthResponse,
    PlanStatus, SpeedVsDetail
)
from planexe_api.database import (
    get_database, create_tables, DatabaseService, Plan, LLMInteraction,
    PlanFile, PlanMetrics, SessionLocal
)
from planexe_api.services.pipeline_execution_service import PipelineExecutionService

# Initialize FastAPI app
app = FastAPI(
    title="PlanExe API",
    description="REST API for PlanExe - Transform ideas into detailed plans using AI",
    version="1.0.0",
)

# Environment detection
IS_DEVELOPMENT = os.environ.get("PLANEXE_CLOUD_MODE", "false").lower() != "true"

# CORS configuration - only enable for local development
if IS_DEVELOPMENT:
    print("Development mode: CORS enabled for localhost:3000")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    print("Production mode: CORS disabled, serving static UI")

# Static file serving for production (Railway single-service deployment)
if not IS_DEVELOPMENT:
    static_dir = Path("/app/ui_static")
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
        print(f"Serving static UI from: {static_dir}")
    else:
        print(f"Warning: Static UI directory not found: {static_dir}")
        print("   This is expected in local development mode")

# Initialize cloud-native configuration system
print("=== PlanExe API Initialization ===")
planexe_config = PlanExeConfig.load()
RUN_DIR = "run"

if planexe_config.cloud_mode:
    print("Cloud environment detected - using cloud-native configuration")
else:
    print("Local development environment - using file-based configuration")

# Load environment variables with hybrid approach (cloud-native)
print("Loading environment configuration...")
planexe_dotenv = PlanExeDotEnv.load()  # Automatically uses hybrid loading in cloud mode
print(f"Configuration loaded from: {planexe_dotenv.dotenv_path}")

# CRITICAL: Ensure environment variables are available in os.environ for Luigi subprocess
print("Merging configuration into system environment...")
planexe_dotenv.update_os_environ()

# Validate API keys are available
api_keys_to_check = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
available_keys = []
for key in api_keys_to_check:
    value = os.environ.get(key)
    if value:
        available_keys.append(key)
        print(f"  [OK] {key}: Available")
    else:
        print(f"  [MISSING] {key}: Not available")

print(f"Environment validation complete - {len(available_keys)} API keys available")

# Set up paths
planexe_project_root = Path(__file__).parent.parent.absolute()
override_run_dir = planexe_dotenv.get_absolute_path_to_dir(DotEnvKeyEnum.PLANEXE_RUN_DIR.value)
if isinstance(override_run_dir, Path):
    run_dir = override_run_dir
else:
    run_dir = planexe_project_root / RUN_DIR

# Initialize services
prompt_catalog = PromptCatalog()
prompt_catalog.load_simple_plan_prompts()
llm_info = LLMInfo.obtain_info()
pipeline_service = PipelineExecutionService(planexe_project_root)

# Database initialization
database = get_database()
create_tables()


def execute_plan_async(plan_id: str, request: CreatePlanRequest) -> None:
    """Execute Luigi pipeline asynchronously using the dedicated service"""
    db = SessionLocal()
    try:
        db_service = DatabaseService(db)
        pipeline_service.execute_plan(plan_id, request, db_service)
    except Exception as e:
        print(f"Exception in plan execution: {e}")
    finally:
        try:
            db.close()
        except Exception as e:
            print(f"Error closing database: {e}")


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        version="1.0.0",
        planexe_version="2025.5.20",
        available_models=len(llm_info.llm_config_items)
    )


@app.get("/ping")
async def ping():
    """Ultra simple ping endpoint"""
    return {"ping": "pong"}


# LLM models endpoint
@app.get("/api/models", response_model=List[LLMModel])
async def get_models():
    """Get available LLM models"""
    try:
        models = []
        for config in llm_info.llm_config_items:
            model = LLMModel(
                id=config.model_id,
                name=config.model_name,
                provider=config.provider,
                description=f"{config.provider} - {config.model_name}"
            )
            models.append(model)
        return models
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}")


# Prompt examples endpoint
@app.get("/api/prompts", response_model=List[PromptExample])
async def get_prompts():
    """Get example prompts"""
    try:
        examples = []
        for prompt in prompt_catalog.prompts:
            example = PromptExample(
                title=prompt.title,
                description=prompt.description,
                prompt=prompt.prompt,
                category=getattr(prompt, 'category', 'general')
            )
            examples.append(example)
        return examples
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prompts: {str(e)}")


# Plan creation endpoint
@app.post("/api/plans", response_model=PlanResponse)
async def create_plan(request: CreatePlanRequest, db: DatabaseService = Depends(get_database)):
    """Create a new plan and start background processing"""
    try:
        # Generate unique plan ID and directory
        start_time = datetime.utcnow()
        plan_id = generate_run_id("PlanExe", start_time)

        # Create run directory
        run_id_dir = run_dir / plan_id
        run_id_dir.mkdir(parents=True, exist_ok=True)
        print(f"DEBUG: Directory created successfully")

        # Create plan in database
        plan_data = {
            "plan_id": plan_id,
            "prompt": request.prompt,
            "llm_model": request.llm_model,
            "speed_vs_detail": request.speed_vs_detail.value,
            "openrouter_api_key_hash": None,
            "status": PlanStatus.pending.value,
            "progress_percentage": 0,
            "progress_message": "Plan queued for processing...",
            "output_dir": str(run_id_dir)
        }

        plan = db.create_plan(plan_data)
        print(f"DEBUG: Plan created in database")

        # Start background execution using threading (Windows compatibility)
        thread = threading.Thread(
            target=execute_plan_async,
            args=(plan_id, request),
            name=f"PlanExecution-{plan_id}",
            daemon=True
        )
        thread.start()
        print(f"DEBUG: Thread started: {thread.name}")

        # Convert database model to response
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

    except Exception as e:
        print(f"Error creating plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create plan: {str(e)}")


# Plan details endpoint
@app.get("/api/plans/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Get plan details"""
    try:
        plan = db.get_plan(plan_id)
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plan: {str(e)}")


# SSE stream endpoint for real-time progress
@app.get("/api/plans/{plan_id}/stream")
async def stream_plan_progress(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Stream real-time progress updates via Server-Sent Events"""

    async def event_generator():
        # Check if plan exists
        plan = db.get_plan(plan_id)
        if not plan:
            yield {"event": "error", "data": json.dumps({"message": "Plan not found"})}
            return

        # Get progress stream from service
        progress_queue = pipeline_service.get_progress_stream(plan_id)
        if not progress_queue:
            yield {"event": "error", "data": json.dumps({"message": "Stream could not be established."})}
            return

        try:
            while True:
                # Non-blocking check for messages
                try:
                    update = progress_queue.get_nowait()
                except:  # queue.Empty or similar
                    await asyncio.sleep(0.1)  # Wait briefly
                    continue

                if update is None:  # End signal
                    yield {"event": "end", "data": "Stream ended"}
                    break

                # Send update to client
                yield {"event": "task_update", "data": json.dumps(update)}

        except asyncio.CancelledError:
            print(f"Stream for plan {plan_id} was cancelled by client.")
        finally:
            # Clean up progress stream
            pipeline_service.cleanup_progress_stream(plan_id)

    return EventSourceResponse(event_generator())


# Plan files endpoint
@app.get("/api/plans/{plan_id}/files", response_model=PlanFilesResponse)
async def get_plan_files(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Get list of files generated by a plan"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        files = db.get_plan_files(plan_id)

        return PlanFilesResponse(
            plan_id=plan_id,
            files=[
                {
                    "filename": f.filename,
                    "file_type": f.file_type,
                    "file_size_bytes": f.file_size_bytes,
                    "generated_by_stage": f.generated_by_stage,
                    "created_at": f.created_at
                }
                for f in files
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plan files: {str(e)}")


# File download endpoints
@app.get("/api/plans/{plan_id}/report")
async def download_plan_report(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Download the final HTML report for a plan"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        report_path = Path(plan.output_dir) / "999-final-report.html"

        if not report_path.exists():
            raise HTTPException(status_code=404, detail="Report not found")

        return FileResponse(
            path=str(report_path),
            filename=f"{plan_id}-report.html",
            media_type="text/html"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download report: {str(e)}")


@app.get("/api/plans/{plan_id}/files/{filename}")
async def download_plan_file(plan_id: str, filename: str, db: DatabaseService = Depends(get_database)):
    """Download a specific file from a plan"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        file_path = Path(plan.output_dir) / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=str(file_path),
            filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


# Plan management endpoints
@app.delete("/api/plans/{plan_id}")
async def delete_plan(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Delete a plan and its associated files"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Delete files from filesystem
        output_dir = Path(plan.output_dir)
        if output_dir.exists():
            import shutil
            shutil.rmtree(output_dir)

        # Delete from database
        db.delete_plan(plan_id)

        return {"message": f"Plan {plan_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {str(e)}")


@app.get("/api/plans", response_model=List[PlanResponse])
async def list_plans(db: DatabaseService = Depends(get_database)):
    """Get list of all plans"""
    try:
        plans = db.get_all_plans()

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plans: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)