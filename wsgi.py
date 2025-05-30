import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Get the absolute path of the current directory
project_home = os.path.dirname(os.path.abspath(__file__))
logger.debug(f"Project home: {project_home}")

if project_home not in sys.path:
    sys.path = [project_home] + sys.path
    logger.debug(f"Updated sys.path: {sys.path}")

# Debug llama_index installation
try:
    import llama_index
    logger.debug(f"llama_index version: {llama_index.__version__}")
    logger.debug(f"llama_index path: {llama_index.__file__}")
except ImportError as e:
    logger.error(f"Failed to import llama_index: {e}")
    # List all installed packages
    import pkg_resources
    installed_packages = [f"{dist.key} {dist.version}" for dist in pkg_resources.working_set]
    logger.debug("Installed packages:")
    for package in installed_packages:
        logger.debug(package)

# Import the Flask app
logger.debug("Attempting to import MyFlaskApp...")
from src.ui_flask.app import MyFlaskApp
logger.debug("Successfully imported MyFlaskApp")

# Create the application instance
logger.debug("Creating MyFlaskApp instance...")
app = MyFlaskApp()
logger.debug("Successfully created MyFlaskApp instance")

# Enable debug mode
app.app.debug = True
logger.debug("Debug mode enabled")

# This is the variable that PythonAnywhere will look for
application = app
logger.debug("WSGI application configured") 