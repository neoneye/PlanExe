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
from html import escape
from pathlib import Path
from typing import Dict, Optional, List

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
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
from planexe.utils.planexe_llmconfig import PlanExeLLMConfig

from planexe_api.models import (
    CreatePlanRequest, PlanResponse, PlanProgressEvent, LLMModel,
    PromptExample, PlanFilesResponse, PlanArtefactListResponse, PlanArtefact, APIError, HealthResponse,
    PlanStatus, SpeedVsDetail, PipelineDetailsResponse, StreamStatusResponse,
    FallbackReportResponse, ReportSection, MissingSection,
    AnalysisStreamRequest, AnalysisStreamSessionResponse,
)
from planexe_api.database import (
    get_database, get_database_service, create_tables, DatabaseService, Plan, LLMInteraction,
    PlanFile, PlanMetrics, PlanContent, SessionLocal
)
from planexe_api.services.pipeline_execution_service import PipelineExecutionService
from planexe_api.websocket_manager import websocket_manager
from planexe_api.streaming import AnalysisStreamSessionStore, AnalysisStreamService

# Initialize FastAPI app
app = FastAPI(
    title="PlanExe API",
    description="REST API for PlanExe - Transform ideas into detailed plans using AI",
    version="1.0.0",
)

# Environment detection
IS_DEVELOPMENT = os.environ.get("PLANEXE_CLOUD_MODE", "false").lower() != "true"

STREAMING_FLAG_VALUE = (
    os.environ.get("STREAMING_ENABLED")
    or os.environ.get("PLANEXE_STREAMING_ENABLED")
    or os.environ.get("NEXT_PUBLIC_STREAMING_ENABLED")
    or ("true" if IS_DEVELOPMENT else "false")
)
STREAMING_ENABLED = STREAMING_FLAG_VALUE.lower() == "true"

# CORS configuration - only enable for local development
if IS_DEVELOPMENT:
    print("Development mode: CORS enabled for localhost:3000 and localhost:3001")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    print("Production mode: CORS disabled, serving static UI")


STATIC_UI_DIR: Optional[Path] = Path("/app/ui_static") if not IS_DEVELOPMENT else None

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
llm_config = PlanExeLLMConfig.load()
pipeline_service = PipelineExecutionService(planexe_project_root)

analysis_session_store = AnalysisStreamSessionStore(ttl_seconds=45)
analysis_stream_service = AnalysisStreamService(session_store=analysis_session_store)

if STREAMING_ENABLED:
    print("Streaming analysis enabled - Responses SSE harness ready")
else:
    print("Streaming analysis disabled - set STREAMING_ENABLED=true to enable")

# Database initialization
create_tables()


# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    await websocket_manager.start_heartbeat_task()
    print("FastAPI application started - WebSocket manager initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up services on application shutdown"""
    await websocket_manager.shutdown()
    print("FastAPI application shutdown - WebSocket manager cleaned up")


def execute_plan_async(plan_id: str, request: CreatePlanRequest) -> None:
    """Execute Luigi pipeline asynchronously using the dedicated service with WebSocket support"""
    import asyncio

    async def run_pipeline():
        db = SessionLocal()
        try:
            db_service = DatabaseService(db)
            await pipeline_service.execute_plan(plan_id, request, db_service)
        except Exception as e:
            print(f"Exception in plan execution: {e}")
        finally:
            try:
                db.close()
            except Exception:
                pass

    # Create new event loop for the thread
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_pipeline())
    except Exception as e:
        print(f"Failed to execute pipeline for plan {plan_id}: {e}")
    finally:
        try:
            loop.close()
        except Exception:
            pass


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
    return {
        "ping": "pong",
        "timestamp": "2025-09-27T16:01:00Z",
        "railway_deployment_test": "latest_code_deployed",
        "api_routes_working": True
    }


@app.post("/api/stream/analyze", response_model=AnalysisStreamSessionResponse)
async def create_analysis_stream_endpoint(
    request: AnalysisStreamRequest,
):
    """Cache streaming payloads before upgrading to SSE."""

    if not STREAMING_ENABLED:
        raise HTTPException(status_code=403, detail="STREAMING_DISABLED")

    cached = await analysis_stream_service.create_session(request)
    ttl_seconds = int(max(0, round((cached.expires_at - cached.created_at).total_seconds())))
    return AnalysisStreamSessionResponse(
        session_id=cached.session_id,
        task_id=cached.task_id,
        model_key=cached.model_key,
        expires_at=cached.expires_at,
        ttl_seconds=ttl_seconds,
    )


@app.get("/api/stream/analyze/{task_id}/{model_key}/{session_id}")
async def stream_analysis_endpoint(task_id: str, model_key: str, session_id: str):
    """Upgrade cached analysis payload into an SSE stream."""

    if not STREAMING_ENABLED:
        raise HTTPException(status_code=403, detail="STREAMING_DISABLED")

    async def event_generator():
        async for event in analysis_stream_service.stream(
            task_id=task_id,
            model_key=model_key,
            session_id=session_id,
        ):
            yield event

    return EventSourceResponse(event_generator(), ping=10000)


# LLM models endpoint
@app.get("/api/models", response_model=List[LLMModel])
async def get_models():
    """Get available LLM models"""
    try:
        models = []
        for config_item in llm_info.llm_config_items:
            # Get original config data to access comment, priority, etc.
            original_config = llm_config.llm_config_dict.get(config_item.id, {})

            model = LLMModel(
                id=config_item.id,
                label=config_item.label,
                comment=original_config.get("comment", ""),
                priority=original_config.get("priority", 999),
                requires_api_key=True  # All models require API keys in this system
            )
            models.append(model)
        return models
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}")


# Railway debugging endpoint for models
@app.get("/api/models/debug")
async def debug_models():
    """Debug endpoint to check LLM configuration on Railway"""
    debug_info = {
        "railway_environment": os.getenv("PLANEXE_CLOUD_MODE", "false") == "true",
        "llm_config_available": False,
        "llm_info_available": False,
        "config_items_count": 0,
        "config_dict_keys": [],
        "error_details": None
    }
    
    try:
        # Check if llm_config is available
        if llm_config:
            debug_info["llm_config_available"] = True
            debug_info["config_dict_keys"] = list(llm_config.llm_config_dict.keys())
        
        # Check if llm_info is available  
        if llm_info:
            debug_info["llm_info_available"] = True
            debug_info["config_items_count"] = len(llm_info.llm_config_items)
            
    except Exception as e:
        debug_info["error_details"] = str(e)
    
    return debug_info


# Prompt examples endpoint
@app.get("/api/prompts", response_model=List[PromptExample])
async def get_prompts():
    """Get example prompts"""
    try:
        examples = []
        for i, prompt in enumerate(prompt_catalog._catalog.values()):
            example = PromptExample(
                uuid=prompt.id,  # Use the prompt's existing ID as UUID
                prompt=prompt.prompt,
                title=prompt.extras.get('title', prompt.id)  # Use title from extras or ID as fallback
            )
            examples.append(example)
        return examples
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prompts: {str(e)}")


# Plan creation endpoint
@app.post("/api/plans", response_model=PlanResponse)
async def create_plan(request: CreatePlanRequest):
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

        db = get_database_service()
        try:
            plan = db.create_plan(plan_data)
        finally:
            db.close()
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


# Database artefact endpoint
@app.get("/api/plans/{plan_id}/artefacts", response_model=PlanArtefactListResponse)
async def list_plan_artefacts(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Return artefacts persisted in plan_content for the given plan."""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        content_records = db.get_plan_content(plan_id)
        artefacts: List[PlanArtefact] = []

        for record in content_records:
            size_bytes = record.content_size_bytes
            if size_bytes is None:
                size_bytes = len(record.content.encode('utf-8')) if record.content else 0

            description = record.filename
            if '-' in description:
                description = description.split('-', 1)[1]
            if '.' in description:
                description = description.rsplit('.', 1)[0]
            description = description.replace('_', ' ').replace('-', ' ').strip().title() or record.filename

            try:
                order = int(record.filename.split('-', 1)[0])
            except (ValueError, IndexError):
                order = None

            artefacts.append(
                PlanArtefact(
                    filename=record.filename,
                    content_type=record.content_type,
                    stage=record.stage,
                    size_bytes=size_bytes,
                    created_at=record.created_at or datetime.utcnow(),
                    description=description,
                    task_name=record.stage or description,
                    order=order,
                )
            )

        artefacts.sort(key=lambda entry: ((entry.order if entry.order is not None else 9999), entry.filename))

        return PlanArtefactListResponse(
            plan_id=plan_id,
            artefacts=artefacts
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch plan artefacts: {exc}")



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


# DEPRECATED SSE endpoint - replaced with WebSocket for thread-safety
@app.get("/api/plans/{plan_id}/stream")
async def stream_plan_progress_deprecated(plan_id: str, db: DatabaseService = Depends(get_database)):
    """
    DEPRECATED: SSE stream has been replaced with WebSocket for thread-safety
    Use WebSocket endpoint: ws://localhost:8080/ws/plans/{plan_id}/progress
    """
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=410,  # Gone
        content={
            "error": "SSE endpoint deprecated due to thread safety issues",
            "message": "Please migrate to WebSocket endpoint for real-time progress",
            "websocket_url": f"ws://localhost:8080/ws/plans/{plan_id}/progress",
            "migration_guide": {
                "old": f"GET /api/plans/{plan_id}/stream",
                "new": f"WebSocket ws://localhost:8080/ws/plans/{plan_id}/progress",
                "reason": "Thread-safe WebSocket architecture replaces broken SSE global dictionaries"
            }
        }
    )


# WebSocket endpoint for real-time progress (replaces unreliable SSE)
@app.websocket("/ws/plans/{plan_id}/progress")
async def websocket_plan_progress(websocket: WebSocket, plan_id: str):
    """
    WebSocket endpoint for real-time Luigi pipeline progress updates.

    This replaces the unreliable SSE endpoint and fixes:
    - Global dictionary race conditions
    - Thread safety violations
    - Memory leaks from abandoned connections
    - Poor error handling
    - Connection reliability issues
    """
    await websocket.accept()

    client_id = None
    try:
        # Add connection to WebSocket manager
        client_id = await websocket_manager.add_connection(websocket, plan_id)

        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "plan_id": plan_id,
            "client_id": client_id,
            "message": "Connected to Luigi pipeline progress stream"
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (heartbeat responses, commands, etc.)
                data = await websocket.receive_json()

                # Handle heartbeat responses
                if data.get("type") == "heartbeat_response":
                    # Update heartbeat timestamp
                    pass

                # Handle other client messages (future expansion)
                elif data.get("type") == "command":
                    # Could be used for pause/resume pipeline, etc.
                    pass

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket error for plan {plan_id}, client {client_id}: {e}")
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket connection error for plan {plan_id}: {e}")
    finally:
        # Clean up connection
        if client_id:
            await websocket_manager.remove_connection(client_id)
            print(f"WebSocket disconnected: plan_id={plan_id}, client_id={client_id}")


# Plan content endpoint (Option 3: retrieve from database)
@app.get("/api/plans/{plan_id}/content/{filename}")
async def get_plan_content_file(plan_id: str, filename: str, db: DatabaseService = Depends(get_database)):
    """Get specific plan file content from database (Option 3 fix)"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Try to get content from database first (persistent)
        content_record = db.get_plan_content_by_filename(plan_id, filename)
        if content_record:
            # Return content from database
            content_type_map = {
                'json': 'application/json',
                'markdown': 'text/markdown',
                'html': 'text/html',
                'csv': 'text/csv',
                'txt': 'text/plain',
                'unknown': 'application/octet-stream'
            }
            media_type = content_type_map.get(content_record.content_type, 'text/plain')
            
            return Response(
                content=content_record.content,
                media_type=media_type,
                headers={"Content-Disposition": f'inline; filename="{filename}"'}
            )
        
        # Fallback: try filesystem (ephemeral, may not exist after restart)
        file_path = Path(plan.output_dir) / filename
        if file_path.exists():
            return FileResponse(file_path)
        
        raise HTTPException(status_code=404, detail="File not found in database or filesystem")
        
    except Exception as e:
        print(f"Error retrieving plan content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Plan files endpoint
@app.get("/api/plans/{plan_id}/files", response_model=PlanFilesResponse)
async def get_plan_files(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Get list of files generated by a plan"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        artefact_response = await list_plan_artefacts(plan_id, db)
        report_filename = FilenameEnum.REPORT.value
        has_report = any(entry.filename == report_filename for entry in artefact_response.artefacts)
        if not has_report:
            report_path = Path(plan.output_dir) / report_filename
            has_report = report_path.exists()

        filenames = [entry.filename for entry in artefact_response.artefacts]

        return PlanFilesResponse(
            plan_id=plan_id,
            files=filenames,
            has_report=has_report
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plan files: {str(e)}")


# Database artefact endpoint
@app.get("/api/plans/{plan_id}/artefacts", response_model=PlanArtefactListResponse)
async def list_plan_artefacts(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Return artefacts persisted in plan_content for the given plan."""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        content_records = db.get_plan_content(plan_id)
        artefacts: List[PlanArtefact] = []

        for record in content_records:
            size_bytes = record.content_size_bytes
            if size_bytes is None:
                size_bytes = len(record.content.encode('utf-8')) if record.content else 0

            description = record.filename
            if '-' in description:
                description = description.split('-', 1)[1]
            if '.' in description:
                description = description.rsplit('.', 1)[0]
            description = description.replace('_', ' ').replace('-', ' ').strip().title() or record.filename

            try:
                order = int(record.filename.split('-', 1)[0])
            except (ValueError, IndexError):
                order = None

            artefacts.append(
                PlanArtefact(
                    filename=record.filename,
                    content_type=record.content_type,
                    stage=record.stage,
                    size_bytes=size_bytes,
                    created_at=record.created_at or datetime.utcnow(),
                    description=description,
                    task_name=record.stage or description,
                    order=order,
                )
            )

        artefacts.sort(key=lambda entry: ((entry.order if entry.order is not None else 9999), entry.filename))

        return PlanArtefactListResponse(
            plan_id=plan_id,
            artefacts=artefacts
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch plan artefacts: {exc}")



# Plan details endpoint
@app.get("/api/plans/{plan_id}/details", response_model=PipelineDetailsResponse)
async def get_plan_details(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Get detailed pipeline information for a plan"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Read pipeline stage files and logs
        plan_dir = Path(plan.output_dir)

        # Get pipeline stages (simplified - would need to read actual stage files)
        pipeline_stages = []
        if plan_dir.exists():
            stage_files = list(plan_dir.glob("*.json"))
            for stage_file in sorted(stage_files):
                try:
                    with open(stage_file, 'r') as f:
                        stage_data = json.loads(f.read())
                        pipeline_stages.append({
                            "stage": stage_file.stem,
                            "status": "completed" if stage_file.exists() else "pending",
                            "data": stage_data
                        })
                except:
                    pass

        # Read pipeline log
        log_file = plan_dir / "log.txt"
        pipeline_log = ""
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    pipeline_log = f.read()
            except:
                pass

        # Get generated files
        files = db.get_plan_files(plan_id)
        generated_files = [
            {
                "filename": f.filename,
                "file_type": getattr(f, 'file_type', 'unknown'),
                "size": getattr(f, 'file_size_bytes', 0),
                "created_at": getattr(f, 'created_at', None)
            }
            for f in files
        ]

        return PipelineDetailsResponse(
            plan_id=plan_id,
            run_directory=str(plan.output_dir),
            pipeline_stages=pipeline_stages,
            pipeline_log=pipeline_log,
            generated_files=generated_files,
            total_files=len(files)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plan details: {str(e)}")


# Stream status endpoint
@app.get("/api/plans/{plan_id}/stream-status", response_model=StreamStatusResponse)
async def get_stream_status(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Check if SSE stream is ready for a plan"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Check if SSE stream is ready based on plan status
        is_ready = plan.status in ['running', 'completed', 'failed']

        return StreamStatusResponse(
            status="ready" if is_ready else "not_ready",
            ready=is_ready
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stream status: {str(e)}")


# Helper utilities for fallback report assembly
EXPECTED_REPORT_FILENAMES = [
    member.value
    for member in FilenameEnum
    if "{}" not in member.value
]


def _infer_stage_from_filename(filename: str) -> Optional[str]:
    try:
        return FilenameEnum(filename).name.lower()
    except ValueError:
        return None


def _normalise_content_type(content_type: Optional[str]) -> str:
    return (content_type or "text/plain").lower()


def _render_section_html(section: ReportSection) -> str:
    content_type = _normalise_content_type(section.content_type)
    if content_type in ("html", "text/html"):
        body_html = section.content
    elif content_type in ("markdown", "md", "text/markdown"):
        body_html = f"<pre class='content-block markdown'>{escape(section.content)}</pre>"
    elif content_type in ("json", "application/json"):
        body_html = f"<pre class='content-block json'>{escape(section.content)}</pre>"
    elif content_type in ("csv", "text/csv"):
        body_html = f"<pre class='content-block csv'>{escape(section.content)}</pre>"
    else:
        body_html = f"<pre class='content-block plain'>{escape(section.content)}</pre>"

    title_text = escape(section.stage or section.filename)
    filename_text = escape(section.filename)

    return (
        "<section class='plan-section'>"
        f"<h2>{title_text}</h2>"
        f"<p class='filename'>{filename_text}</p>"
        f"{body_html}"
        "</section>"
    )


def _render_missing_sections_html(missing_sections: List[MissingSection]) -> str:
    if not missing_sections:
        return (
            "<section class='missing'>"
            "<h2>Further Research Required</h2>"
            "<p>All expected sections were recovered.</p>"
            "</section>"
        )

    items = []
    for missing in missing_sections:
        stage_text = missing.stage or "-"
        items.append(
            "<li>"
            f"<strong>{escape(stage_text)}</strong> "
            f"<span class='filename'>{escape(missing.filename)}</span> - "
            f"{escape(missing.reason)}"
            "</li>"
        )

    return (
        "<section class='missing'>"
        "<h2>Further Research Required</h2>"
        "<ul>" + "".join(items) + "</ul>"
        "</section>"
    )


def _build_fallback_html(
    plan_id: str,
    generated_at: datetime,
    completion_percentage: float,
    recovered_expected: int,
    total_expected: int,
    sections: List[ReportSection],
    missing_sections: List[MissingSection],
) -> str:
    header_html = (
        "<header class='report-header'>"
        f"<h1>Recovered Plan Report: {escape(plan_id)}</h1>"
        f"<p>Generated at {escape(generated_at.isoformat() + 'Z')}</p>"
        f"<p>Recovered {recovered_expected} of {total_expected} expected sections ("
        f"{completion_percentage:.2f}% complete).</p>"
        "</header>"
    )

    missing_html = _render_missing_sections_html(missing_sections)
    sections_html = "".join(_render_section_html(section) for section in sections)

    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='utf-8' />
<title>Recovered Plan Report - {escape(plan_id)}</title>
<style>
body {{ font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif; background: #f9fafb; color: #111827; margin: 2rem; }}
header.report-header {{ background: #111827; color: #f9fafb; padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; box-shadow: 0 10px 30px rgba(17, 24, 39, 0.25); }}
header.report-header h1 {{ margin: 0 0 0.5rem 0; font-size: 1.8rem; }}
header.report-header p {{ margin: 0.25rem 0; }}
section.missing {{ background: #fef3c7; border: 1px solid #f59e0b; padding: 1.25rem; border-radius: 10px; margin-bottom: 2rem; }}
section.missing ul {{ margin: 0.75rem 0 0 1.25rem; }}
section.missing li {{ margin-bottom: 0.5rem; }}
section.plan-section {{ background: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb; padding: 1.5rem; margin-bottom: 1.75rem; box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08); }}
section.plan-section h2 {{ margin-top: 0; margin-bottom: 0.75rem; font-size: 1.4rem; color: #0f172a; }}
section.plan-section .filename {{ color: #475569; font-size: 0.9rem; margin-bottom: 1rem; }}
pre.content-block {{ background: #f1f5f9; padding: 1rem; border-radius: 8px; overflow-x: auto; font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.9rem; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }}
pre.content-block.markdown {{ background: #eef2ff; }}
pre.content-block.json {{ background: #ecfeff; }}
pre.content-block.csv {{ background: #fef9c3; }}
</style>
</head>
<body>
{header_html}
{missing_html}
{sections_html}
</body>
</html>
"""


def _assemble_fallback_report(plan_id: str, plan_contents: List[PlanContent]) -> FallbackReportResponse:
    generated_at = datetime.utcnow()
    records_by_filename = {}
    for record in plan_contents:
        if record.filename not in records_by_filename:
            records_by_filename[record.filename] = record

    missing_sections: List[MissingSection] = []
    sections: List[ReportSection] = []
    recovered_expected = 0
    observed_filenames = set()

    for expected_filename in EXPECTED_REPORT_FILENAMES:
        record = records_by_filename.get(expected_filename)
        if record:
            sections.append(
                ReportSection(
                    filename=record.filename,
                    stage=record.stage,
                    content_type=record.content_type,
                    content=record.content,
                )
            )
            recovered_expected += 1
            observed_filenames.add(expected_filename)
        else:
            missing_sections.append(
                MissingSection(
                    filename=expected_filename,
                    stage=_infer_stage_from_filename(expected_filename),
                    reason="Missing from plan_content table",
                )
            )

    extra_records = [
        record
        for filename, record in records_by_filename.items()
        if filename not in observed_filenames
    ]
    extra_records.sort(key=lambda record: record.filename)

    for record in extra_records:
        sections.append(
            ReportSection(
                filename=record.filename,
                stage=record.stage,
                content_type=record.content_type,
                content=record.content,
            )
        )

    total_expected = len(EXPECTED_REPORT_FILENAMES)
    completion_percentage = round((recovered_expected / total_expected) * 100, 2) if total_expected else 0.0
    assembled_html = _build_fallback_html(
        plan_id,
        generated_at,
        completion_percentage,
        recovered_expected,
        total_expected,
        sections,
        missing_sections,
    )

    return FallbackReportResponse(
        plan_id=plan_id,
        generated_at=generated_at,
        completion_percentage=completion_percentage,
        sections=sections,
        missing_sections=missing_sections,
        assembled_html=assembled_html,
    )


@app.get("/api/plans/{plan_id}/fallback-report", response_model=FallbackReportResponse)
async def get_fallback_report(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Assemble a fallback report from plan_content records without rerunning Luigi."""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        plan_contents = db.get_plan_content(plan_id)
        if not plan_contents:
            raise HTTPException(status_code=404, detail="No plan content found for this plan")

        return _assemble_fallback_report(plan_id, plan_contents)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to assemble fallback report: {exc}")
# File download endpoints
@app.get("/api/plans/{plan_id}/report")
async def download_plan_report(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Download the final HTML report for a plan"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        report_path = Path(plan.output_dir) / FilenameEnum.REPORT.value

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
    """Delete a plan, terminate running processes, and clean up all associated resources"""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Terminate running pipeline process if exists
        try:
            terminated = pipeline_service.terminate_plan_execution(plan_id)
            if terminated:
                print(f"Terminated running pipeline for plan {plan_id}")
        except Exception as e:
            print(f"Warning: Failed to terminate pipeline for plan {plan_id}: {e}")

        # Clean up WebSocket connections for this plan
        try:
            await websocket_manager.cleanup_plan_connections(plan_id)
            print(f"Cleaned up WebSocket connections for plan {plan_id}")
        except Exception as e:
            print(f"Warning: Failed to cleanup WebSocket connections for plan {plan_id}: {e}")

        # Delete files from filesystem
        output_dir = Path(plan.output_dir)
        if output_dir.exists():
            import shutil
            shutil.rmtree(output_dir)

        # Delete from database
        db.delete_plan(plan_id)

        return {"message": f"Plan {plan_id} deleted successfully with full resource cleanup"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {str(e)}")


@app.get("/api/plans", response_model=List[PlanResponse])
async def list_plans(db: DatabaseService = Depends(get_database)):
    """Get list of all plans"""
    try:
        plans = db.list_plans()

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

# Mount static frontend after all API routes are registered (production only)
if not IS_DEVELOPMENT:
    if STATIC_UI_DIR and STATIC_UI_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_UI_DIR), html=True), name="static")
        print(f"Serving static UI from: {STATIC_UI_DIR}")
    else:
        missing_dir = STATIC_UI_DIR or Path("/app/ui_static")
        print(f"Warning: Static UI directory not found: {missing_dir}")
        print("   This is expected in local development mode or before frontend build")



# Plan artefact listing endpoint (database-backed)
@app.get("/api/plans/{plan_id}/artefacts", response_model=PlanArtefactListResponse)
async def list_plan_artefacts(plan_id: str, db: DatabaseService = Depends(get_database)):
    """Return artefacts persisted in plan_content for the given plan."""
    try:
        plan = db.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        content_records = db.get_plan_content(plan_id)
        artefacts: List[PlanArtefact] = []

        for record in content_records:
            size_bytes = record.content_size_bytes
            if size_bytes is None:
                size_bytes = len(record.content.encode('utf-8')) if record.content else 0

            description = record.filename
            if '-' in description:
                description = description.split('-', 1)[1]
            if '.' in description:
                description = description.rsplit('.', 1)[0]
            description = description.replace('_', ' ').replace('-', ' ').strip().title() or record.filename

            try:
                order = int(record.filename.split('-', 1)[0])
            except (ValueError, IndexError):
                order = None

            artefacts.append(
                PlanArtefact(
                    filename=record.filename,
                    content_type=record.content_type,
                    stage=record.stage,
                    size_bytes=size_bytes,
                    created_at=record.created_at or datetime.utcnow(),
                    description=description,
                    task_name=record.stage or description,
                    order=order,
                )
            )

        artefacts.sort(key=lambda entry: ((entry.order if entry.order is not None else 9999), entry.filename))

        return PlanArtefactListResponse(plan_id=plan_id, artefacts=artefacts)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch plan artefacts: {exc}")




if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)



