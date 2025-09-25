"""
Author: Claude Code using Sonnet 4
Date: 2025-09-24
PURPOSE: Dedicated service for Luigi pipeline execution - handles subprocess orchestration,
         progress streaming, environment setup, and file management separately from HTTP concerns
SRP and DRY check: Pass - Single responsibility of pipeline execution, extracted from bloated API layer
"""
import os
import queue
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from planexe_api.models import CreatePlanRequest, PlanStatus
from planexe_api.database import DatabaseService
from planexe.pipeline_environment import PipelineEnvironmentEnum, FilenameEnum

# Global process and queue management
running_processes: Dict[str, subprocess.Popen] = {}
progress_streams: Dict[str, queue.Queue] = {}

# Pipeline configuration
MODULE_PATH_PIPELINE = "planexe.run_plan_pipeline"


class PipelineExecutionService:
    """Service responsible for executing Luigi pipelines in background threads"""

    def __init__(self, planexe_project_root: Path):
        self.planexe_project_root = planexe_project_root

    def execute_plan(self, plan_id: str, request: CreatePlanRequest, db_service: DatabaseService) -> None:
        """
        Execute Luigi pipeline in background thread for the given plan

        Args:
            plan_id: Unique plan identifier
            request: Plan creation request with prompt and configuration
            db_service: Database service for persistence
        """
        # Create thread-safe queue for progress updates
        progress_queue = queue.Queue()
        progress_streams[plan_id] = progress_queue

        print(f"DEBUG: Starting pipeline execution for plan_id: {plan_id}")

        try:
            # Get plan from database
            plan = db_service.get_plan(plan_id)
            if not plan:
                print(f"DEBUG: Plan not found in database: {plan_id}")
                return

            run_id_dir = Path(plan.output_dir)

            # Set up execution environment
            environment = self._setup_environment(plan_id, request, run_id_dir)

            # Write pipeline input files
            self._write_pipeline_inputs(run_id_dir, request)

            # Update plan status to running
            db_service.update_plan(plan_id, {
                "status": PlanStatus.running.value,
                "progress_percentage": 0,
                "progress_message": "Starting plan generation pipeline...",
                "started_at": datetime.utcnow()
            })

            # Start Luigi subprocess
            process = self._start_luigi_subprocess(plan_id, environment, db_service)
            if not process:
                return

            # Monitor process execution
            self._monitor_process_execution(plan_id, process, run_id_dir, db_service, progress_queue)

        except Exception as e:
            print(f"DEBUG: Pipeline execution failed for {plan_id}: {e}")
            db_service.update_plan(plan_id, {
                "status": PlanStatus.failed.value,
                "error_message": f"Pipeline execution failed: {str(e)}"
            })
        finally:
            # Clean up resources
            self._cleanup_execution(plan_id)

    def _setup_environment(self, plan_id: str, request: CreatePlanRequest, run_id_dir: Path) -> Dict[str, str]:
        """Set up environment variables for Luigi pipeline execution"""
        print(f"DEBUG ENV: Starting environment setup for plan {plan_id}")

        # Check API keys in current environment
        api_keys_to_check = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
        print("DEBUG ENV: API keys in os.environ:")
        for key in api_keys_to_check:
            value = os.environ.get(key)
            if value:
                print(f"  {key}: {'*' * 10}...{value[-4:] if len(value) > 4 else '****'}")
            else:
                print(f"  {key}: NOT FOUND")

        # Copy environment and add pipeline-specific variables
        environment = os.environ.copy()
        environment[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_id_dir)

        # Map API enum values to pipeline enum values
        speed_vs_detail_mapping = {
            "fast_but_skip_details": "fast_but_skip_details",
            "balanced": "balanced",
            "detailed": "detailed"
        }

        environment[PipelineEnvironmentEnum.SPEED_VS_DETAIL.value] = speed_vs_detail_mapping.get(
            request.speed_vs_detail.value, "balanced"
        )
        environment[PipelineEnvironmentEnum.LLM_MODEL.value] = request.llm_model

        print(f"DEBUG ENV: Pipeline environment configured with {len(environment)} variables")
        return environment

    def _write_pipeline_inputs(self, run_id_dir: Path, request: CreatePlanRequest) -> None:
        """Write input files required by Luigi pipeline"""
        # Write start time
        start_time_file = run_id_dir / FilenameEnum.START_TIME.value
        with open(start_time_file, "w", encoding="utf-8") as f:
            f.write(datetime.utcnow().isoformat())

        # Write initial plan prompt
        initial_plan_file = run_id_dir / FilenameEnum.INITIAL_PLAN.value
        with open(initial_plan_file, "w", encoding="utf-8") as f:
            f.write(request.prompt)

    def _start_luigi_subprocess(self, plan_id: str, environment: Dict[str, str], db_service: DatabaseService) -> Optional[subprocess.Popen]:
        """Start Luigi pipeline subprocess"""
        import sys
        import platform

        python_executable = sys.executable
        command = [python_executable, "-m", MODULE_PATH_PIPELINE]

        print(f"DEBUG: Starting subprocess with command: {command}")
        print(f"DEBUG: Working directory: {self.planexe_project_root}")
        print(f"DEBUG: RUN_ID_DIR env var: {environment.get('RUN_ID_DIR')}")

        # Use shell=True on Windows for path compatibility
        use_shell = platform.system() == "Windows"

        try:
            process = subprocess.Popen(
                command,
                cwd=str(self.planexe_project_root),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                shell=use_shell
            )
            print(f"DEBUG: Subprocess started with PID: {process.pid}")

            # Test if subprocess actually started
            if process.poll() is not None:
                raise subprocess.SubprocessError(f"Subprocess failed to start, exit code: {process.returncode}")

            # Store process reference
            running_processes[plan_id] = process
            return process

        except Exception as e:
            print(f"DEBUG: Subprocess creation failed: {e}")
            db_service.update_plan(plan_id, {
                "status": PlanStatus.failed.value,
                "error_message": f"Failed to start subprocess: {str(e)}"
            })
            return None

    def _monitor_process_execution(self, plan_id: str, process: subprocess.Popen,
                                 run_id_dir: Path, db_service: DatabaseService,
                                 progress_queue: queue.Queue) -> None:
        """Monitor Luigi process execution and stream progress updates"""

        def read_stdout():
            """Stream Luigi pipeline logs to progress queue"""
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if not line:
                        continue

                    # Send log line to progress queue
                    log_data = {
                        "type": "log",
                        "message": line,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    try:
                        progress_queue.put_nowait(log_data)
                    except queue.Full:
                        print(f"Warning: Progress queue for plan {plan_id} is full.")

                    print(f"Luigi: {line}")

                # Signal stdout completion
                try:
                    completion_data = {
                        "type": "status",
                        "status": "stdout_closed",
                        "message": "Pipeline stdout stream closed"
                    }
                    progress_queue.put_nowait(completion_data)
                except queue.Full:
                    pass

                process.stdout.close()

        def read_stderr():
            """Stream Luigi pipeline errors to progress queue"""
            if process.stderr:
                for line in iter(process.stderr.readline, ''):
                    line = line.strip()
                    if not line:
                        continue

                    error_data = {
                        "type": "error",
                        "message": line,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    try:
                        progress_queue.put_nowait(error_data)
                    except queue.Full:
                        pass

                    print(f"Luigi ERROR: {line}")

                process.stderr.close()

        # Start monitoring threads
        stdout_thread = threading.Thread(target=read_stdout, name=f"stdout-{plan_id}")
        stderr_thread = threading.Thread(target=read_stderr, name=f"stderr-{plan_id}")
        stdout_thread.start()
        stderr_thread.start()

        # Wait for process completion
        return_code = process.wait()
        print(f"DEBUG: Luigi process completed with return code: {return_code}")

        # Wait for monitoring threads to complete
        stdout_thread.join(timeout=5.0)
        stderr_thread.join(timeout=5.0)

        # Update final plan status based on results
        self._finalize_plan_status(plan_id, return_code, run_id_dir, db_service, progress_queue)

    def _finalize_plan_status(self, plan_id: str, return_code: int, run_id_dir: Path,
                            db_service: DatabaseService, progress_queue: queue.Queue) -> None:
        """Update final plan status and index generated files"""

        if return_code == 0:
            # Check for expected final output file
            final_output_file = run_id_dir / "999-final-report.html"

            if final_output_file.exists():
                # Success - send completion message
                try:
                    success_data = {
                        "type": "status",
                        "status": "completed",
                        "message": "✅ Pipeline completed successfully! All files generated."
                    }
                    progress_queue.put_nowait(success_data)
                except queue.Full:
                    pass

                # Index all generated files
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
                # Pipeline completed but no final output
                try:
                    failure_data = {
                        "type": "status",
                        "status": "failed",
                        "message": "❌ Pipeline completed but final output file not found"
                    }
                    progress_queue.put_nowait(failure_data)
                except queue.Full:
                    pass

                db_service.update_plan(plan_id, {
                    "status": PlanStatus.failed.value,
                    "error_message": "Pipeline did not complete successfully"
                })
        else:
            # Process failed
            try:
                failure_data = {
                    "type": "status",
                    "status": "failed",
                    "message": f"❌ Pipeline failed with exit code {return_code}"
                }
                progress_queue.put_nowait(failure_data)
            except queue.Full:
                pass

            db_service.update_plan(plan_id, {
                "status": PlanStatus.failed.value,
                "error_message": f"Pipeline process failed with exit code {return_code}"
            })

        # Signal end of stream
        try:
            progress_queue.put_nowait(None)  # End signal
        except queue.Full:
            pass

    def _cleanup_execution(self, plan_id: str) -> None:
        """Clean up execution resources"""
        # Remove process reference
        if plan_id in running_processes:
            del running_processes[plan_id]

        print(f"DEBUG: Cleaned up execution resources for {plan_id}")

    def get_progress_stream(self, plan_id: str) -> Optional[queue.Queue]:
        """Get progress stream queue for a plan"""
        return progress_streams.get(plan_id)

    def cleanup_progress_stream(self, plan_id: str) -> None:
        """Clean up progress stream for a plan"""
        if plan_id in progress_streams:
            # Empty the queue
            while not progress_streams[plan_id].empty():
                try:
                    progress_streams[plan_id].get_nowait()
                except queue.Empty:
                    break
            del progress_streams[plan_id]
            print(f"Cleaned up progress stream for plan {plan_id}")