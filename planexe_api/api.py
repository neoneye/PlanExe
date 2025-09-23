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

from planexe_api.models import (
    CreatePlanRequest, PlanResponse, PlanProgressEvent, LLMModel,
    PromptExample, PlanFilesResponse, APIError, HealthResponse,
    PlanStatus, SpeedVsDetail
)
from planexe_api.database import (
    get_database, create_tables, DatabaseService, Plan, LLMInteraction,
    PlanFile, PlanMetrics, SessionLocal
)

# Initialize FastAPI app
app = FastAPI(
    title="PlanExe API",
    description="REST API for PlanExe - Transform ideas into detailed plans using AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Allow all origins during development - this eliminates all CORS issues
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state - keeping in-memory processes but using DB for persistence
running_processes: Dict[str, subprocess.Popen] = {}
progress_streams: Dict[str, asyncio.Queue] = {}  # In-memory queues for real-time progress
MODULE_PATH_PIPELINE = "planexe.plan.run_plan_pipeline"
RUN_DIR = "run"

# Initialize database
create_tables()

# Load configuration
planexe_config = PlanExeConfig.load()
print("DEBUG ENV: Loading .env file...")
planexe_dotenv = PlanExeDotEnv.load()
print(f"DEBUG ENV: Loaded .env from: {planexe_dotenv.dotenv_path}")
print(f"DEBUG ENV: .env contains {len(planexe_dotenv.dotenv_dict)} variables")

# Log API keys from .env file before updating os.environ
api_keys_in_dotenv = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
print("DEBUG ENV: API keys found in .env file:")
for key in api_keys_in_dotenv:
    value = planexe_dotenv.dotenv_dict.get(key)
    if value:
        print(f"  {key}: {'*' * 10}...{value[-4:] if len(value) > 4 else '****'}")
    else:
        print(f"  {key}: NOT FOUND in .env")

print("DEBUG ENV: Updating os.environ with .env values...")
planexe_dotenv.update_os_environ()

# Verify API keys are now in os.environ
print("DEBUG ENV: API keys in os.environ after .env update:")
for key in api_keys_in_dotenv:
    value = os.environ.get(key)
    if value:
        print(f"  {key}: {'*' * 10}...{value[-4:] if len(value) > 4 else '****'}")
    else:
        print(f"  {key}: NOT FOUND in os.environ")

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
    # Create a queue for this job to send progress updates
    progress_queue = asyncio.Queue()
    progress_streams[plan_id] = progress_queue
    """Background task to run the plan generation pipeline"""
    print(f"DEBUG: Starting run_plan_job for plan_id: {plan_id}")

    # Create database session directly for background task
    db = SessionLocal()
    try:
        db_service = DatabaseService(db)
        print("DEBUG: Database service created successfully")
    except Exception as e:
        print(f"Database connection error: {e}")
        return

    try:
        # Get plan from database
        print(f"DEBUG: Looking up plan in database: {plan_id}")
        plan = db_service.get_plan(plan_id)
        if not plan:
            print(f"DEBUG: Plan not found in database: {plan_id}")
            return
        print(f"DEBUG: Plan found: {plan.plan_id}, status: {plan.status}")

        run_id_dir = Path(plan.output_dir)

        # Set up environment with comprehensive logging
        print(f"DEBUG ENV: Starting environment setup for plan {plan_id}")

        # Check what API keys are available in os.environ before copying
        api_keys_to_check = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
        print("DEBUG ENV: API keys in os.environ before copy:")
        for key in api_keys_to_check:
            value = os.environ.get(key)
            if value:
                print(f"  {key}: {'*' * 10}...{value[-4:] if len(value) > 4 else '****'}")
            else:
                print(f"  {key}: NOT FOUND")

        environment = os.environ.copy()
        print(f"DEBUG ENV: Copied os.environ, total variables: {len(environment)}")

        # Add pipeline-specific environment variables
        environment[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_id_dir)
        print(f"DEBUG ENV: Set RUN_ID_DIR = {str(run_id_dir)}")

        # Map API enum values to pipeline enum values
        speed_vs_detail_mapping = {
            "fast_but_skip_details": "fast_but_skip_details",
            "balanced_speed_and_detail": "all_details_but_slow",  # Map balanced to detailed
            "all_details_but_slow": "all_details_but_slow"
        }
        pipeline_speed_value = speed_vs_detail_mapping.get(request.speed_vs_detail.value, "all_details_but_slow")
        environment[PipelineEnvironmentEnum.SPEED_VS_DETAIL.value] = pipeline_speed_value
        print(f"DEBUG ENV: Set SPEED_VS_DETAIL = {pipeline_speed_value}")

        if request.llm_model:
            environment[PipelineEnvironmentEnum.LLM_MODEL.value] = request.llm_model
            print(f"DEBUG ENV: Set LLM_MODEL = {request.llm_model}")

        if request.openrouter_api_key:
            environment["OPENROUTER_API_KEY"] = request.openrouter_api_key
            print(f"DEBUG ENV: Override OPENROUTER_API_KEY from request")

        # Final check of API keys in subprocess environment
        print("DEBUG ENV: Final API keys in subprocess environment:")
        for key in api_keys_to_check:
            value = environment.get(key)
            if value:
                print(f"  {key}: {'*' * 10}...{value[-4:] if len(value) > 4 else '****'}")
            else:
                print(f"  {key}: NOT FOUND IN SUBPROCESS ENV")

        print(f"DEBUG ENV: Final subprocess environment variables count: {len(environment)}")

        # Create START_TIME file as expected by Luigi pipeline
        start_time_file = run_id_dir / FilenameEnum.START_TIME.value
        start_time_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "plan_id": plan_id
        }
        with open(start_time_file, "w", encoding="utf-8") as f:
            json.dump(start_time_data, f, indent=2)

        # Write the plan prompt to INITIAL_PLAN file as expected by Luigi pipeline
        initial_plan_file = run_id_dir / FilenameEnum.INITIAL_PLAN.value
        with open(initial_plan_file, "w", encoding="utf-8") as f:
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
        print(f"DEBUG: Starting subprocess with command: {command}")
        print(f"DEBUG: Working directory: {planexe_project_root}")
        print(f"DEBUG: RUN_ID_DIR env var: {environment.get('RUN_ID_DIR')}")
        print(f"DEBUG ENV: Subprocess will receive {len(environment)} environment variables")
        print(f"DEBUG ENV: Key pipeline variables for subprocess:")
        for key in ["RUN_ID_DIR", "SPEED_VS_DETAIL", "LLM_MODEL", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
            value = environment.get(key)
            if key.endswith("_API_KEY") and value:
                print(f"  {key}: {'*' * 10}...{value[-4:] if len(value) > 4 else '****'}")
            elif value:
                print(f"  {key}: {value}")
            else:
                print(f"  {key}: NOT SET")

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
        print(f"DEBUG: Subprocess started with PID: {process.pid}")

        # Store process reference
        running_processes[plan_id] = process

        # Monitor actual Luigi pipeline progress by parsing stdout
        import re
        completed_tasks = set()
        total_tasks = 61  # Actual count of Luigi task classes

        # Monitor stdout and send progress updates to the queue
        import threading
        
        def read_stdout():
            """Stream raw Luigi pipeline logs directly to frontend terminal"""
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if not line:
                        continue

                    # Send raw log line to frontend terminal
                    log_data = {
                        "type": "log", 
                        "message": line,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    try:
                        progress_queue.put_nowait(log_data)
                    except asyncio.QueueFull:
                        print(f"Warning: Progress queue for plan {plan_id} is full.")
                    
                    # Also print to server console for debugging
                    print(f"Luigi: {line}")

                # Send completion signal
                try:
                    completion_data = {
                        "type": "status",
                        "status": "stdout_closed",
                        "message": "Pipeline stdout stream closed"
                    }
                    progress_queue.put_nowait(completion_data)
                except asyncio.QueueFull:
                    pass
                    
                process.stdout.close()
                
        def read_stderr():
            """Stream error logs to frontend terminal"""
            if process.stderr:
                for line in iter(process.stderr.readline, ''):
                    line = line.strip()
                    if line:
                        # Send error line to frontend terminal
                        error_data = {
                            "type": "log", 
                            "message": f"ERROR: {line}",
                            "timestamp": datetime.utcnow().isoformat(),
                            "level": "error"
                        }
                        try:
                            progress_queue.put_nowait(error_data)
                        except asyncio.QueueFull:
                            print(f"Warning: Progress queue for plan {plan_id} is full.")
                        
                        # Also print to server console for debugging
                        print(f"Luigi ERROR: {line}")
                process.stderr.close()
        
        # Start threads to read both stdout and stderr
        stdout_thread = threading.Thread(target=read_stdout)
        stderr_thread = threading.Thread(target=read_stderr)
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for process to complete
        return_code = process.wait()
        
        # Wait for threads to finish
        stdout_thread.join()
        stderr_thread.join()

        # Process completed
        return_code = process.wait()

        if return_code == 0:
            # Check if pipeline completed successfully
            complete_file = run_id_dir / FilenameEnum.PIPELINE_COMPLETE.value
            if complete_file.exists():
                # Send success message to terminal
                try:
                    success_data = {
                        "type": "status",
                        "status": "completed",
                        "message": "✅ Pipeline completed successfully! All files generated."
                    }
                    progress_queue.put_nowait(success_data)
                except asyncio.QueueFull:
                    pass

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
                # Send failure message to terminal
                try:
                    failure_data = {
                        "type": "status",
                        "status": "failed",
                        "message": "❌ Pipeline completed but final output file not found"
                    }
                    progress_queue.put_nowait(failure_data)
                except asyncio.QueueFull:
                    pass

                db_service.update_plan(plan_id, {
                    "status": PlanStatus.failed.value,
                    "error_message": "Pipeline did not complete successfully"
                })
        else:
            # Send failure message to terminal
            try:
                failure_data = {
                    "type": "status",
                    "status": "failed",
                    "message": f"❌ Pipeline failed with exit code {return_code}"
                }
                progress_queue.put_nowait(failure_data)
            except asyncio.QueueFull:
                pass

            stderr_output = process.stderr.read() if process.stderr else "Unknown error"
            db_service.update_plan(plan_id, {
                "status": PlanStatus.failed.value,
                "error_message": f"Pipeline failed with code {return_code}: {stderr_output}"
            })

    except Exception as e:
        print(f"Exception in run_plan_job: {e}")
        
        # Send exception message to terminal
        if plan_id in progress_streams:
            try:
                exception_data = {
                    "type": "status",
                    "status": "failed",
                    "message": f"💥 Fatal error in pipeline: {str(e)}"
                }
                progress_streams[plan_id].put_nowait(exception_data)
            except asyncio.QueueFull:
                pass

        try:
            db_service.update_plan(plan_id, {
                "status": PlanStatus.failed.value,
                "error_message": str(e)
            })
        except Exception as db_err:
            print(f"Failed to update plan status: {db_err}")
    finally:
        # Clean up process reference and signal end of stream
        if plan_id in running_processes:
            del running_processes[plan_id]
        if plan_id in progress_streams:
            try:
                progress_streams[plan_id].put_nowait(None)  # Signal end
            except asyncio.QueueFull:
                pass # If full, consumer will eventually get there
        # Close database session
        try:
            db.close()
        except Exception as e:
            print(f"Error closing database: {e}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        version="1.0.0",
        planexe_version="2025.5.20",
        available_models=len(llm_info.llm_config_items)
    )

@app.get("/test-models")
async def test_models_simple():
    """Simple test endpoint for models"""
    return {"test": "working", "models": ["gemini-2.0-flash", "gpt-4o-mini"]}

@app.get("/ping")
async def ping():
    """Ultra simple ping endpoint"""
    return {"ping": "pong"}

@app.post("/debug-plan")
async def debug_plan(request: CreatePlanRequest):
    """Debug version that logs everything"""
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info(f"Received request: {request}")

    try:
        from datetime import datetime
        from planexe.plan.generate_run_id import generate_run_id

        start_time = datetime.utcnow()
        plan_id = generate_run_id(use_uuid=True, start_time=start_time)

        logger.info(f"Generated plan_id: {plan_id}")

        return {"status": "success", "plan_id": plan_id, "received": request.dict()}

    except Exception as e:
        logger.error(f"Error in debug_plan: {e}")
        import traceback
        traceback.print_exc()
        raise

@app.post("/test-request")
async def test_request(request: CreatePlanRequest):
    """Test endpoint to isolate request parsing issues"""
    return {"received": request.prompt, "speed": request.speed_vs_detail}


@app.post("/test-create-plan")
async def test_create_plan_simple():
    """Test the create plan logic without background tasks"""
    try:
        print("DEBUG: Starting test create plan")
        from planexe_api.models import CreatePlanRequest, SpeedVsDetail

        request = CreatePlanRequest(
            prompt="test",
            speed_vs_detail=SpeedVsDetail.fast_basic
        )
        print("DEBUG: Request created successfully")

        return {"success": True, "message": "Plan creation logic works"}
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.get("/api/models", response_model=List[LLMModel])
async def get_models():
    """Get available LLM models from llm_config.json"""
    from planexe.utils.planexe_llmconfig import PlanExeLLMConfig
    
    # Load current LLM configuration
    llm_config = PlanExeLLMConfig.load()
    models = []
    
    # Convert each config entry to LLMModel format
    for model_id, config in llm_config.llm_config_dict.items():
        priority = config.get("priority", 999)
        comment = config.get("comment", "")
        provider = config.get("provider", "unknown")
        
        # Determine if API key is required based on provider
        requires_api_key = provider in ["openrouter", "anthropic"]
        
        # Create friendly label
        label = model_id
        if priority <= 10:  # Only show priority for configured models
            label = f"{model_id} (Priority {priority})"
        
        models.append(LLMModel(
            id=model_id,
            label=label,
            comment=comment,
            priority=priority,
            requires_api_key=requires_api_key
        ))
    
    # Sort by priority (lower numbers first)
    models.sort(key=lambda x: x.priority)
    return models


@app.get("/api/prompts", response_model=List[PromptExample])
async def get_prompt_examples():
    """Get example prompts - temporary hardcoded list"""
    hardcoded_prompts = [
        PromptExample(
            uuid="business-plan-001",
            title="Business Plan",
            prompt="Create a comprehensive business plan for a new tech startup including market analysis, financial projections, and strategy"
        ),
        PromptExample(
            uuid="project-plan-002",
            title="Project Plan",
            prompt="Plan the development of a mobile app from concept to launch with timeline, resources, and milestones"
        ),
        PromptExample(
            uuid="marketing-strategy-003",
            title="Marketing Strategy",
            prompt="Develop a marketing strategy for launching a new product with target audience analysis"
        )
    ]
    return hardcoded_prompts


async def _create_and_run_plan(request: CreatePlanRequest, background_tasks: BackgroundTasks, db: Session) -> Plan:
    """Helper function to create a new plan record and start the background job."""
    try:
        print(f"DEBUG: Starting _create_and_run_plan with request: {request}")

        # Generate unique plan ID
        start_time = datetime.utcnow()
        print(f"DEBUG: Generated start_time: {start_time}")

        plan_id = generate_run_id(use_uuid=True, start_time=start_time)
        print(f"DEBUG: Generated plan_id: {plan_id}")

        run_id_dir = (run_dir / plan_id).resolve()  # Convert to absolute path
        print(f"DEBUG: Run directory path: {run_id_dir}")

        # Create output directory
        run_id_dir.mkdir(parents=True, exist_ok=True)
        print(f"DEBUG: Directory created successfully")

        # Hash API key for storage (never store plaintext)
        api_key_hash = None
        if request.openrouter_api_key:
            api_key_hash = hashlib.sha256(request.openrouter_api_key.encode()).hexdigest()
        print(f"DEBUG: API key hash created")

        # Create plan in database
        db_service = DatabaseService(db)
        print(f"DEBUG: Database service created")

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
        print(f"DEBUG: Plan data prepared: {plan_data}")

        plan = db_service.create_plan(plan_data)
        print(f"DEBUG: Plan created in database")

        # Start background task
        background_tasks.add_task(run_plan_job, plan_id, request)
        print(f"DEBUG: Background task added")

        return plan

    except Exception as e:
        print(f"ERROR in _create_and_run_plan: {e}")
        import traceback
        traceback.print_exc()
        # Re-raise the exception to be handled by the calling endpoint
        raise

@app.post("/api/plans", response_model=PlanResponse)
async def create_plan(request: CreatePlanRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_database)):
    """Create a new plan generation job."""
    try:
        plan = await _create_and_run_plan(request, background_tasks, db)
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
        print(f"ERROR in create_plan: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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


@app.post("/api/plans/{plan_id}/retry", response_model=PlanResponse)
async def retry_plan(plan_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_database)):
    """Retries a failed or stuck plan by creating a new plan with the same settings."""
    db_service = DatabaseService(db)
    original_plan = db_service.get_plan(plan_id)

    if not original_plan:
        raise HTTPException(status_code=404, detail="Original plan not found")

    # Create a new request from the original plan's data
    retry_request = CreatePlanRequest(
        prompt=original_plan.prompt,
        llm_model=original_plan.llm_model,
        speed_vs_detail=SpeedVsDetail(original_plan.speed_vs_detail),
        # We don't have the original API key if it was per-request, so we use None
        openrouter_api_key=None
    )

    # Create and run the new plan using the refactored helper function
    new_plan = await _create_and_run_plan(retry_request, background_tasks, db)

    # Return the NEW plan's information
    return PlanResponse(
        plan_id=new_plan.plan_id,
        status=PlanStatus(new_plan.status),
        created_at=new_plan.created_at,
        prompt=new_plan.prompt,
        progress_percentage=new_plan.progress_percentage,
        progress_message=new_plan.progress_message,
        error_message=new_plan.error_message,
        output_dir=new_plan.output_dir
    )


@app.get("/api/plans/{plan_id}/stream-status")
async def get_stream_status(plan_id: str):
    """Check if the progress stream for a given plan is available."""
    if plan_id in progress_streams and progress_streams[plan_id] is not None:
        return {"status": "ready"}
    else:
        return {"status": "pending"}


@app.get("/api/plans/{plan_id}/details")
async def get_plan_details(plan_id: str, db: Session = Depends(get_database)):
    """Get detailed pipeline execution information"""
    db_service = DatabaseService(db)
    plan = db_service.get_plan(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    run_id_dir = Path(plan.output_dir)

    # Read Luigi activity log if it exists
    activity_log_path = run_id_dir / "track_activity.jsonl"
    pipeline_stages = []

    if activity_log_path.exists():
        try:
            with open(activity_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        stage_data = json.loads(line.strip())
                        pipeline_stages.append(stage_data)
        except Exception as e:
            print(f"Error reading activity log: {e}")

    # Read log file if it exists
    log_file_path = run_id_dir / "log.txt"
    pipeline_log = ""

    if log_file_path.exists():
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                pipeline_log = f.read()
        except Exception as e:
            print(f"Error reading log file: {e}")

    # List generated files
    generated_files = []
    if run_id_dir.exists():
        for file_path in run_id_dir.iterdir():
            if file_path.is_file():
                generated_files.append({
                    "filename": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                    "modified_at": file_path.stat().st_mtime
                })

    return {
        "plan_id": plan_id,
        "run_directory": str(run_id_dir),
        "pipeline_stages": pipeline_stages,
        "pipeline_log": pipeline_log[-5000:] if pipeline_log else "",  # Last 5KB
        "generated_files": generated_files,
        "total_files": len(generated_files)
    }


@app.get("/api/plans/{plan_id}/stream")
async def stream_plan_progress(plan_id: str):
    """Server-sent events stream for real-time plan progress"""

    async def event_generator():
        # This function is now responsible for handling the initial connection and the stream lifecycle.
        # This ensures that the EventSourceResponse is always created, allowing CORS headers to be sent.

        # Wait for the queue to become available, but do it inside the generator.
        for _ in range(10):  # Try for up to 5 seconds
            if plan_id in progress_streams:
                break
            await asyncio.sleep(0.5)
        
        if plan_id not in progress_streams:
            yield {"event": "error", "data": json.dumps({"message": "Stream could not be established."})}
            return

        queue = progress_streams[plan_id]
        try:
            while True:
                # Wait for a new message from the background job
                update = await queue.get()

                if update is None:  # End of stream signal
                    yield {"event": "end", "data": "Stream ended"}
                    break

                # Send the detailed task update to the client
                yield {"event": "task_update", "data": json.dumps(update)}

                queue.task_done()
        except asyncio.CancelledError:
            print(f"Stream for plan {plan_id} was cancelled by client.")
        finally:
            # Clean up the queue when the client disconnects or stream ends
            if plan_id in progress_streams:
                # Ensure the queue is empty before deleting
                while not progress_streams[plan_id].empty():
                    progress_streams[plan_id].get_nowait()
                    progress_streams[plan_id].task_done()
                del progress_streams[plan_id]
            print(f"Cleaned up progress stream for plan {plan_id}")

    return EventSourceResponse(event_generator())


@app.get("/api/plans/{plan_id}/files", response_model=PlanFilesResponse)
async def get_plan_files(plan_id: str, db: Session = Depends(get_database)):
    """Get list of files generated for a plan"""
    try:
        db_service = DatabaseService(db)
        plan = db_service.get_plan(plan_id)

        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Get files from database
        try:
            plan_files = db_service.get_plan_files(plan_id)
            files = [pf.filename for pf in plan_files]
        except Exception as e:
            print(f"Warning: Database query failed for plan {plan_id}: {e}")
            files = []

        # Fallback: scan filesystem if database is empty
        if not files and plan.output_dir:
            try:
                output_dir = Path(plan.output_dir)
                if output_dir.exists():
                    # Get all files except log and tracking files
                    filesystem_files = []
                    for file_path in output_dir.iterdir():
                        if file_path.is_file() and file_path.name not in ['log.txt', 'track_activity.jsonl']:
                            filesystem_files.append(file_path.name)
                    files = filesystem_files
            except Exception as e:
                print(f"Warning: Could not scan filesystem for plan {plan_id}: {e}")

        has_report = FilenameEnum.REPORT.value in files

        return PlanFilesResponse(
            plan_id=plan_id,
            files=sorted(files),
            has_report=has_report
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_plan_files for {plan_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
    report_file = output_dir / FilenameEnum.REPORT.value

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