import sys

project_home = '/home/neoneye/git/PlanExe'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Import the Flask app
from src.ui_flask.app import MyFlaskApp

# Create the application instance
app = MyFlaskApp()

# This is the variable that PythonAnywhere will look for
application = app 