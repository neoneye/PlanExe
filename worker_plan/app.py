import logging
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from worker_plan_api.filenames import FilenameEnum
from worker_plan_api.generate_run_id import generate_run_id
from worker_plan_api.llm_info import LLMInfo
from planexe.plan.pipeline_environment import PipelineEnvironmentEnum
from planexe.plan.plan_file import PlanFile
from planexe.plan.start_time import StartTime
from planexe.llm_factory import obtain_llm_info

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

MODULE_PATH_PIPELINE = "planexe.plan.run_plan_pipeline"
RUN_BASE_PATH = Path(os.environ.get("PLANEXE_RUN_DIR", "run")).resolve()
RELAY_PROCESS_OUTPUT = os.environ.get("WORKER_RELAY_PROCESS_OUTPUT", "false").lower() == "true"
APP_ROOT = Path(os.environ.get("PLANEXE_CONFIG_PATH", Path(".").resolve())).resolve()

RUN_BASE_PATH.mkdir(parents=True, exist_ok=True)


class StartRunRequest(BaseModel):
    submit_or_retry: Literal["submit", "retry"] = Field(description="Whether this is a new run or a retry of an existing run.")
    plan_prompt: str = Field(..., description="The user provided plan description.")
    llm_model: str = Field(..., description="LLM model identifier.")
    speed_vs_detail: str = Field(..., description="Speed vs detail preference.")
    openrouter_api_key: Optional[str] = Field(None, description="Optional OpenRouter API key.")
    use_uuid_as_run_id: bool = Field(False, description="Force UUID based run IDs.")
    run_id: Optional[str] = Field(None, description="Existing run ID to retry.")


class StartRunResponse(BaseModel):
    run_id: str
    run_dir: str
    pid: int
    status: str


class StopRunResponse(BaseModel):
    run_id: str
    stopped: bool
    message: str
    returncode: Optional[int]


class RunStatusResponse(BaseModel):
    run_id: str
    run_dir: str
    pid: Optional[int]
    running: bool
    returncode: Optional[int]
    pipeline_complete: bool
    stop_requested: bool


@dataclass
class RunProcessInfo:
    run_id: str
    run_dir: Path
    process: subprocess.Popen
    submit_or_retry: str
    started_at: float = field(default_factory=time.time)
    stop_requested: bool = False

    def is_running(self) -> bool:
        return self.process.poll() is None

    def returncode(self) -> Optional[int]:
        if self.is_running():
            return None
        return self.process.returncode


process_store: Dict[str, RunProcessInfo] = {}
process_lock = threading.Lock()
app = FastAPI(title="PlanExe Worker", version="0.1.0")


def has_pipeline_complete_file(path_dir: Path) -> bool:
    if not path_dir.exists():
        return False
    try:
        return FilenameEnum.PIPELINE_COMPLETE.value in os.listdir(path_dir)
    except FileNotFoundError:
        return False


def build_env(run_dir: Path, llm_model: str, speed_vs_detail: str, openrouter_api_key: Optional[str]) -> Dict[str, str]:
    env = os.environ.copy()
    env[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_dir)
    env[PipelineEnvironmentEnum.LLM_MODEL.value] = llm_model
    env[PipelineEnvironmentEnum.SPEED_VS_DETAIL.value] = speed_vs_detail
    if openrouter_api_key:
        env["OPENROUTER_API_KEY"] = openrouter_api_key
    return env


def start_pipeline_subprocess(env: Dict[str, str]) -> subprocess.Popen:
    command = [sys.executable, "-m", MODULE_PATH_PIPELINE]
    logger.info("Starting pipeline: %s", " ".join(command))
    stdout_target = None if RELAY_PROCESS_OUTPUT else subprocess.DEVNULL
    stderr_target = None if RELAY_PROCESS_OUTPUT else subprocess.DEVNULL
    return subprocess.Popen(command, cwd=str(APP_ROOT), env=env, stdout=stdout_target, stderr=stderr_target)


def create_run_directory(request: StartRunRequest) -> tuple[str, Path]:
    if request.submit_or_retry == "retry":
        if not request.run_id:
            raise HTTPException(status_code=400, detail="run_id is required when retrying a run.")
        run_dir = RUN_BASE_PATH / request.run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run directory does not exist: {run_dir}")
        return request.run_id, run_dir.resolve()

    start_time = datetime.now().astimezone()
    run_id = generate_run_id(use_uuid=request.use_uuid_as_run_id, start_time=start_time)
    run_dir = RUN_BASE_PATH / run_id
    if run_dir.exists():
        raise HTTPException(status_code=409, detail=f"Run directory already exists: {run_dir}")

    run_dir.mkdir(parents=True, exist_ok=False)
    start_time_file = StartTime.create(start_time)
    start_time_file.save(run_dir / FilenameEnum.START_TIME.value)

    plan_file = PlanFile.create(vague_plan_description=request.plan_prompt, start_time=start_time)
    plan_file.save(run_dir / FilenameEnum.INITIAL_PLAN.value)

    return run_id, run_dir.resolve()


@app.post("/runs", response_model=StartRunResponse)
def start_run(request: StartRunRequest) -> StartRunResponse:
    run_id, run_dir = create_run_directory(request)

    with process_lock:
        existing = process_store.get(run_id)
        if existing and existing.is_running():
            raise HTTPException(status_code=409, detail=f"Run {run_id} is already active.")

    env = build_env(run_dir=run_dir, llm_model=request.llm_model, speed_vs_detail=request.speed_vs_detail, openrouter_api_key=request.openrouter_api_key)
    process = start_pipeline_subprocess(env)

    info = RunProcessInfo(
        run_id=run_id,
        run_dir=run_dir,
        process=process,
        submit_or_retry=request.submit_or_retry,
    )

    with process_lock:
        process_store[run_id] = info

    return StartRunResponse(run_id=run_id, run_dir=str(run_dir), pid=process.pid, status="running")


@app.post("/runs/{run_id}/stop", response_model=StopRunResponse)
def stop_run(run_id: str) -> StopRunResponse:
    with process_lock:
        info = process_store.get(run_id)

    if not info:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    running_before = info.is_running()
    if running_before:
        info.stop_requested = True
        try:
            info.process.terminate()
        except Exception as exc:
            logger.warning("Error terminating run %s: %s", run_id, exc)

    return StopRunResponse(
        run_id=run_id,
        stopped=running_before,
        message="Stop signal sent." if running_before else "Process already finished.",
        returncode=info.returncode(),
    )


@app.get("/runs/{run_id}", response_model=RunStatusResponse)
def run_status(run_id: str) -> RunStatusResponse:
    run_dir = (RUN_BASE_PATH / run_id).resolve()
    pipeline_complete = has_pipeline_complete_file(run_dir)

    with process_lock:
        info = process_store.get(run_id)

    running = False
    pid: Optional[int] = None
    returncode: Optional[int] = None
    stop_requested = False

    if info:
        pid = info.process.pid
        stop_requested = info.stop_requested
        running = info.is_running()
        returncode = info.returncode()

    return RunStatusResponse(
        run_id=run_id,
        run_dir=str(run_dir),
        pid=pid,
        running=running,
        returncode=returncode,
        pipeline_complete=pipeline_complete,
        stop_requested=stop_requested,
    )


@app.get("/llm-info", response_model=LLMInfo)
def llm_info() -> LLMInfo:
    return obtain_llm_info()


@app.get("/healthz")
def healthcheck() -> dict:
    return {"status": "ok", "run_base_path": str(RUN_BASE_PATH)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("worker_plan.app:app", host="0.0.0.0", port=8000, reload=False)
