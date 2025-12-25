"""
Flask UI for PlanExe-server.

PROMPT> python3 -m src.app
"""
from datetime import datetime, UTC
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
from pathlib import Path
from flask import Flask, render_template, Response, request, jsonify, send_file, redirect, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from functools import wraps
from flask import make_response
from planexe.utils.planexe_dotenv import DotEnvKeyEnum, PlanExeDotEnv
from planexe.utils.planexe_config import PlanExeConfig
from planexe.plan.generate_run_id import generate_run_id
from planexe.plan.start_time import StartTime
from planexe.plan.plan_file import PlanFile
from planexe.plan.filenames import FilenameEnum, ExtraFilenameEnum
from planexe.prompt.prompt_catalog import PromptCatalog
from planexe.llm_factory import SPECIAL_AUTO_ID, get_llm_names_by_priority, get_llm
from planexe.plan.speedvsdetail import SpeedVsDetailEnum
from planexe.plan.pipeline_environment import PipelineEnvironmentEnum
from llama_index.core.llms import ChatMessage, MessageRole
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from model_taskitem import TaskItem, TaskState
from model_event import EventType, EventItem
from model_worker import WorkerItem
from model_nonce import NonceItem
from planexe_modelviews import WorkerItemView, TaskItemView, NonceItemView

logger = logging.getLogger(__name__)

# IDEA: move secrets to env vars.
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

MODULE_PATH_PIPELINE = "planexe.plan.run_plan_pipeline"
RUN_DIR = "run"

SHOW_DEMO_PLAN = False

DEMO_INSTANT_RUN_PROMPT_UUID = "4dc34d55-0d0d-4e9d-92f4-23765f49dd29"
DEMO_FORM_RUN_PROMPT_UUIDS = [
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
    run_id_dir: Path
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

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        return super(MyAdminIndexView, self).index()

def nocache(view):
    """Decorator to add 'no-cache' headers to a response."""
    @wraps(view)
    def no_cache_view(*args, **kwargs):
        # Call the original view function
        response = make_response(view(*args, **kwargs))
        # Modify headers
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1' # Or any date in the past, or 0
        return response
    return no_cache_view

class MyFlaskApp:
    def __init__(self):
        logger.info(f"MyFlaskApp.__init__. Starting...")

        self.planexe_config = PlanExeConfig.load()
        logger.info(f"MyFlaskApp.__init__. planexe_config: {self.planexe_config!r}")

        self.planexe_dotenv = PlanExeDotEnv.load()
        logger.info(f"MyFlaskApp.__init__. planexe_dotenv: {self.planexe_dotenv!r}")

        # This is a workaround to fix the inconsistency.
        # Workaround-problem: When the Flask app launches in debug mode it runs __init__ twice, so that the app can hot reload.
        # However there is this inconsistency.
        # 1st time, the os.environ is the original environment of the shell.
        # 2nd time, the os.environ is the original environment of the shell + the .env content.
        # If it was the same in both cases, it would be easier to reason about the environment variables.
        # On following hot reloads, the os.environ continues to be the original environment of the shell + the .env content.
        # Workaround-solution: Every time update the os.environ with the .env content, so that the os.environ is always the 
        # original environment of the shell + the .env content.
        # I prefer NEVER to modify the os.environ for the current process, and instead spawn a child process with the modified os.environ.
        self.planexe_dotenv.update_os_environ()

        override_path_to_python = self.planexe_dotenv.get_absolute_path_to_file(DotEnvKeyEnum.PATH_TO_PYTHON.value)
        if isinstance(override_path_to_python, Path):
            debug_path_to_python = 'override'
            self.path_to_python = override_path_to_python
        else:
            debug_path_to_python = 'default'
            self.path_to_python = Path(sys.executable)
        logger.info(f"MyFlaskApp.__init__. path_to_python ({debug_path_to_python}): {self.path_to_python!r}")
        
        self.planexe_project_root = Path(__file__).parent.parent.parent.absolute()
        logger.info(f"MyFlaskApp.__init__. planexe_project_root: {self.planexe_project_root!r}")

        override_planexe_run_dir = self.planexe_dotenv.get_absolute_path_to_dir(DotEnvKeyEnum.PLANEXE_RUN_DIR.value)
        if isinstance(override_planexe_run_dir, Path):
            debug_planexe_run_dir = 'override'
            self.planexe_run_dir = override_planexe_run_dir
        else:
            debug_planexe_run_dir = 'default'
            self.planexe_run_dir = self.planexe_project_root / RUN_DIR
        logger.info(f"MyFlaskApp.__init__. planexe_run_dir ({debug_planexe_run_dir}): {self.planexe_run_dir!r}")

        self._start_check()

        self.jobs: Dict[str, JobState] = {}
        self.users: Dict[str, UserState] = {}

        # Load prompt catalog and examples.
        self.prompt_catalog = PromptCatalog()
        self.prompt_catalog.load_simple_plan_prompts()

        # Point to the "templates" dir.
        template_folder = os.path.join(os.path.dirname(__file__), "templates")
        logger.info(f"MyFlaskApp.__init__. template_folder: {template_folder!r}")
        self.app = Flask(__name__, template_folder=template_folder)
        
        # Load configuration from config.py
        self.app.config.from_pyfile('config.py')

        sqlalchemy_database_uri = self.planexe_dotenv.get("SQLALCHEMY_DATABASE_URI")
        if sqlalchemy_database_uri is None:
            raise Exception(f"SQLALCHEMY_DATABASE_URI is not set in the .env file. Please set it in the .env file.")
        self.app.config['SQLALCHEMY_DATABASE_URI'] = sqlalchemy_database_uri
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle' : 280}
        
        # Initialize database
        from planexe_db_singleton import db
        self.db = db
        self.db.init_app(self.app)
        
        # Create database tables
        with self.app.app_context():
            self.db.create_all()
            
            # Add initial records if the table is empty
            if TaskItem.query.count() == 0:
                tasks = TaskItem.demo_items()
                for task in tasks:
                    self.db.session.add(task)
                self.db.session.commit()

            # Add initial records if the table is empty
            if EventItem.query.count() == 0:
                events = EventItem.demo_items()
                for event in events:
                    self.db.session.add(event)
                self.db.session.commit()

            # Add initial records if the table is empty
            if NonceItem.query.count() == 0:
                nonce_items = NonceItem.demo_items()
                for nonce_item in nonce_items:
                    self.db.session.add(nonce_item)
                self.db.session.commit()
        
        # Setup Flask-Login
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        self.login_manager.login_view = 'login'
        
        @self.login_manager.user_loader
        def load_user(user_id):
            if user_id == 'admin':
                return User(user_id)
            return None
        
        # Setup Flask-Admin
        self.admin = Admin(self.app, name='PlanExe Admin', template_mode='bootstrap3', index_view=MyAdminIndexView())
        
        # Add database tables to admin panel
        self.admin.add_view(TaskItemView(model=TaskItem, session=self.db.session, name="Task"))
        self.admin.add_view(ModelView(model=EventItem, session=self.db.session, name="Event"))
        self.admin.add_view(WorkerItemView(model=WorkerItem, session=self.db.session, name="Worker"))
        self.admin.add_view(NonceItemView(model=NonceItem, session=self.db.session, name="Nonce"))

        self._setup_routes()

        self._track_flask_app_started()

    def _track_flask_app_started(self):
        logger.info(f"MyFlaskApp._track_flask_app_started. Starting...")
        
        # Determine if this is the main process or reloader process
        is_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        is_debug_mode = self.app.debug if hasattr(self, 'app') else True
        
        event_context = {
            "pid": str(os.getpid()),
            "parent_pid": str(os.getppid()),
            "is_reloader_process": is_reloader,
            "is_debug_mode": is_debug_mode,
            "WERKZEUG_RUN_MAIN": os.environ.get('WERKZEUG_RUN_MAIN', 'not_set'),
            "python_executable": sys.executable,
            "command_line": ' '.join(sys.argv),
            "FLASK_ENV": os.environ.get('FLASK_ENV', 'not_set'),
            "FLASK_DEBUG": os.environ.get('FLASK_DEBUG', 'not_set')
        }
            
        with self.app.app_context():
            event = EventItem(
                event_type=EventType.GENERIC_EVENT,
                message="Flask app started",
                context=event_context
            )
            self.db.session.add(event)
            self.db.session.commit()
            
        logger.info(f"MyFlaskApp._track_flask_app_started. Logged {event_context!r}")

    def _start_check(self):
        # When the Flask app launches in debug mode it runs __init__ twice, so that the app can hot reload.
        # However there is this inconsistency.
        # 1st time, the os.environ is the original environment of the shell.
        # 2nd time, the os.environ is the original environment of the shell + the .env content.
        # If it was the same in both cases, it would be easier to reason about the environment variables.
        # On following hot reloads, the os.environ continues to be the original environment of the shell + the .env content.
        logger.info(f"MyFlaskApp._start_check. environment variables: {os.environ}")

        issue_count = 0
        if not self.path_to_python.exists():
            logger.error(f"The python executable does not exist at this point. However the python executable should exist: {self.path_to_python!r}")
            issue_count += 1
        if not self.planexe_project_root.exists():
            logger.error(f"The planexe_project_root does not exist at this point. However the planexe_project_root should exist: {self.planexe_project_root!r}")
            issue_count += 1
        if issue_count > 0:
            raise Exception(f"There are {issue_count} issues with the python executable and project root directory")

    def _create_job_internal(self, run_id: str, run_id_dir: Path) -> Tuple[Dict[str, Any], int]:
        """
        Internal logic for creating a job.
        Called by both the /jobs endpoint and other internal functions.
        job_data is the full dictionary that would have come from request.json
        """
        if not run_id:
            return {"error": "run_id is required"}, 400

        if run_id in self.jobs:
            return {"error": "run_id already exists"}, 409

        if not run_id_dir.exists():
            raise Exception(f"The run_id_dir directory is supposed to exist at this point. However no run_id_dir directory exists: {run_id_dir!r}")

        environment = os.environ.copy()
        environment[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_id_dir)
        environment[PipelineEnvironmentEnum.LLM_MODEL.value] = SPECIAL_AUTO_ID
        environment[PipelineEnvironmentEnum.SPEED_VS_DETAIL.value] = SpeedVsDetailEnum.ALL_DETAILS_BUT_SLOW.value

        # Create job state
        job = JobState(run_id=run_id, run_id_dir=run_id_dir, environment=environment)
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

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                    user = User("admin")
                    login_user(user)
                    return redirect(url_for('admin.index'))
                return 'Invalid credentials', 401
            return render_template('login.html')

        @self.app.route('/logout')
        @login_required
        def logout():
            logout_user()
            return redirect(url_for('index'))

        @self.app.route('/ping')
        @login_required
        def ping():
            return render_template('ping.html')

        @self.app.route('/ping/stream')
        @login_required
        def ping_stream():
            def generate():
                llm_names = get_llm_names_by_priority()

                for llm_name in llm_names:
                    # Send "pinging" status
                    yield f"data: {json.dumps({
                        'name': llm_name,
                        'status': 'pinging',
                        'response_time': 0,
                        'response': 'Pinging model…'
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
        @login_required
        def create_job():
            try:
                data = request.json
                run_id = generate_run_id(CONFIG.use_uuid_as_run_id)
                run_id_dir = (self.planexe_run_dir / run_id).absolute()
                response_data, status_code = self._create_job_internal(run_id, run_id_dir)
                return jsonify(response_data), status_code            
            except Exception as e:
                logger.error(f"Error creating job: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/jobs/stop_all", methods=["POST"])
        @login_required
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

        @self.app.route('/run', methods=['GET', 'POST'])
        @nocache
        def run():
            # When request.method is POST, and urlencoded parameters are detected, then return an error, so the developer can detect that something is wrong, the parameters in the url are supposed to be part for the form.
            if request.method == 'POST' and request.args:
                logger.error(f"endpoint /run. POST request with urlencoded parameters detected. This is not allowed. The url parameters are supposed to be part of the form.")
                return jsonify({"error": "POST request with urlencoded parameters detected. This is not allowed. The url parameters are supposed to be part of the form."}), 400

            # Obtain info about the request
            request_size_bytes: int = len(request.get_data())
            request_content_type: str = request.headers.get('Content-Type', '')

            # Gather the parameters from the request.form (POST) or request.args (GET)
            request_form_or_args = request.form if request.method == 'POST' else request.args
            prompt_param = request_form_or_args.get('prompt', '')
            user_id_param = request_form_or_args.get('user_id', '')
            nonce_param = request_form_or_args.get('nonce', '')
            parameters = {key: value for key, value in request_form_or_args.items()}

            # Remove the parameters that have already been extracted from the parameters dictionary
            parameters.pop('prompt', None)
            parameters.pop('user_id', None)
            parameters.pop('nonce', None)
            if len(parameters) == 0:
                parameters = None

            # Get length of prompt_param in bytes and in characters
            prompt_param_bytes = len(prompt_param.encode('utf-8'))
            prompt_param_characters = len(prompt_param)

            # Avoid flooding logs when the prompt is long.
            log_prompt_info = prompt_param[:100]
            if len(prompt_param) > 100:
                log_prompt_info += "... (truncated)"
            logger.info(f"endpoint /run ({request.method}). Size of request: {request_size_bytes} bytes. Starting run with parameters: prompt={log_prompt_info!r}, user_id={user_id_param!r}, nonce={nonce_param!r}, parameters={parameters!r}, prompt_param_bytes={prompt_param_bytes}, prompt_param_characters={prompt_param_characters}")

            if not nonce_param:
                logger.error(f"endpoint /run. No nonce provided")
                return jsonify({"error": "A unique request identifier (nonce) is required."}), 400

            with self.app.app_context():
                context = {
                    "user_agent": request.headers.get('User-Agent'),
                    "ip_address": request.remote_addr,
                    "prompt": prompt_param,
                    "user_id": user_id_param,
                }
                nonce_item, is_new = NonceItem.get_or_create(nonce_key=nonce_param, context=context)
                if not is_new:
                    logger.warning(f"endpoint /run. Replay detected for nonce '{nonce_param}'. Request count: {nonce_item.request_count}.")
                    return jsonify({"error": "This action has already been performed. Reusing this link is not permitted."}), 409

            if not prompt_param:
                logger.error(f"endpoint /run. No prompt provided")
                return jsonify({"error": "No prompt provided"}), 400
            
            if not user_id_param:
                logger.error(f"endpoint /run. No user_id provided")
                return jsonify({"error": "No user_id provided"}), 400

            with self.app.app_context():
                task = TaskItem(
                    state=TaskState.pending,
                    prompt=prompt_param,
                    progress_percentage=0.0,
                    progress_message="Awaiting server to start…",
                    user_id=user_id_param,
                    parameters=parameters
                )
                self.db.session.add(task)
                self.db.session.commit()
                task_id = task.id if hasattr(task, 'id') else None
                logger.info(f"endpoint /run. Task received: {task_id!r}")
                event_context = {
                    "task_id": str(task_id),
                    "request_size_bytes": request_size_bytes,
                    "request_content_type": request_content_type,
                    "prompt_param_bytes": prompt_param_bytes,
                    "prompt_param_characters": prompt_param_characters,
                    "prompt": prompt_param,
                    "user_id": user_id_param,
                    "parameters": parameters,
                    "method": request.method
                }
                event = EventItem(
                    event_type=EventType.TASK_PENDING,
                    message=f"Enqueued task via /run endpoint",
                    context=event_context
                )
                self.db.session.add(event)
                self.db.session.commit()
            return render_template('run_via_database.html', run_id=task_id)

        @self.app.route('/run_separate_process')
        @login_required
        def run_separate_process():
            prompt_param = request.args.get('prompt', '')
            user_id_param = request.args.get('user_id', '')

            # Ensure the string contain a-zA-Z0-9-_ so it's safe to use in filenames/database
            if not re.match(r'^[a-zA-Z0-9\-_]{1,80}$', user_id_param):
                logger.error(f"endpoint /run_separate_process. Invalid formatting for user_id. parameters: prompt={prompt_param}, user_id_param={user_id_param}")
                return jsonify({"error": "Invalid user_id"}), 400

            if user_id_param not in self.users:
                logger.error(f"endpoint /run_separate_process. No such user_id. parameters: prompt={prompt_param}, user_id_param={user_id_param}")
                return jsonify({"error": "Invalid user_id"}), 400

            logger.info(f"endpoint /run_separate_process. Starting run with parameters: prompt={prompt_param}, user_id_param={user_id_param}")

            current_user = self.users[user_id_param]
            if current_user.current_run_id is not None:
                logger.info(f"endpoint /run_separate_process. User {user_id_param} already has a current run_id. Stopping it first.")
                self.jobs[current_user.current_run_id].stop_event.set()
                current_user.current_run_id = None

            start_time: datetime = datetime.now().astimezone()

            run_id = generate_run_id(use_uuid=CONFIG.use_uuid_as_run_id, start_time=start_time)
            run_id_dir = (self.planexe_run_dir / run_id).absolute()

            logger.info(f"endpoint /run_separate_process. current working directory: {Path.cwd()}")
            logger.info(f"endpoint /run_separate_process. run_id: {run_id}")
            logger.info(f"endpoint /run_separate_process. run_id_dir: {run_id_dir!r}")

            if run_id_dir.exists():
                raise Exception(f"The run_id_dir is not supposed to exist at this point. However the run_id_dir already exists: {run_id_dir!r}")
            run_id_dir.mkdir(parents=True, exist_ok=True)

            # write the start time to the run_id_dir
            start_time_file = StartTime.create(local_time=start_time)
            start_time_file.save(str(run_id_dir / FilenameEnum.START_TIME.value))

            # Create the initial plan file.
            plan_file = PlanFile.create(vague_plan_description=prompt_param, start_time=start_time)
            plan_file.save(str(run_id_dir / FilenameEnum.INITIAL_PLAN.value))

            response_data, status_code = self._create_job_internal(run_id, run_id_dir)
            if status_code != 202:
                logger.error(f"Error creating job internally: {response_data}")
                return jsonify({"error": "Failed to create job", "details": response_data}), 500

            current_user.current_run_id = run_id

            logger.info(f"endpoint /run_separate_process. render_template. run_id={run_id} user_id={user_id_param}")

            return render_template('run_in_separate_process.html', user_id=user_id_param)

        @self.app.route('/progress_separate_process')
        @login_required
        def get_progress_separate_process():
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

        @self.app.route('/progress')
        def get_progress():
            run_id = request.args.get('run_id', '')
            logger.debug(f"Progress endpoint received run_id: {run_id!r}")
            # lookup the task in the database
            task = self.db.session.get(TaskItem, run_id)
            if task is None:
                logger.error(f"Task not found for run_id: {run_id!r}")
                return jsonify({"error": "Task not found"}), 400
            
            progress_percentage = float(task.progress_percentage) if task.progress_percentage is not None else 0.0
            progress_message = task.progress_message if task.progress_message is not None else ""
            if isinstance(task.state, TaskState):
                status = task.state.name
            else:
                status = f"unknown-{task.state}"

            # update the last_seen_timestamp
            try:
                task.last_seen_timestamp = datetime.now(UTC)
                self.db.session.commit()
            except Exception as e:
                logger.error(f"get_progress, error updating last_seen_timestamp for task {run_id!r}: {e}", exc_info=True)
                self.db.session.rollback()
                # ignore the error

            return jsonify({"progress_percentage": progress_percentage, "progress_message": progress_message, "status": status}), 200

        @self.app.route('/viewplan_separate_process')
        @login_required
        def viewplan_separate_process():
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

            run_id_dir = (self.planexe_run_dir / run_id).absolute()
            if not run_id_dir.exists():
                raise Exception(f"Run directory not found at {run_id_dir!r}. Please ensure the run directory exists before viewing the plan.")

            path_to_html_file = run_id_dir / FilenameEnum.REPORT.value
            if not path_to_html_file.exists():
                raise Exception(f"The html file does not exist at this point. However the html file should exist: {path_to_html_file!r}")
            return send_file(str(path_to_html_file), mimetype='text/html')

        @self.app.route('/viewplan')
        def viewplan():
            run_id = request.args.get('run_id', '')
            logger.info(f"Progress endpoint received run_id: {run_id!r}")
            # lookup the task in the database
            task = self.db.session.get(TaskItem, run_id)
            if task is None:
                logger.error(f"Task not found for run_id: {run_id!r}")
                return jsonify({"error": "Task not found"}), 400

            run_id = task.id
            if SHOW_DEMO_PLAN:
                run_id = '20250524_universal_manufacturing'

            logger.info(f"ViewPlan endpoint. run_id={run_id!r}")

            run_id_dir = (self.planexe_run_dir / str(run_id)).absolute()
            if not run_id_dir.exists():
                raise Exception(f"Run directory not found at {run_id_dir!r}. Please ensure the run directory exists before viewing the plan.")

            path_to_html_file = run_id_dir / FilenameEnum.REPORT.value
            if not path_to_html_file.exists():
                raise Exception(f"The html file does not exist at this point. However the html file should exist: {path_to_html_file!r}")
            return send_file(str(path_to_html_file), mimetype='text/html')

        @self.app.route('/demo_instant_run_in_separate_process')
        @login_required
        def demo_instant_run_in_separate_process():
            # Assign a uuid to the user, so their data belongs to the right user
            user_id = str(uuid.uuid4())
            user_state = UserState(user_id=user_id)
            self.users[user_id] = user_state

            prompt_uuid = DEMO_INSTANT_RUN_PROMPT_UUID
            prompt_item = self.prompt_catalog.find(prompt_uuid)
            if prompt_item is None:
                logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo_instant_run_in_separate_process")
                return "Error: Demo prompt configuration missing.", 500
            return render_template('demo_instant_run_in_separate_process.html', prompt=prompt_item.prompt, user_id=user_id)

        @self.app.route('/demo_instant_run_via_database_developer_method_get')
        def demo_instant_run_via_database_developer_method_get():
            user_id = 'USERIDPLACEHOLDER'
            nonce = 'DEMO_' + str(uuid.uuid4())

            prompt_uuid = DEMO_INSTANT_RUN_PROMPT_UUID
            prompt_item = self.prompt_catalog.find(prompt_uuid)
            if prompt_item is None:
                logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo_instant_run_via_database_developer_method_get")
                return "Error: Demo prompt configuration missing.", 500
            return render_template('demo_instant_run_via_database_developer_method_get.html', prompt=prompt_item.prompt, user_id=user_id, nonce=nonce)

        @self.app.route('/demo_instant_run_via_database_developer_method_post')
        def demo_instant_run_via_database_developer_method_post():
            user_id = 'USERIDPLACEHOLDER'
            nonce = 'DEMO_' + str(uuid.uuid4())

            prompt_uuid = DEMO_INSTANT_RUN_PROMPT_UUID
            prompt_item = self.prompt_catalog.find(prompt_uuid)
            if prompt_item is None:
                logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo_instant_run_via_database_developer_method_post")
                return "Error: Demo prompt configuration missing.", 500
            return render_template('demo_instant_run_via_database_developer_method_post.html', prompt=prompt_item.prompt, user_id=user_id, nonce=nonce)

        @self.app.route('/demo_instant_run_via_database_production_method_get')
        @login_required
        def demo_instant_run_via_database_production_method_get():
            user_id = 'USERIDPLACEHOLDER'
            nonce = 'DEMO_' + str(uuid.uuid4())

            prompt_uuid = DEMO_INSTANT_RUN_PROMPT_UUID
            prompt_item = self.prompt_catalog.find(prompt_uuid)
            if prompt_item is None:
                logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo_instant_run_via_database_production_method_get")
                return "Error: Demo prompt configuration missing.", 500
            return render_template('demo_instant_run_via_database_production_method_get.html', prompt=prompt_item.prompt, user_id=user_id, nonce=nonce)

        @self.app.route('/demo_instant_run_via_database_production_method_post')
        @login_required
        def demo_instant_run_via_database_production_method_post():
            user_id = 'USERIDPLACEHOLDER'
            nonce = 'DEMO_' + str(uuid.uuid4())

            prompt_uuid = DEMO_INSTANT_RUN_PROMPT_UUID
            prompt_item = self.prompt_catalog.find(prompt_uuid)
            if prompt_item is None:
                logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo_instant_run_via_database_production_method_post")
                return "Error: Demo prompt configuration missing.", 500
            return render_template('demo_instant_run_via_database_production_method_post.html', prompt=prompt_item.prompt, user_id=user_id, nonce=nonce)

        @self.app.route('/demo_form_run_in_separate_process')
        @login_required
        def demo_form_run_in_separate_process():
            # Assign a uuid to the user, so their data belongs to the right user
            user_id = str(uuid.uuid4())
            user_state = UserState(user_id=user_id)
            self.users[user_id] = user_state

            # The prompts to be shown on the page.
            prompts = []
            for prompt_uuid in DEMO_FORM_RUN_PROMPT_UUIDS:
                prompt_item = self.prompt_catalog.find(prompt_uuid)
                if prompt_item is None:
                    logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo_form_run_in_separate_process")
                    return "Error: Demo prompt configuration missing.", 500
                prompts.append(prompt_item.prompt)

            return render_template('demo_form_run_in_separate_process.html', user_id=user_id, prompts=prompts)

        @self.app.route('/demo_form_run_via_database_method_get')
        @login_required
        def demo_form_run_via_database_method_get():
            user_id = 'USERIDPLACEHOLDER'
            nonce = 'DEMO_' + str(uuid.uuid4())

            # The prompts to be shown on the page.
            prompts = []
            for prompt_uuid in DEMO_FORM_RUN_PROMPT_UUIDS:
                prompt_item = self.prompt_catalog.find(prompt_uuid)
                if prompt_item is None:
                    logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo_form_run_via_database_method_get")
                    return "Error: Demo prompt configuration missing.", 500
                prompts.append(prompt_item.prompt)

            return render_template('demo_form_run_via_database_method_get.html', user_id=user_id, prompts=prompts, nonce=nonce)

        @self.app.route('/demo_form_run_via_database_method_post')
        @login_required
        def demo_form_run_via_database_method_post():
            user_id = 'USERIDPLACEHOLDER'
            nonce = 'DEMO_' + str(uuid.uuid4())

            # The prompts to be shown on the page.
            prompts = []
            for prompt_uuid in DEMO_FORM_RUN_PROMPT_UUIDS:
                prompt_item = self.prompt_catalog.find(prompt_uuid)
                if prompt_item is None:
                    logger.error(f"Prompt item not found for uuid: {prompt_uuid} in demo_form_run_via_database_method_post")
                    return "Error: Demo prompt configuration missing.", 500
                prompts.append(prompt_item.prompt)

            return render_template('demo_form_run_via_database_method_post.html', user_id=user_id, prompts=prompts, nonce=nonce)

        @self.app.route('/demo_subprocess_run_simple')
        @login_required
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
        @login_required
        def demo_subprocess_run_medium():
            topic = 'subprocess.run with python pinging OpenRouter'
            template = 'check_is_working.html'
            try:
                env = os.environ.copy()
                logger.info(f"demo_subprocess_run_medium. planexe_dotenv: {self.planexe_dotenv!r}")
                logger.info(f"demo_subprocess_run_medium. planexe_project_root: {self.planexe_project_root!r}")
                logger.info(f"demo_subprocess_run_medium. path_to_python: {self.path_to_python!r}")
                env["OPENROUTER_API_KEY"] = self.planexe_dotenv.get("OPENROUTER_API_KEY")
                result = subprocess.run(
                    [str(self.path_to_python), "-m", "planexe.proof_of_concepts.run_ping_simple"],
                    capture_output=True,
                    text=True,
                    check=True,
                    env=env,
                    cwd=str(self.planexe_project_root)
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
        @login_required
        def demo_subprocess_run_advanced():
            topic = 'subprocess.run with python pinging OpenRouter. Uses LlamaIndex.'
            template = 'check_is_working.html'
            try:
                env = os.environ.copy()
                logger.info(f"demo_subprocess_run_advanced. planexe_dotenv: {self.planexe_dotenv!r}")
                logger.info(f"demo_subprocess_run_advanced. planexe_project_root: {self.planexe_project_root!r}")
                logger.info(f"demo_subprocess_run_advanced. path_to_python: {self.path_to_python!r}")
                env["OPENROUTER_API_KEY"] = self.planexe_dotenv.get("OPENROUTER_API_KEY")
                result = subprocess.run(
                    [str(self.path_to_python), "-m", "planexe.proof_of_concepts.run_ping_medium"],
                    capture_output=True,
                    text=True,
                    check=True,
                    env=env,
                    cwd=str(self.planexe_project_root)
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
        @login_required
        def demo_eventsource():
            return render_template('demo_eventsource.html')

        @self.app.route('/demo_eventsource/stream')
        @login_required
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

        @self.app.route('/troubleshoot_truncation_echo', methods=['POST'])
        @nocache
        def troubleshoot_truncation_echo():
            """Echo endpoint to test parameter truncation. Returns JSON with parameter's echoed values."""
            try:
                # Gather the parameters from the request.form (POST) or JSON
                if request.is_json:
                    request_data = request.get_json()
                    if request_data is None:
                        logger.error(f"endpoint /troubleshoot_truncation_echo. Invalid JSON data received")
                        return jsonify({"error": "Invalid JSON data"}), 400
                    parameters = request_data
                else:
                    # Handle form data
                    request_form = request.form
                    parameters = {key: value for key, value in request_form.items()}
                
                # Calculate lengths for all parameters
                result_byte_length = {}
                result_echo = {}
                
                # Copy all parameters to result_echo first
                result_echo = parameters.copy()
                
                # Only process string values for byte length calculation
                for key, value in parameters.items():
                    if not isinstance(value, str):
                        continue
                    
                    # Calculate byte length using UTF-8 encoding, handling invalid surrogates
                    try:
                        byte_length = len(value.encode('utf-8'))
                    except UnicodeEncodeError as e:
                        # Handle invalid surrogate characters by replacing them
                        logger.warning(f"Invalid surrogate character detected in parameter {key}: {e}")
                        safe_value = value.encode('utf-8', errors='replace').decode('utf-8')
                        byte_length = len(safe_value.encode('utf-8'))
                        result_echo[key] = safe_value
                    
                    should_override = False
                    range_start = 4000
                    range_end = 9000
                    override_value = 1234
                    if should_override and byte_length >= range_start and byte_length <= range_end:
                        logger.info(f"endpoint /troubleshoot_truncation_echo. Parameter {key} is between {range_start} and {range_end} bytes. Simulating truncation by truncating content to {override_value} bytes.")
                        byte_length = override_value
                        result_echo[key] = value[:byte_length]

                    result_byte_length[key] = byte_length
                
                logger.info(f"endpoint /troubleshoot_truncation_echo. Parameter lengths: {result_byte_length}")
                return jsonify(result_echo), 200
                
            except Exception as e:
                logger.error(f"Error in troubleshoot_truncation_echo: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route('/troubleshoot_truncation', methods=['GET'])
        @nocache
        def troubleshoot_truncation():
            """UI endpoint to test if form/json parameters gets truncated around 4000 bytes by the server. However no truncation was detected. The test is done by gradually increasing content length."""
            return render_template('troubleshoot_truncation.html')

    def _run_job(self, job: JobState):
        """Run the actual job in a subprocess"""
        
        try:
            run_id_dir = job.run_id_dir
            if not run_id_dir.exists():
                raise Exception(f"The run_id_dir directory is supposed to exist at this point. However the output directory does not exist: {run_id_dir!r}")

            # Start the process
            command = [str(self.path_to_python), "-m", MODULE_PATH_PIPELINE]
            logger.info(f"_run_job. subprocess.Popen before command: {command!r}")
            logger.info(f"_run_job. CWD for subprocess: {self.planexe_project_root!r}")
            logger.info(f"_run_job. Environment keys for subprocess (sample): "
                        f"RUN_ID_DIR={job.environment.get(PipelineEnvironmentEnum.RUN_ID_DIR.value)!r}")

            job.process = subprocess.Popen(
                command,
                cwd=str(self.planexe_project_root),
                env=job.environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
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
                    if run_id_dir.exists() and run_id_dir.is_dir():
                        files = [f.name for f in run_id_dir.iterdir()]
                except OSError as e:
                    logger.warning(f"_run_job: Could not list files in {run_id_dir}: {e}")

                ignore_files = [
                    ExtraFilenameEnum.EXPECTED_FILENAMES1_JSON.value,
                    ExtraFilenameEnum.LOG_TXT.value
                ]
                files = [f for f in files if f not in ignore_files]
                # logger.debug(f"Files in run_id_dir for {job.run_id}: {files}") # Debug, can be noisy
                number_of_files = len(files)
                # logger.debug(f"Number of files in run_id_dir for {job.run_id}: {number_of_files}") # Debug

                # Determine the progress, by comparing the generated files with the expected_filenames1.json
                expected_filenames_path = run_id_dir / ExtraFilenameEnum.EXPECTED_FILENAMES1_JSON.value
                assign_progress_message = f"File count: {number_of_files}"
                assign_progress_percentage = 0
                if expected_filenames_path.exists():
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
        level=logging.DEBUG, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(threadName)s - %(message)s'
    )
    flask_app_instance = MyFlaskApp()
    flask_app_instance.run_server(debug=True)