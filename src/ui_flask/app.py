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

logger = logging.getLogger(__name__)

MODULE_PATH_PIPELINE = "src.plan.run_plan_pipeline"

@dataclass
class JobState:
    """State for a single job"""
    job_id: str
    process: Optional[subprocess.Popen] = None
    stop_event: threading.Event = threading.Event()
    status: str = "pending"
    output_dir: Optional[str] = None
    error: Optional[str] = None

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
        self._setup_routes()

    def _create_job_internal(self, job_id: str, job_data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Internal logic for creating a job.
        Called by both the /jobs endpoint and other internal functions.
        job_data is the full dictionary that would have come from request.json
        """
        if not job_id:
            return {"error": "job_id is required"}, 400

        if job_id in self.jobs:
            return {"error": "job_id already exists"}, 409

        # Create job state
        job = JobState(job_id=job_id)
        self.jobs[job_id] = job

        # Start the job in a background thread
        # Pass the full job_data dict as _run_job expects it
        threading.Thread(target=self._run_job, args=(job, job_data)).start()

        return {
            "job_id": job_id,
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
                job_id = data.get("job_id")
                response_data, status_code = self._create_job_internal(job_id, data)
                return jsonify(response_data), status_code            
            except Exception as e:
                logger.error(f"Error creating job: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route('/run')
        def run():
            prompt_param = request.args.get('prompt', '')
            uuid_param = request.args.get('uuid', '')
            logger.info(f"Run endpoint. parameters: prompt={prompt_param}, uuid={uuid_param}")

            # Check if it's string containing a-zA-Z0-9-_ so it can be used in a file name
            if not re.match(r'^[a-zA-Z0-9\-_]{1,80}$', uuid_param):
                return jsonify({"error": "Invalid UUID"}), 400

            job_payload = {"job_id": uuid_param}

            response_data, status_code = self._create_job_internal(uuid_param, job_payload)
            if status_code != 202:
                logger.error(f"Error creating job internally: {response_data}")
                return jsonify({"error": "Failed to create job", "details": response_data}), 500

            return render_template('run.html', prompt=prompt_param, uuid=uuid_param)

        @self.app.route('/progress')
        def get_progress():
            uuid = request.args.get('uuid', '')
            logger.info(f"Progress endpoint received UUID: {uuid}")
            self.uuid_to_progress[uuid] = 0
            
            def generate():
                while True:
                    # Send the current progress value
                    progress = self.uuid_to_progress[uuid]
                    done = progress == len(self.MESSAGES) - 1
                    data = json.dumps({'progress': self.MESSAGES[progress], 'done': done})
                    yield f"data: {data}\n\n"
                    time.sleep(1)
                    self.uuid_to_progress[uuid] = (progress + 1) % len(self.MESSAGES)
                    if done:
                        logger.info(f"Progress endpoint received UUID: {uuid} is done")
                        del self.uuid_to_progress[uuid]
                        break

            return Response(generate(), mimetype='text/event-stream')

        @self.app.route('/viewplan')
        def viewplan():
            uuid_param = request.args.get('uuid', '')
            logger.info(f"ViewPlan endpoint. uuid={uuid_param}")
            return render_template('viewplan.html', uuid=uuid_param)

        @self.app.route('/demo1')
        def demo1():
            return render_template('demo1.html')

        @self.app.route('/demo2')
        def demo2():
            # Assign a uuid to the user, so their data belongs to the right user
            session_uuid = str(uuid.uuid4())
            return render_template('demo2.html', uuid=session_uuid)

    def _run_job(self, job: JobState, data: dict):
        """Run the actual job in a subprocess"""
        try:
            # Set up environment variables
            env = os.environ.copy()
            env.update(data.get("env", {}))

            # Create output directory
            output_dir = os.path.join("run", job.job_id)
            os.makedirs(output_dir, exist_ok=True)
            job.output_dir = output_dir

            # Start the process
            command = [sys.executable, "-m", MODULE_PATH_PIPELINE]
            job.process = subprocess.Popen(
                command,
                cwd=".",
                env=env,
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

                time.sleep(1)

        except Exception as e:
            logger.error(f"Error running job: {e}")
            job.status = "failed"
            job.error = str(e)

    def run(self, debug=True):
        self.app.run(debug=debug)

if __name__ == '__main__':
    app = MyFlaskApp()
    app.run(debug=True) 