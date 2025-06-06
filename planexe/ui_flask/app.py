import logging
import os
import re
import sys
import time
import json
import uuid
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import subprocess
import threading
from enum import Enum
from flask import Flask, render_template, Response, request, jsonify, send_file
import importlib.resources
from planexe.utils.planexe_dotenv import PlanExeDotEnv
from planexe.utils.planexe_config import PlanExeConfig
from planexe.plan.generate_run_id import generate_run_id
from planexe.plan.plan_file import PlanFile
from planexe.plan.filenames import FilenameEnum, ExtraFilenameEnum
from planexe.prompt.prompt_catalog import PromptCatalog
from planexe.llm_factory import SPECIAL_AUTO_ID, get_llm_names_by_priority, get_llm
from planexe.plan.speedvsdetail import SpeedVsDetailEnum
from planexe.plan.pipeline_environment import PipelineEnvironmentEnum
from llama_index.core.llms import ChatMessage, MessageRole

logger = logging.getLogger(__name__)

MODULE_PATH_PIPELINE = "planexe.plan.run_plan_pipeline"
RUN_DIR = "run"

SHOW_DEMO_PLAN = True

DEMO1_PROMPT_UUID = "4dc34d55-0d0d-4e9d-92f4-23765f49dd29"
DEMO2_PROMPT_UUIDS = [
    "0ad5ea63-cf38-4d10-a3f3-d51baa609abd",
    "00e1c738-a663-476a-b950-62785922f6f0",
    "3ca89453-e65b-4828-994f-dff0b679444a"
]

@dataclass
class Config:
    use_uuid_as_run_id: bool

CONFIG = Config(
    use_uuid_as_run_id=False,
)

class JobStatus(str, Enum):
    running = 'running'
    completed = 'completed'
    failed = 'failed'
    cancelled = 'cancelled'
    pending = 'pending'

@dataclass
class JobState:
    """State for a single job"""
    run_id: str
    run_path: str
    environment: Dict[str, str]
    process: Optional[subprocess.Popen] = None
    stop_event: threading.Event = threading.Event()
    status: JobStatus = JobStatus.pending
    error: Optional[str] = None
    progress_message: str = ""
    progress_percentage: int = 0

@dataclass
class UserState:
    """State for a single user"""
    user_id: str
    current_run_id: Optional[str] = None

class MyFlaskApp:
    def __init__(self):
        logger.info(f"MyFlaskApp.__init__. Starting...")

        self.planexe_config = PlanExeConfig.load()
        logger.info(f"MyFlaskApp.__init__. planexe_config: {self.planexe_config!r}")

        self.planexe_dotenv = PlanExeDotEnv.load()
        logger.info(f"MyFlaskApp.__init__. planexe_dotenv: {self.planexe_dotenv!r}")

        self.path_to_python = self.planexe_dotenv.get("OVERRIDE_PATH_TO_PYTHON")
        if self.path_to_python is None:
            self.path_to_python = sys.executable
        logger.info(f"MyFlaskApp.__init__. path_to_python: {self.path_to_python}")
        
        self.planexe_dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        logger.info(f"MyFlaskApp.__init__. planexe_dir_path: {self.planexe_dir_path!r}")

        self.run_dir_path = os.path.abspath(os.path.join(self.planexe_dir_path, RUN_DIR))
        logger.info(f"MyFlaskApp.__init__. run_dir_path: {self.run_dir_path!r}")

        self._start_check()

        self.jobs: Dict[str, JobState] = {}
        self.users: Dict[str, UserState] = {}

        # Load prompt catalog and examples.
        self.prompt_catalog = PromptCatalog()
        self.prompt_catalog.load_simple_plan_prompts()

        # Point to the "templates" dir.
        template_folder = None
        try:
            resource_path = 'planexe.ui_flask.templates'
            template_dir_traversable = importlib.resources.files(resource_path)
            template_folder = str(template_dir_traversable)
            logger.info(f"MyFlaskApp.__init__. found resource: {resource_path!r}")
        except Exception as e:
            logger.error(f"MyFlaskApp.__init__. Error loading template_dir_traversable: {e}. Using default template folder.")

        logger.info(f"MyFlaskApp.__init__. template_folder: {template_folder!r}")
        self.app = Flask(__name__, template_folder=template_folder)

        self._setup_routes()

    def _start_check(self):
        # print the environment variables
        logger.info(f"MyFlaskApp._start_check. environment variables: {os.environ}")

        issue_count = 0
        if not os.path.exists(self.path_to_python):
            logger.error(f"The python executable does not exist at this point. However the python executable should exist: {self.path_to_python!r}")
            issue_count += 1
        if not os.path.exists(self.planexe_dir_path):
            logger.error(f"The planexe_dir_path does not exist at this point. However the planexe_dir_path should exist: {self.planexe_dir_path!r}")
            issue_count += 1
        if issue_count > 0:
            raise Exception(f"There are {issue_count} issues with the python executable and project root directory")

    def _create_job_internal(self, run_id: str, run_path: str) -> Tuple[Dict[str, Any], int]:
        """
        Internal logic for creating a job.
        Called by both the /jobs endpoint and other internal functions.
        job_data is the full dictionary that would have come from request.json
        """
        if not run_id:
            return {"error": "run_id is required"}, 400

        if run_id in self.jobs:
            return {"error": "run_id already exists"}, 409

        if not os.path.exists(run_path):
            raise Exception(f"The run_path directory is supposed to exist at this point. However no run_path directory exists: {run_path}")

        environment = os.environ.copy()
        environment[PipelineEnvironmentEnum.RUN_ID.value] = run_id
        environment[PipelineEnvironmentEnum.LLM_MODEL.value] = SPECIAL_AUTO_ID
        environment[PipelineEnvironmentEnum.SPEED_VS_DETAIL.value] = SpeedVsDetailEnum.ALL_DETAILS_BUT_SLOW.value

        # Create job state
        job = JobState(run_id=run_id, run_path=run_path, environment=environment)
        self.jobs[run_id] = job

        # Start the job in a background thread
        threading.Thread(target=self._run_job, args=[job]).start()

        return {
            "run_id": run_id,
            "status": "pending"
        }, 202
    
    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/developer')
        def developer():
            return render_template('developer.html')

        @self.app.route('/ping')
        def ping():
            return render_template('ping.html')

        @self.app.route('/ping/stream')
        def ping_stream():
            def generate():
                llm_names = get_llm_names_by_priority()

                for llm_name in llm_names:
                    # Send "pinging" status
                    yield f"data: {json.dumps({
                        'name': llm_name,
                        'status': 'pinging',
                        'response_time': 0,
                        'response': 'Pinging model...'
                    })}\n\n"

                    try:
                        start_time = time.time()
                        llm = get_llm(llm_name)
                        
                        # Test message
                        chat_message_list = [
                            ChatMessage(
                                role=MessageRole.USER,
                                content="Hello, this is a test message. Please respond with 'OK' if you can read this."
                            )
                        ]
                        
                        response = llm.chat(chat_message_list)
                        end_time = time.time()
                        
                        result = {
                            'name': llm_name,
                            'status': 'success',
                            'response_time': int((end_time - start_time) * 1000),  # Convert to milliseconds
                            'response': response.message.content
                        }
                    except Exception as e:
                        result = {
                            'name': llm_name,
                            'status': 'error',
                            'response_time': 0,
                            'response': str(e)
                        }
                    
                    yield f"data: {json.dumps(result)}\n\n"

                # Send final "done" status
                yield f"data: {json.dumps({
                    'name': 'server',
                    'status': 'done',
                    'response_time': 0,
                    'response': ''
                })}\n\n"

            response = Response(generate(), mimetype='text/event-stream')
            response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering
            return response

        @self.app.route("/jobs", methods=["POST"])
        def create_job():
            try:
                data = request.json
                run_id = generate_run_id(CONFIG.use_uuid_as_run_id)
                run_path = os.path.join(self.run_dir_path, run_id)
                absolute_path_to_run_dir = os.path.abspath(run_path)
                response_data, status_code = self._create_job_internal(run_id, absolute_path_to_run_dir)
                return jsonify(response_data), status_code            
            except Exception as e:
                logger.error(f"Error creating job: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/jobs/stop_all", methods=["POST"])
        def stop_all_jobs():
            try:
                running_jobs = [job for job in self.jobs.values() if job.status == JobStatus.running]
                logger.info(f"Stopping {len(running_jobs)} running jobs")
                for job in running_jobs:
                    job.stop_event.set()
                return jsonify({"message": f"Stopped {len(running_jobs)} jobs"}), 200
            except Exception as e:
                logger.error(f"Error stopping jobs: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500

        @self.app.route('/run')
        def run():
            prompt_param = request.args.get('prompt', '')
            user_id_param = request.args.get('user_id', '')

            # Ensure the string contain a-zA-Z0-9-_ so it's safe to use in filenames/database
            if not re.match(r'^[a-zA-Z0-9\-_]{1,80}$', user_id_param):
                logger.error(f"endpoint /run. Invalid formatting for user_id. parameters: prompt={prompt_param}, user_id_param={user_id_param}")
                return jsonify({"error": "Invalid user_id"}), 400

            if user_id_param not in self.users:
                logger.error(f"endpoint /run. No such user_id. parameters: prompt={prompt_param}, user_id_param={user_id_param}")
                return jsonify({"error": "Invalid user_id"}), 400

            logger.info(f"endpoint /run. Starting run with parameters: prompt={prompt_param}, user_id_param={user_id_param}")

            current_user = self.users[user_id_param]
            if current_user.current_run_id is not None:
                logger.info(f"endpoint /run. User {user_id_param} already has a current run_id. Stopping it first.")
                self.jobs[current_user.current_run_id].stop_event.set()
                current_user.current_run_id = None

            run_id = generate_run_id(CONFIG.use_uuid_as_run_id)
            run_path = os.path.join(self.run_dir_path, run_id)
            absolute_path_to_run_dir = os.path.abspath(run_path)

            logger.info(f"endpoint /run. current working directory: {os.getcwd()}")
            logger.info(f"endpoint /run. run_id: {run_id}")
            logger.info(f"endpoint /run. run_path: {run_path}")
            logger.info(f"endpoint /run. absolute_path_to_run_dir: {absolute_path_to_run_dir}")

            if os.path.exists(run_path):
                raise Exception(f"The run path is not supposed to exist at this point. However the run path already exists: {run_path}")
            os.makedirs(run_path, exist_ok=True)

            # Create the initial plan file.
            plan_file = PlanFile.create(prompt_param)
            plan_file.save(os.path.join(run_path, FilenameEnum.INITIAL_PLAN.value))

            response_data, status_code = self._create_job_internal(run_id, absolute_path_to_run_dir)
            if status_code != 202:
                logger.error(f"Error creating job internally: {response_data}")
                return jsonify({"error": "Failed to create job", "details": response_data}), 500

            current_user.current_run_id = run_id

            logger.info(f"endpoint /run. render_template. run_id={run_id} user_id={user_id_param}")

            return render_template('run.html', user_id=user_id_param)

        @self.app.route('/progress')
        def get_progress():
            user_id = request.args.get('user_id', '')
            logger.info(f"Progress endpoint received user_id: {user_id}")
            if user_id not in self.users:
                logger.error(f"Invalid User ID: {user_id}")
                return jsonify({"error": "Invalid user_id"}), 400
            
            user_state = self.users[user_id]
            if user_state.current_run_id is None:
                logger.error(f"No current_run_id for user: {user_id}")
                return jsonify({"error": "Invalid user_id"}), 400
            run_id = user_state.current_run_id

            job = self.jobs.get(run_id)
            if not job:
                logger.error(f"Job not found for run_id: {run_id}")
                return jsonify({"error": "Job not found"}), 400
            
            def generate():
                try:
                    while True:
                        # Send the current progress value
                        is_running = job.status == JobStatus.running
                        logger.info(f"Current job status: {job.status}, is_running: {is_running}")
                        if is_running:
                            progress_message = job.progress_message
                        else:
                            progress_message = f"{job.status.value}, {job.progress_message}"

                        data = json.dumps({'progress_message': progress_message, 'progress_percentage': job.progress_percentage, 'status': job.status.value})
                        yield f"data: {data}\n\n"
                        time.sleep(1)
                        if not is_running:
                            logger.info(f"Progress endpoint received user_id: {user_id} is done")
                            break
                except GeneratorExit:
                    # Client disconnected
                    logger.info(f"Client disconnected for user_id: {user_id}")
                    job.stop_event.set()
                except Exception as e:
                    logger.error(f"Error in progress stream for user_id {user_id}: {e}")
                    job.stop_event.set()

            response = Response(generate(), mimetype='text/event-stream')
            response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering
            return response

        @self.app.route('/viewplan')
        def viewplan():
            user_id = request.args.get('user_id', '')
            if user_id not in self.users:
                logger.error(f"Invalid User ID: {user_id}")
                return jsonify({"error": "Invalid user_id"}), 400
            
            user_state = self.users[user_id]
            if user_state.current_run_id is None:
                logger.error(f"No current_run_id for user: {user_id}")
                return jsonify({"error": "Invalid user_id"}), 400
            run_id = user_state.current_run_id
            if SHOW_DEMO_PLAN:
                run_id = '20250524_universal_manufacturing'

            logger.info(f"ViewPlan endpoint. user_id={user_id} run_id={run_id}")

            run_path = os.path.join(self.run_dir_path, run_id)
            absolute_path_to_run_dir = os.path.abspath(run_path)
            if not os.path.exists(absolute_path_to_run_dir):
                raise Exception(f"Run directory not found at {absolute_path_to_run_dir}. Please ensure the run directory exists before viewing the plan.")

            path_to_html_file = os.path.join(absolute_path_to_run_dir, FilenameEnum.REPORT.value)
            if not os.path.exists(path_to_html_file):
                raise Exception(f"The html file does not exist at this point. However the html file should exist: {path_to_html_file}")
            return send_file(path_to_html_file, mimetype='text/html')

        @self.app.route('/demo1')
        def demo1():
            # Assign a uuid to the user, so their data belongs to the right user
            user_id = str(uuid.uuid4())
            user_state = UserState(user_id=user_id)
            self.users[user_id] = user_state

            prompt_uuid = DEMO1_PROMPT_UUID
            prompt_item = self.prompt_catalog.find(prompt_uuid)
            if prompt_item is None:
                logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo1")
                return "Error: Demo prompt configuration missing.", 500
            return render_template('demo1.html', prompt=prompt_item.prompt, user_id=user_id)

        @self.app.route('/demo2')
        def demo2():
            # Assign a uuid to the user, so their data belongs to the right user
            user_id = str(uuid.uuid4())
            user_state = UserState(user_id=user_id)
            self.users[user_id] = user_state

            # The prompts to be shown on the page.
            prompts = []
            for prompt_uuid in DEMO2_PROMPT_UUIDS:
                prompt_item = self.prompt_catalog.find(prompt_uuid)
                if prompt_item is None:
                    logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo2")
                    return "Error: Demo prompt configuration missing.", 500
                prompts.append(prompt_item.prompt)

            return render_template('demo2.html', user_id=user_id, prompts=prompts)

        @self.app.route('/demo_subprocess_run_simple')
        def demo_subprocess_run_simple():
            topic = 'subprocess.run with simple command'
            template = 'check_is_working.html'
            try:
                result = subprocess.run(
                    ["/usr/bin/uname", "-a"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                output = result.stdout.strip()
                return render_template(template, topic=topic, output=output, error=None)
            except subprocess.CalledProcessError as e:
                logger.error(f"demo_subprocess_run_simple. Subprocess failed with exit code {e.returncode}. stdout: {e.stdout!r}, stderr: {e.stderr!r}")
                message = "subprocess.CalledProcessError, see log for details."
                return render_template(template, topic=topic, output=None, error=message)
            except Exception as e:
                logger.error(f"demo_subprocess_run_simple. Unexpected error: {str(e)}")
                message = "Exception, see log for details."
                return render_template(template, topic=topic, output=None, error=message)

        @self.app.route('/demo_subprocess_run_medium')
        def demo_subprocess_run_medium():
            topic = 'subprocess.run with python pinging OpenRouter'
            template = 'check_is_working.html'
            try:
                env = os.environ.copy()
                logger.info(f"demo_subprocess_run_medium. planexe_dotenv: {self.planexe_dotenv!r}")
                logger.info(f"demo_subprocess_run_medium. planexe_dir_path: {self.planexe_dir_path!r}")
                logger.info(f"demo_subprocess_run_medium. path_to_python: {self.path_to_python!r}")
                env["OPENROUTER_API_KEY"] = self.planexe_dotenv.get("OPENROUTER_API_KEY")
                result = subprocess.run(
                    [self.path_to_python, "-m", "planexe.proof_of_concepts.run_ping_simple"],
                    capture_output=True,
                    text=True,
                    check=True,
                    env=env,
                    cwd=self.planexe_dir_path
                )
                output = result.stdout.strip()
                return render_template(template, topic=topic, output=output, error=None)
            except subprocess.CalledProcessError as e:
                logger.error(f"demo_subprocess_run_medium. Subprocess failed with exit code {e.returncode}. stdout: {e.stdout!r}, stderr: {e.stderr!r}")
                message = "subprocess.CalledProcessError, see log for details."
                return render_template(template, topic=topic, output=None, error=message)
            except Exception as e:
                logger.error(f"demo_subprocess_run_medium. Unexpected error: {str(e)}")
                message = "Exception, see log for details."
                return render_template(template, topic=topic, output=None, error=message)

        @self.app.route('/demo_subprocess_run_advanced')
        def demo_subprocess_run_advanced():
            topic = 'subprocess.run with python pinging OpenRouter. Uses LlamaIndex.'
            template = 'check_is_working.html'
            try:
                env = os.environ.copy()
                logger.info(f"demo_subprocess_run_advanced. planexe_dotenv: {self.planexe_dotenv!r}")
                logger.info(f"demo_subprocess_run_advanced. planexe_dir_path: {self.planexe_dir_path!r}")
                logger.info(f"demo_subprocess_run_advanced. path_to_python: {self.path_to_python!r}")
                env["OPENROUTER_API_KEY"] = self.planexe_dotenv.get("OPENROUTER_API_KEY")
                result = subprocess.run(
                    [self.path_to_python, "-m", "planexe.proof_of_concepts.run_ping_medium"],
                    capture_output=True,
                    text=True,
                    check=True,
                    env=env,
                    cwd=self.planexe_dir_path
                )
                output = result.stdout.strip()
                return render_template(template, topic=topic, output=output, error=None)
            except subprocess.CalledProcessError as e:
                logger.error(f"demo_subprocess_run_advanced. Subprocess failed with exit code {e.returncode}. stdout: {e.stdout!r}, stderr: {e.stderr!r}")
                message = "subprocess.CalledProcessError, see log for details."
                return render_template(template, topic=topic, output=None, error=message)
            except Exception as e:
                logger.error(f"demo_subprocess_run_advanced. Unexpected error: {str(e)}")
                message = "Exception, see log for details."
                return render_template(template, topic=topic, output=None, error=message)

        @self.app.route('/demo_eventsource')
        def demo_eventsource():
            return render_template('demo_eventsource.html')

        @self.app.route('/demo_eventsource/stream')
        def demo_eventsource_stream():
            def event_stream():
                start_time = time.time()
                count = 0
                try:
                    while time.time() - start_time < 30:  # Run for 30 seconds
                        time.sleep(1)  # Send an event every second
                        count += 1
                        # CRITICAL: Ensure you have two newlines at the end of each message
                        yield f"data: Message number {count}\n\n"
                    # Send a final message to indicate completion
                    yield f"data: Stream completed after {count} messages\n\n"
                except GeneratorExit:
                    # Client disconnected, stop the stream
                    logger.info("Client disconnected from demo_eventsource stream")
                    return
            response = Response(event_stream(), mimetype='text/event-stream')
            response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering
            return response

    def _run_job(self, job: JobState):
        """Run the actual job in a subprocess"""
        
        try:
            run_path = job.run_path
            if not os.path.exists(run_path):
                raise Exception(f"The run_path directory is supposed to exist at this point. However the output directory does not exist: {run_path}")

            # Start the process
            command = [self.path_to_python, "-m", MODULE_PATH_PIPELINE]
            # command = [self.path_to_python, "--version"]
            # python_executable = "/home/neoneye/git/PlanExe/planexe_run.sh"
            # command = [python_executable]
            # python_executable = "/usr/bin/git"
            # python_executable = self.path_to_python
            # command = [python_executable, "--version"]
            logger.info(f"_run_job. subprocess.Popen before command: {command!r}")
            logger.info(f"_run_job. CWD for subprocess: {self.planexe_dir_path!r}")
            logger.info(f"_run_job. Environment keys for subprocess (sample): "
                        f"RUN_ID={job.environment.get(PipelineEnvironmentEnum.RUN_ID.value)!r}")


            job.process = subprocess.Popen(
                command,
                cwd=self.planexe_dir_path,
                env=job.environment, # This passes the parent's environment, including VIRTUAL_ENV if set
                stdout=subprocess.PIPE, # Capture stdout
                stderr=subprocess.PIPE, # Capture stderr
                text=True # Decode stdout/stderr as text
            )
            logger.info(f"_run_job. subprocess.Popen after command: {command!r} with PID: {job.process.pid}")

            job.status = JobStatus.running

            # Monitor the process
            while True:
                if job.stop_event.is_set():
                    logger.info(f"_run_job: Stop event set for run_id {job.run_id}. Terminating process.")
                    job.process.terminate()
                    try:
                        # Wait a bit for graceful termination
                        job.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning(f"_run_job: Process {job.process.pid} did not terminate gracefully. Killing.")
                        job.process.kill()
                    job.status = JobStatus.cancelled
                    break

                return_code = job.process.poll()
                if return_code is not None:
                    stdout, stderr = job.process.communicate() # Get remaining output
                    if stdout:
                        logger.info(f"_run_job {job.run_id} STDOUT:\n{stdout}")
                    if stderr:
                        logger.error(f"_run_job {job.run_id} STDERR:\n{stderr}")

                    if return_code == 0:
                        job.status = JobStatus.completed
                        logger.info(f"_run_job: Process for run_id {job.run_id} completed successfully.")
                    else:
                        job.status = JobStatus.failed
                        job.error = f"Process exited with code {return_code}. Stderr: {stderr[:500]}" # Log part of stderr
                        logger.error(f"_run_job: Process for run_id {job.run_id} failed with code {return_code}.")
                    break

                # Update progress (same logic as before)
                files = []
                try:
                    if os.path.exists(run_path) and os.path.isdir(run_path):
                        files = os.listdir(run_path)
                except OSError as e:
                    logger.warning(f"_run_job: Could not list files in {run_path}: {e}")

                ignore_files = [
                    ExtraFilenameEnum.EXPECTED_FILENAMES1_JSON.value,
                    ExtraFilenameEnum.LOG_TXT.value
                ]
                files = [f for f in files if f not in ignore_files]
                # logger.debug(f"Files in run_path for {job.run_id}: {files}") # Debug, can be noisy
                number_of_files = len(files)
                # logger.debug(f"Number of files in run_path for {job.run_id}: {number_of_files}") # Debug

                # Determine the progress, by comparing the generated files with the expected_filenames1.json
                expected_filenames_path = os.path.join(run_path, ExtraFilenameEnum.EXPECTED_FILENAMES1_JSON.value)
                assign_progress_message = f"File count: {number_of_files}"
                assign_progress_percentage = 0
                if os.path.exists(expected_filenames_path):
                    with open(expected_filenames_path, "r") as f:
                        expected_filenames = json.load(f)
                    set_files = set(files)
                    set_expected_files = set(expected_filenames)
                    intersection_files = set_files & set_expected_files
                    assign_progress_message = f"{len(intersection_files)} of {len(set_expected_files)}"
                    if len(set_expected_files) > 0:
                        assign_progress_percentage = (len(intersection_files) * 100) // len(set_expected_files)

                job.progress_message = assign_progress_message
                job.progress_percentage = assign_progress_percentage

                time.sleep(1)

        except Exception as e:
            logger.error(f"Error running job {job.run_id}: {e}", exc_info=True)
            job.status = JobStatus.failed
            job.error = str(e)
        finally:
            # End of the job. No matter what, clear the stop event, so that the user can start a new job.
            job.stop_event.clear()
            logger.info(f"_run_job: Finished processing job {job.run_id} with status {job.status}.")
            if job.process and job.process.poll() is None: # Ensure process is cleaned up if loop exited abnormally
                logger.warning(f"_run_job: Job {job.run_id} loop exited but process {job.process.pid} still running. Terminating.")
                job.process.terminate()
                job.process.wait() # Wait for termination


    def run_server(self, debug=True, host='127.0.0.1', port=5000):
        self.app.run(debug=debug, host=host, port=port)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(threadName)s - %(message)s'
    )
    flask_app_instance = MyFlaskApp()
    flask_app_instance.run_server(debug=True)