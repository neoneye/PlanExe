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
from flask import Flask, render_template, Response, request, jsonify
from src.plan.generate_run_id import generate_run_id
from src.plan.plan_file import PlanFile
from src.plan.filenames import FilenameEnum
from src.prompt.prompt_catalog import PromptCatalog

logger = logging.getLogger(__name__)

MODULE_PATH_PIPELINE = "src.plan.run_plan_pipeline"
RUN_DIR = "run"

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

@dataclass
class JobState:
    """State for a single job"""
    run_id: str
    run_path: str
    environment: Dict[str, str]
    process: Optional[subprocess.Popen] = None
    stop_event: threading.Event = threading.Event()
    status: str = "pending"
    error: Optional[str] = None
    progress_message: str = ""

class MyFlaskApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.jobs: Dict[str, JobState] = {}
        self.uuid_to_progress = {}
        self.MESSAGES = [
            "step 1: initializing",
            "step 2: loading data",
            "step 3: processing data",
            "step 4: analyzing data",
            "step 5: generating report",
            "step 6: completing task",
            "step 7: saving results",
        ]

        # Load prompt catalog and examples.
        self.prompt_catalog = PromptCatalog()
        self.prompt_catalog.load_simple_plan_prompts()

        self._setup_routes()

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
        environment["RUN_ID"] = run_id
        environment["LLM_MODEL"] = "openrouter-paid-gemini-2.0-flash-001"
        environment["SPEED_VS_DETAIL"] = "fast"

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

        @self.app.route("/jobs", methods=["POST"])
        def create_job():
            try:
                data = request.json
                run_id = generate_run_id(CONFIG.use_uuid_as_run_id)
                run_path = os.path.join(RUN_DIR, run_id)
                absolute_path_to_run_dir = os.path.abspath(run_path)
                response_data, status_code = self._create_job_internal(run_id, absolute_path_to_run_dir)
                return jsonify(response_data), status_code            
            except Exception as e:
                logger.error(f"Error creating job: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route('/run')
        def run():
            prompt_param = request.args.get('prompt', '')
            user_id_param = request.args.get('user_id', '')
            logger.info(f"Run endpoint. parameters: prompt={prompt_param}, user_id_param={user_id_param}")

            # Ensure the string contain a-zA-Z0-9-_ so it's safe to use in filenames/database
            if not re.match(r'^[a-zA-Z0-9\-_]{1,80}$', user_id_param):
                return jsonify({"error": "Invalid user_id"}), 400

            run_id = generate_run_id(CONFIG.use_uuid_as_run_id)
            run_path = os.path.join(RUN_DIR, run_id)
            absolute_path_to_run_dir = os.path.abspath(run_path)

            if os.path.exists(run_path):
                raise Exception(f"The run path is not supposed to exist at this point. However the run path already exists: {run_path}")
            os.makedirs(run_path)

            # Create the initial plan file.
            plan_file = PlanFile.create(prompt_param)
            plan_file.save(os.path.join(run_path, FilenameEnum.INITIAL_PLAN.value))

            response_data, status_code = self._create_job_internal(run_id, absolute_path_to_run_dir)
            if status_code != 202:
                logger.error(f"Error creating job internally: {response_data}")
                return jsonify({"error": "Failed to create job", "details": response_data}), 500

            return render_template('run.html', prompt=prompt_param, user_id=user_id_param)

        @self.app.route('/progress')
        def get_progress():
            user_id = request.args.get('user_id', '')
            logger.info(f"Progress endpoint received user_id: {user_id}")
            self.uuid_to_progress[user_id] = 0
            
            def generate():
                while True:
                    # Send the current progress value
                    progress = self.uuid_to_progress[user_id]
                    done = progress == len(self.MESSAGES) - 1
                    data = json.dumps({'progress': self.MESSAGES[progress], 'done': done})
                    yield f"data: {data}\n\n"
                    time.sleep(1)
                    self.uuid_to_progress[user_id] = (progress + 1) % len(self.MESSAGES)
                    if done:
                        logger.info(f"Progress endpoint received user_id: {user_id} is done")
                        del self.uuid_to_progress[user_id]
                        break

            return Response(generate(), mimetype='text/event-stream')

        @self.app.route('/viewplan')
        def viewplan():
            user_id_param = request.args.get('user_id', '')
            logger.info(f"ViewPlan endpoint. user_id={user_id_param}")
            return render_template('viewplan.html', user_id=user_id_param)

        @self.app.route('/demo1')
        def demo1():
            prompt_uuid = DEMO1_PROMPT_UUID
            prompt_item = self.prompt_catalog.find(prompt_uuid)
            if prompt_item is None:
                raise Exception(f"Prompt item not found for uuid: {prompt_uuid}")
            return render_template('demo1.html', prompt=prompt_item.prompt)

        @self.app.route('/demo2')
        def demo2():
            # Assign a uuid to the user, so their data belongs to the right user
            user_id = str(uuid.uuid4())

            # The prompts to be shown on the page.
            prompts = []
            for prompt_uuid in DEMO2_PROMPT_UUIDS:
                prompt_item = self.prompt_catalog.find(prompt_uuid)
                if prompt_item is None:
                    raise Exception(f"Prompt item not found for uuid: {prompt_uuid}")
                prompts.append(prompt_item.prompt)

            return render_template('demo2.html', user_id=user_id, prompts=prompts)

    def _run_job(self, job: JobState):
        """Run the actual job in a subprocess"""
        try:
            run_path = job.run_path
            if not os.path.exists(run_path):
                raise Exception(f"The run_path directory is supposed to exist at this point. However the output directory does not exist: {run_path}")

            # Start the process
            command = [sys.executable, "-m", MODULE_PATH_PIPELINE]
            job.process = subprocess.Popen(
                command,
                cwd=".",
                env=job.environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            job.status = "running"

            # Monitor the process
            while True:
                if job.stop_event.is_set():
                    job.process.terminate()
                    job.status = "cancelled"
                    break

                if job.process.poll() is not None:
                    if job.process.returncode == 0:
                        job.status = "completed"
                    else:
                        job.status = "failed"
                        job.error = f"Process exited with code {job.process.returncode}"
                    break

                # obtain list of files in the run_path directory
                files = os.listdir(run_path)
                logger.info(f"Files in run_path: {files}")
                number_of_files = len(files)
                logger.info(f"Number of files in run_path: {number_of_files}")
                job.progress_message = f"File count: {files}"

                time.sleep(1)

        except Exception as e:
            logger.error(f"Error running job: {e}")
            job.status = "failed"
            job.error = str(e)

    def run(self, debug=True):
        self.app.run(debug=debug)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    app = MyFlaskApp()
    app.run(debug=True) 