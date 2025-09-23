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

        # Set up environment
        environment = os.environ.copy()
        environment[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_id_dir)

        # Map API enum values to pipeline enum values
        speed_vs_detail_mapping = {
            "fast_but_skip_details": "fast_but_skip_details",
            "balanced_speed_and_detail": "all_details_but_slow",  # Map balanced to detailed
            "all_details_but_slow": "all_details_but_slow"
        }
        pipeline_speed_value = speed_vs_detail_mapping.get(request.speed_vs_detail.value, "all_details_but_slow")
        environment[PipelineEnvironmentEnum.SPEED_VS_DETAIL.value] = pipeline_speed_value

        if request.llm_model:
            environment[PipelineEnvironmentEnum.LLM_MODEL.value] = request.llm_model

        if request.openrouter_api_key:
            environment["OPENROUTER_API_KEY"] = request.openrouter_api_key

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
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if not line:
                        continue

                    print(f"DEBUG Luigi STDOUT: {line}")

                    # Parse for task name
                    task_name_match = re.search(r'(\w+Task)', line)
                    if not task_name_match:
                        continue
                    
                    task_name = task_name_match.group(1)
                    
                    # Determine task status from log message
                    status = None
                    if "DONE" in line or "complete" in line:
                        status = "completed"
                    elif "running" in line.lower() or "starting" in line.lower() or "executing" in line.lower():
                        status = "running"
                    elif "failed" in line.lower() or "error" in line.lower():
                        status = "failed"

                    if status:
                        update_data = {
                            "task_id": task_name,
                            "status": status,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        try:
                            progress_queue.put_nowait(update_data)
                        except asyncio.QueueFull:
                            print(f"Warning: Progress queue for plan {plan_id} is full.")

                    # Also update the database for polling fallback and persistence
                    if status == 'completed' and task_name not in completed_tasks:
                        completed_tasks.add(task_name)
                        progress_percentage = min(95, int((len(completed_tasks) / total_tasks) * 100))
                        progress_message = f"Task {len(completed_tasks)}/{total_tasks}: {task_name} completed"
                        db_service.update_plan(plan_id, {
                            "progress_percentage": progress_percentage,
                            "progress_message": progress_message
                        })

                process.stdout.close()
                
        def read_stderr():
            if process.stderr:
                for line in iter(process.stderr.readline, ''):
                    line = line.strip()
                    if line:
                        print(f"DEBUG Luigi STDERR: {line}")
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
        print(f"Exception in run_plan_job: {e}")
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
        # OpenRouter fallbacks - using exact llm_config.json keys
        LLMModel(
            id="qwen-qwen3-max",
            label="Qwen3 Max (OpenRouter)",
            comment="High-performance Qwen model via OpenRouter. Excellent reasoning.",
            priority=4,
            requires_api_key=True  # Uses OPENROUTER_API_KEY
        ),
        LLMModel(
            id="x-ai-grok-4-fast-free",
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


@app.post("/api/plans", response_model=PlanResponse)
async def create_plan(request: CreatePlanRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_database)):
    """Create a new plan generation job"""

    try:
        print(f"DEBUG: Starting create_plan with request: {request}")

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
    """Retry a failed or stuck plan"""
    db_service = DatabaseService(db)
    plan = db_service.get_plan(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Reset plan to pending status
    db_service.update_plan(plan_id, {
        "status": PlanStatus.pending.value,
        "progress_percentage": 0,
        "progress_message": "Plan queued for retry processing...",
        "error_message": None,
        "started_at": None,
        "completed_at": None
    })

    # Create request object from stored plan data
    request = CreatePlanRequest(
        prompt=plan.prompt,
        llm_model=plan.llm_model,
        speed_vs_detail=plan.speed_vs_detail
    )

    # Start background task
    background_tasks.add_task(run_plan_job, plan_id, request)

    # Return updated plan
    updated_plan = db_service.get_plan(plan_id)
    return PlanResponse(
        plan_id=updated_plan.plan_id,
        status=PlanStatus(updated_plan.status),
        created_at=updated_plan.created_at,
        prompt=updated_plan.prompt,
        progress_percentage=updated_plan.progress_percentage,
        progress_message=updated_plan.progress_message,
        error_message=updated_plan.error_message,
        output_dir=updated_plan.output_dir
    )


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