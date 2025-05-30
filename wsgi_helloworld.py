import sys

project_home = '/home/neoneye/git/PlanExe'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

from src.ui_flask.app2 import app

# This is the variable that PythonAnywhere will look for
application = app 