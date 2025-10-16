"""
/**
 * Author: ChatGPT gpt-5-codex
 * Date: 2025-10-19
 * PURPOSE: Extend Luigi pipeline execution service with Responses delta forwarding so
 *          WebSocket clients render reasoning telemetry without extra subprocess hooks.
 * SRP and DRY check: Pass - maintains single execution service while layering stream-aware
 *          parsing on top of existing WebSocket broadcast loop.
 * Previous Authors:
 *   - Codex using GPT-4o (CLI) on 2025-10-02T00:00:00Z (OS-aware subprocess fixes)
 *   - Claude Code using Sonnet 4 on 2025-09-27 (Thread-safe WebSocket integration)
 */
"""
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import platform

from planexe_api.models import CreatePlanRequest, PlanStatus
from planexe_api.database import DatabaseService
from planexe_api.websocket_manager import websocket_manager
from planexe.plan.pipeline_environment import PipelineEnvironmentEnum
from planexe.plan.filenames import FilenameEnum

# Thread-safe process management (replaces global dictionary)
class ProcessRegistry:
    """Thread-safe registry for running subprocess references"""

    def __init__(self):
        self._processes: Dict[str, subprocess.Popen] = {}
        self._lock = threading.RLock()

    def register(self, plan_id: str, process: subprocess.Popen) -> None:
        with self._lock:
            self._processes[plan_id] = process

    def unregister(self, plan_id: str) -> Optional[subprocess.Popen]:
        with self._lock:
            return self._processes.pop(plan_id, None)

    def get(self, plan_id: str) -> Optional[subprocess.Popen]:
        with self._lock:
            return self._processes.get(plan_id)

# Thread-safe process registry (replaces global dictionary)
process_registry = ProcessRegistry()

# Pipeline configuration
MODULE_PATH_PIPELINE = "planexe.plan.run_plan_pipeline"


class PipelineExecutionService:
    """Service responsible for executing Luigi pipelines in background threads"""

    def __init__(self, planexe_project_root: Path):
        self.planexe_project_root = planexe_project_root

    async def execute_plan(self, plan_id: str, request: CreatePlanRequest, db_service: DatabaseService) -> None:
        """
        Execute Luigi pipeline in background thread with WebSocket progress streaming

        Args:
            plan_id: Unique plan identifier
            request: Plan creation request with prompt and configuration
            db_service: Database service for persistence
        """
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

            # Update plan status to running and broadcast
            db_service.update_plan(plan_id, {
                "status": PlanStatus.running.value,
                "progress_percentage": 0,
                "progress_message": "Starting plan generation pipeline...",
                "started_at": datetime.utcnow()
            })

            # Broadcast initial status via WebSocket
            await websocket_manager.broadcast_to_plan(plan_id, {
                "type": "status",
                "status": "running",
                "message": "Starting plan generation pipeline...",
                "progress_percentage": 0,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Start Luigi subprocess
            process = self._start_luigi_subprocess(plan_id, environment, db_service)
            if not process:
                return

            # Monitor process execution with WebSocket streaming
            await self._monitor_process_execution(plan_id, process, run_id_dir, db_service)

        except Exception as e:
            print(f"DEBUG: Pipeline execution failed for {plan_id}: {e}")
            db_service.update_plan(plan_id, {
                "status": PlanStatus.failed.value,
                "error_message": f"Pipeline execution failed: {str(e)}"
            })
            # Broadcast error via WebSocket
            await websocket_manager.broadcast_to_plan(plan_id, {
                "type": "status",
                "status": "failed",
                "message": f"Pipeline execution failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            })
        finally:
            # Clean up resources
            await self._cleanup_execution(plan_id)

    def _setup_environment(self, plan_id: str, request: CreatePlanRequest, run_id_dir: Path) -> Dict[str, str]:
        """Set up environment variables for Luigi pipeline execution"""
        print(f"DEBUG ENV: Starting environment setup for plan {plan_id}")

        # CRITICAL: Validate required API keys BEFORE subprocess creation
        # Allow single provider usage - at least one of OpenAI or OpenRouter must be available
        required_keys = {
            "OPENAI_API_KEY": "OpenAI API calls",
            "OPENROUTER_API_KEY": "OpenRouter API calls"
        }

        available_keys = []
        missing_keys = []
        for key, purpose in required_keys.items():
            value = os.environ.get(key)
            if not value:
                missing_keys.append(f"{key} (needed for {purpose})")
                print(f"  ❌ {key}: NOT FOUND in os.environ")
            else:
                available_keys.append(key)
                print(f"  ✅ {key}: Available (length: {len(value)})")

        if not available_keys:
            error_msg = f"No API keys available. At least one provider (OpenAI or OpenRouter) is required."
            print(f"ERROR ENV: {error_msg}")
            raise ValueError(error_msg)

        print(f"INFO ENV: {len(available_keys)} API provider(s) available: {', '.join(available_keys)}")

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

        # Ensure Python runs UTF-8 to prevent Unicode console crashes on Windows
        environment['PYTHONIOENCODING'] = environment.get('PYTHONIOENCODING', 'utf-8')
        environment['PYTHONUTF8'] = environment.get('PYTHONUTF8', '1')
        # Enable verbose OpenAI client logging unless explicitly disabled
        environment['OPENAI_LOG'] = environment.get('OPENAI_LOG', 'debug')

        # CRITICAL: Configure HOME/cache paths appropriately per OS
        system_name = platform.system()
        if system_name == "Windows":
            # Prefer USERPROFILE, fallback to TEMP, then C:\\Temp
            home_dir = os.environ.get('USERPROFILE') or os.environ.get('TEMP') or 'C:\\Temp'
            cache_dir = str(Path(os.environ.get('TEMP') or home_dir) / '.cache' / 'openai')
            luigi_cfg = str(Path(os.environ.get('TEMP') or home_dir) / '.luigi')
            try:
                Path(cache_dir).mkdir(parents=True, exist_ok=True)
                Path(luigi_cfg).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"WARNING ENV: Failed to create Windows cache/config dirs: {e}")
            environment['HOME'] = home_dir
            environment['OPENAI_CACHE_DIR'] = cache_dir
            environment['LUIGI_CONFIG_PATH'] = luigi_cfg
            print(f"DEBUG ENV: Windows HOME={home_dir} OPENAI_CACHE_DIR={cache_dir} LUIGI_CONFIG_PATH={luigi_cfg}")
        else:
            # Railway/Linux: use /tmp which is writable at runtime
            environment['HOME'] = '/tmp'
            environment['OPENAI_CACHE_DIR'] = '/tmp/.cache/openai'
            environment['LUIGI_CONFIG_PATH'] = '/tmp/.luigi'
            print(f"DEBUG ENV: Set HOME=/tmp for SDK cache writes (Linux/Railway)")
        
        environment[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_id_dir)

        # Map API enum values to Luigi pipeline enum values (Source of Truth: planexe/plan/speedvsdetail.py)
        # Luigi only has 2 values: "all_details_but_slow" and "fast_but_skip_details"
        # API's "balanced_speed_and_detail" maps to "all_details_but_slow" per models.py line 25
        speed_vs_detail_mapping = {
            "all_details_but_slow": "all_details_but_slow",
            "balanced_speed_and_detail": "all_details_but_slow",  # Maps balanced to detailed mode
            "fast_but_skip_details": "fast_but_skip_details"
        }

        environment[PipelineEnvironmentEnum.SPEED_VS_DETAIL.value] = speed_vs_detail_mapping.get(
            request.speed_vs_detail.value, "all_details_but_slow"  # Default to detailed mode
        )
        environment[PipelineEnvironmentEnum.LLM_MODEL.value] = request.llm_model
        
        # EXPLICIT: Re-add API keys to ensure they're in subprocess env
        for key in required_keys.keys():
            value = os.environ.get(key)
            if value:
                environment[key] = value
                print(f"DEBUG ENV: Explicitly set {key} in subprocess environment")

        # CRITICAL: Add DATABASE_URL for Luigi database writes
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            environment["DATABASE_URL"] = database_url
            print(f"DEBUG ENV: Explicitly set DATABASE_URL in subprocess environment")
        else:
            print(f"WARNING ENV: DATABASE_URL not found in environment - Luigi will use SQLite fallback")

        print(f"DEBUG ENV: Pipeline environment configured with {len(environment)} variables")
        return environment

    def _write_pipeline_inputs(self, run_id_dir: Path, request: CreatePlanRequest) -> None:
        """Write input files required by Luigi pipeline"""
        # CRITICAL FIX: ALWAYS delete run directory before each plan to prevent Luigi from skipping tasks
        # Luigi checks if output files exist, and if they do, it considers tasks "already complete"
        # This was causing the production issue where Luigi would hang without executing tasks
        import shutil
        import os as os_module
        import logging
        logger = logging.getLogger(__name__)
        
        # Use logger.error() to ensure these messages appear in Railway logs (print() gets lost)
        logger.error(f"🔥🔥🔥 _write_pipeline_inputs() CALLED for: {run_id_dir}")
        logger.error(f"🔥🔥🔥 Directory exists? {run_id_dir.exists()}")
        print(f"🔥 _write_pipeline_inputs() called for run_id_dir: {run_id_dir}")
        print(f"🔥 run_id_dir.exists() = {run_id_dir.exists()}")
        
        if run_id_dir.exists():
            existing_files = list(run_id_dir.iterdir())
            logger.error(f"🔥🔥🔥 Directory EXISTS with {len(existing_files)} files - WILL DELETE!")
            print(f"🔥 CRITICAL: Run directory EXISTS with {len(existing_files)} files!")
            if len(existing_files) > 0:
                print(f"🔥 First 10 files: {[f.name for f in existing_files[:10]]}")
                print(f"🔥 Leftover files would cause Luigi to skip all tasks (thinks they're complete)")
            print(f"🔥 DELETING entire run directory: {run_id_dir}")
            try:
                shutil.rmtree(run_id_dir)
                logger.error(f"🔥🔥🔥 Directory DELETED successfully")
                print(f"🔥 ✅ Run directory DELETED successfully")
            except Exception as e:
                logger.error(f"🔥🔥🔥 ERROR deleting directory: {e}")
                print(f"🔥 ❌ ERROR deleting run directory: {e}")
                raise
        else:
            logger.error(f"🔥🔥🔥 Directory does NOT exist (fresh plan)")
            print(f"🔥 Run directory does NOT exist (fresh plan)")
        
        logger.error(f"🔥🔥🔥 Creating directory: {run_id_dir}")
        print(f"🔥 Creating clean run directory: {run_id_dir}")
        run_id_dir.mkdir(parents=True, exist_ok=True)
        logger.error(f"🔥🔥🔥 Directory created - writing input files...")
        print(f"🔥 ✅ Run directory created successfully")

        # PROOF OF CLEANUP: Write a marker file that Luigi can read to prove cleanup ran
        cleanup_marker = run_id_dir / "CLEANUP_RAN.txt"
        with open(cleanup_marker, "w", encoding="utf-8") as f:
            f.write(f"Directory cleanup executed at {datetime.utcnow().isoformat()}\n")
            f.write(f"Directory existed: {run_id_dir.exists()}\n")
            f.write(f"Cleanup function called from FastAPI process\n")
        logger.error(f"🔥🔥🔥 Wrote cleanup marker file: {cleanup_marker}")

        # Write start time
        start_time_file = run_id_dir / FilenameEnum.START_TIME.value
        with open(start_time_file, "w", encoding="utf-8") as f:
            f.write(datetime.utcnow().isoformat())
        print(f"🔥 Created {start_time_file.name}")

        # Write initial plan prompt
        initial_plan_file = run_id_dir / FilenameEnum.INITIAL_PLAN.value
        with open(initial_plan_file, "w", encoding="utf-8") as f:
            f.write(request.prompt)
        print(f"🔥 Created {initial_plan_file.name}")

        # DIAGNOSTIC: Verify only expected files exist
        all_files = list(run_id_dir.iterdir())
        print(f"🔥 Run directory now contains {len(all_files)} files: {[f.name for f in all_files]}")

    def _start_luigi_subprocess(self, plan_id: str, environment: Dict[str, str], db_service: DatabaseService) -> Optional[subprocess.Popen]:
        """Start Luigi pipeline subprocess"""
        import sys
        import platform

        python_executable = sys.executable
        system_name = platform.system()
        
        print(f"DEBUG: Python executable: {python_executable}")
        print(f"DEBUG: Python version: {sys.version}")
        print(f"DEBUG: System: {system_name}")
        
        # CRITICAL: Always use list format, NEVER shell=True to avoid encoding crashes
        command = [python_executable, "-m", MODULE_PATH_PIPELINE]
        use_shell = False

        print(f"DEBUG: Starting subprocess with command: {command}")
        print(f"DEBUG: Working directory: {self.planexe_project_root}")
        print(f"DEBUG: RUN_ID_DIR env var: {environment.get('RUN_ID_DIR')}")

        # use_shell defined above per OS

        try:
            # Sanity: show which API keys we are passing (masked)
            try:
                oa = environment.get('OPENAI_API_KEY')
                orr = environment.get('OPENROUTER_API_KEY')
                print(f"DEBUG ENV: OPENAI_API_KEY present? {bool(oa)} len={len(oa) if oa else 0}")
                print(f"DEBUG ENV: OPENROUTER_API_KEY present? {bool(orr)} len={len(orr) if orr else 0}")
            except Exception:
                pass

            # CRITICAL FIX: On Windows, avoid console encoding crashes (exit code 3221225794)
            # Match Gradio's working approach: merge stderr into stdout, use text mode
            popen_kwargs = {
                'cwd': str(self.planexe_project_root),
                'env': environment,
                'stdout': subprocess.PIPE,
                'stderr': subprocess.STDOUT,  # Merge stderr into stdout like Gradio
                'text': True,  # Text mode works when stderr is merged
                'bufsize': 1,
                'shell': use_shell
            }
            
            if system_name == "Windows":
                # Prevent console window creation
                popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(command, **popen_kwargs)
            print(f"DEBUG: Subprocess started with PID: {process.pid}")

            # Test if subprocess actually started
            if process.poll() is not None:
                raise subprocess.SubprocessError(f"Subprocess failed to start, exit code: {process.returncode}")

            # Store process reference in thread-safe registry
            process_registry.register(plan_id, process)
            return process

        except Exception as e:
            print(f"DEBUG: Subprocess creation failed: {e}")
            db_service.update_plan(plan_id, {
                "status": PlanStatus.failed.value,
                "error_message": f"Failed to start subprocess: {str(e)}"
            })
            return None

    async def _monitor_process_execution(self, plan_id: str, process: subprocess.Popen,
                                        run_id_dir: Path, db_service: DatabaseService) -> None:
        """Monitor Luigi process execution and stream progress via WebSocket"""
        import asyncio

        async def read_stdout():
            """Stream Luigi pipeline logs via WebSocket (includes stderr since merged)"""
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("LLM_STREAM|"):
                        _, _, payload_text = line.partition("|")
                        try:
                            stream_payload = json.loads(payload_text)
                        except json.JSONDecodeError:
                            stream_payload = {
                                "type": "log",
                                "message": f"[LLM_STREAM PARSE ERROR] {payload_text}",
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        if isinstance(stream_payload, dict):
                            stream_payload.setdefault("timestamp", datetime.utcnow().isoformat())
                            stream_payload.setdefault("type", "llm_stream")
                            try:
                                await websocket_manager.broadcast_to_plan(plan_id, stream_payload)
                            except Exception as e:
                                print(f"WebSocket stream payload error for plan {plan_id}: {e}")
                        continue

                    # Broadcast log line via WebSocket
                    log_data = {
                        "type": "log",
                        "message": line,
                        "timestamp": datetime.utcnow().isoformat()
                    }

                    try:
                        await websocket_manager.broadcast_to_plan(plan_id, log_data)
                    except Exception as e:
                        print(f"WebSocket broadcast error for plan {plan_id}: {e}")

                    print(f"Luigi: {line}")

                # Signal stdout completion
                completion_data = {
                    "type": "status",
                    "status": "stdout_closed",
                    "message": "Pipeline stdout stream closed",
                    "timestamp": datetime.utcnow().isoformat()
                }
                try:
                    await websocket_manager.broadcast_to_plan(plan_id, completion_data)
                except Exception:
                    pass

                process.stdout.close()

        # stderr is merged into stdout, so only need one monitoring task
        # Start monitoring task
        stdout_task = asyncio.create_task(read_stdout())

        # Wait for process completion in executor (blocking operation)
        loop = asyncio.get_event_loop()
        return_code = await loop.run_in_executor(None, process.wait)
        print(f"DEBUG: Luigi process completed with return code: {return_code}")

        # Wait for monitoring task to complete
        try:
            await asyncio.wait_for(stdout_task, timeout=5.0)
        except asyncio.TimeoutError:
            print(f"Warning: Monitoring task for plan {plan_id} timed out")
            stdout_task.cancel()

        # Update final plan status based on results
        await self._finalize_plan_status(plan_id, return_code, run_id_dir, db_service)

    async def _finalize_plan_status(self, plan_id: str, return_code: int, run_id_dir: Path,
                                  db_service: DatabaseService) -> None:
        """Update final plan status, index generated files, and broadcast via WebSocket"""

        if return_code == 0:
            # Check for expected final output file
            final_output_file = run_id_dir / FilenameEnum.REPORT.value

            if final_output_file.exists():
                # Success - broadcast completion message
                success_data = {
                    "type": "status",
                    "status": "completed",
                    "message": "✅ Pipeline completed successfully! All files generated.",
                    "progress_percentage": 100,
                    "timestamp": datetime.utcnow().isoformat()
                }
                try:
                    await websocket_manager.broadcast_to_plan(plan_id, success_data)
                except Exception as e:
                    print(f"WebSocket success broadcast failed for plan {plan_id}: {e}")

                # Index all generated files AND persist content to database (Option 3 fix)
                files = list(run_id_dir.iterdir())
                files_synced = 0
                content_bytes_synced = 0
                
                for file_path in files:
                    if file_path.is_file():
                        # Create file metadata record
                        db_service.create_plan_file({
                            "plan_id": plan_id,
                            "filename": file_path.name,
                            "file_type": file_path.suffix.lstrip('.') or 'unknown',
                            "file_size_bytes": file_path.stat().st_size,
                            "file_path": str(file_path),
                            "generated_by_stage": "pipeline_complete"
                        })
                        
                        # CRITICAL: Persist actual file content to database (Option 3 fix)
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            content_size = len(content.encode('utf-8'))
                            
                            # Determine content type from extension
                            ext = file_path.suffix.lstrip('.')
                            content_type_map = {
                                'json': 'json',
                                'md': 'markdown',
                                'html': 'html',
                                'csv': 'csv',
                                'txt': 'txt',
                                '': 'txt'
                            }
                            content_type = content_type_map.get(ext, 'unknown')
                            
                            # Extract stage from filename (e.g., "018-wbs_level1.json" -> "wbs_level1")
                            stage = None
                            if '-' in file_path.stem:
                                parts = file_path.stem.split('-', 1)
                                if len(parts) == 2:
                                    stage = parts[1]
                            
                            db_service.create_plan_content({
                                "plan_id": plan_id,
                                "filename": file_path.name,
                                "stage": stage,
                                "content_type": content_type,
                                "content": content,
                                "content_size_bytes": content_size
                            })
                            
                            files_synced += 1
                            content_bytes_synced += content_size
                            print(f"DEBUG: Synced {file_path.name} to database ({content_size} bytes)")
                            
                        except Exception as e:
                            print(f"WARNING: Could not sync {file_path.name} to database: {e}")
                            # Continue with other files even if one fails

                print(f"DEBUG: Synced {files_synced} files to database ({content_bytes_synced} bytes total)")

                db_service.update_plan(plan_id, {
                    "status": PlanStatus.completed.value,
                    "progress_percentage": 100,
                    "progress_message": f"Plan generation completed! {files_synced} files persisted to database.",
                    "completed_at": datetime.utcnow()
                })
            else:
                # Pipeline completed but no final output
                failure_data = {
                    "type": "status",
                    "status": "failed",
                    "message": "❌ Pipeline completed but final output file not found",
                    "timestamp": datetime.utcnow().isoformat()
                }
                try:
                    await websocket_manager.broadcast_to_plan(plan_id, failure_data)
                except Exception as e:
                    print(f"WebSocket failure broadcast failed for plan {plan_id}: {e}")

                db_service.update_plan(plan_id, {
                    "status": PlanStatus.failed.value,
                    "error_message": "Pipeline did not complete successfully"
                })
        else:
            # Attempt agent-style minimal fallback to avoid leaving the user stuck
            if os.environ.get("PLANEXE_ENABLE_AGENT_FALLBACK", "true").lower() == "true":
                try:
                    await websocket_manager.broadcast_to_plan(plan_id, {
                        "type": "status",
                        "status": "fallback",
                        "message": "Luigi failed. Switching to minimal agent fallback...",
                        "timestamp": datetime.utcnow().isoformat()
                    })

                    if self._run_fallback_minimal_report(plan_id, run_id_dir, db_service):
                        # Fallback produced a minimal final report; mark completed
                        await websocket_manager.broadcast_to_plan(plan_id, {
                            "type": "status",
                            "status": "completed",
                            "message": "✅ Fallback completed. Minimal report generated.",
                            "progress_percentage": 100,
                            "timestamp": datetime.utcnow().isoformat()
                        })

                        db_service.update_plan(plan_id, {
                            "status": PlanStatus.completed.value,
                            "progress_percentage": 100,
                            "progress_message": "Plan completed via fallback (minimal report)",
                            "completed_at": datetime.utcnow()
                        })

                        # End stream and cleanup
                        end_data = {
                            "type": "stream_end",
                            "message": "Pipeline execution completed - closing connections",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        try:
                            await websocket_manager.broadcast_to_plan(plan_id, end_data)
                            await websocket_manager.cleanup_plan_connections(plan_id)
                        except Exception:
                            pass
                        return
                except Exception as e:
                    print(f"Fallback error for plan {plan_id}: {e}")

            # Existing failure behavior if fallback not enabled or failed
            failure_data = {
                "type": "status",
                "status": "failed",
                "message": f"❌ Pipeline failed with exit code {return_code}",
                "timestamp": datetime.utcnow().isoformat()
            }
            try:
                await websocket_manager.broadcast_to_plan(plan_id, failure_data)
            except Exception as e:
                print(f"WebSocket failure broadcast failed for plan {plan_id}: {e}")

            db_service.update_plan(plan_id, {
                "status": PlanStatus.failed.value,
                "error_message": f"Pipeline process failed with exit code {return_code}"
            })

        # Signal end of stream and cleanup connections
        end_data = {
            "type": "stream_end",
            "message": "Pipeline execution completed - closing connections",
            "timestamp": datetime.utcnow().isoformat()
        }
        try:
            await websocket_manager.broadcast_to_plan(plan_id, end_data)
            await websocket_manager.cleanup_plan_connections(plan_id)
        except Exception as e:
            print(f"WebSocket end stream broadcast failed for plan {plan_id}: {e}")

    # --- New helper: minimal fallback report generator ---
    def _run_fallback_minimal_report(self, plan_id: str, run_id_dir: Path, db_service: DatabaseService) -> bool:
        """
        Generate a minimal final report when Luigi fails, so the UI can still display results.
        Does not invoke Luigi; produces a Plan Lite HTML using the user's prompt.
        Returns True on success.
        """
        try:
            prompt_text = ""
            try:
                prompt_text = (run_id_dir / FilenameEnum.INITIAL_PLAN.value).read_text(encoding='utf-8')
            except Exception:
                prompt_text = "(initial prompt unavailable)"

            now_iso = datetime.utcnow().isoformat()
            html = f"""
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>PlanExe Report (Fallback)</title>
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 2rem; }}
      .badge {{ display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; background: #ffe9a8; color: #7a5d00; font-weight: 600; margin-bottom: 1rem; }}
      pre {{ background: #f5f5f5; padding: 1rem; border-radius: 6px; white-space: pre-wrap; }}
    </style>
  </head>
  <body>
    <div class=\"badge\">Fallback Report</div>
    <h1>PlanExe Minimal Report</h1>
    <p>Luigi pipeline failed. A minimal fallback report was generated to avoid blocking your workflow.</p>
    <h2>Initial Prompt</h2>
    <pre>{prompt_text}</pre>
    <h2>Status</h2>
    <ul>
      <li>Generation mode: agent fallback (minimal)</li>
      <li>Timestamp (UTC): {now_iso}</li>
      <li>Plan ID: {plan_id}</li>
    </ul>
    <p style=\"margin-top:2rem;color:#666\">You can re-run later to produce the full 61-task plan once Luigi is healthy.</p>
  </body>
</html>
            """

            report_path = run_id_dir / FilenameEnum.REPORT.value
            report_path.write_text(html, encoding='utf-8')

            # Persist to database (Option 3 path) so the UI can fetch content
            try:
                db_service.create_plan_content({
                    "plan_id": plan_id,
                    "filename": FilenameEnum.REPORT.value,
                    "stage": "reporting",
                    "content_type": "html",
                    "content": html,
                    "content_size_bytes": len(html.encode('utf-8'))
                })
            except Exception as e:
                print(f"WARNING: Could not persist fallback report to DB for plan {plan_id}: {e}")

            return True
        except Exception as e:
            print(f"Fallback generation failed for plan {plan_id}: {e}")
            return False

    async def _cleanup_execution(self, plan_id: str) -> None:
        """Clean up execution resources and WebSocket connections"""
        # Remove process reference from thread-safe registry
        process = process_registry.unregister(plan_id)
        if process:
            print(f"DEBUG: Removed process reference for plan {plan_id}")

        # Ensure all WebSocket connections are cleaned up
        await websocket_manager.cleanup_plan_connections(plan_id)

        print(f"DEBUG: Cleaned up execution resources for {plan_id}")

    def get_process(self, plan_id: str) -> Optional[subprocess.Popen]:
        """Get subprocess reference for a plan (thread-safe)"""
        return process_registry.get(plan_id)

    def terminate_plan_execution(self, plan_id: str) -> bool:
        """Terminate a running plan execution (thread-safe)"""
        process = process_registry.get(plan_id)
        if process and process.poll() is None:  # Process is still running
            try:
                process.terminate()
                print(f"Terminated process for plan {plan_id}")
                return True
            except Exception as e:
                print(f"Failed to terminate process for plan {plan_id}: {e}")
                return False
        return False
