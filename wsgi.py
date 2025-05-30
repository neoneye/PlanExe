import sys
import os

# Add the project root directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask app
from src.ui_flask.app import MyFlaskApp

# Create the application instance
app = MyFlaskApp()

# This is the variable that PythonAnywhere will look for
application = app 