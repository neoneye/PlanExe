import logging
import time
import json
import uuid
from flask import Flask, render_template, Response, request

logger = logging.getLogger(__name__)

class MyFlaskApp:
    def __init__(self):
        self.app = Flask(__name__)
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

    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/developer')
        def developer():
            return render_template('developer.html')

        @self.app.route('/run')
        def run():
            prompt_param = request.args.get('prompt', '')
            uuid_param = request.args.get('uuid', '')
            print(f"Run endpoint. parameters: prompt={prompt_param}, uuid={uuid_param}")
            return render_template('run.html', prompt=prompt_param, uuid=uuid_param)

        @self.app.route('/progress')
        def get_progress():
            uuid = request.args.get('uuid', '')
            print(f"Progress endpoint received UUID: {uuid}")
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
                        print(f"Progress endpoint received UUID: {uuid} is done")
                        del self.uuid_to_progress[uuid]
                        break

            return Response(generate(), mimetype='text/event-stream')

        @self.app.route('/viewplan')
        def viewplan():
            uuid_param = request.args.get('uuid', '')
            print(f"ViewPlan endpoint. uuid={uuid_param}")
            return render_template('viewplan.html', uuid=uuid_param)

        @self.app.route('/demo1')
        def demo1():
            return render_template('demo1.html')

        @self.app.route('/demo2')
        def demo2():
            # Assign a uuid to the user, so their data belongs to the right user
            session_uuid = str(uuid.uuid4())
            return render_template('demo2.html', uuid=session_uuid)

    def run(self, debug=True):
        self.app.run(debug=debug)

if __name__ == '__main__':
    app = MyFlaskApp()
    app.run(debug=True) 