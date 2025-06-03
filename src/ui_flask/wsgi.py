import sys
import os
import logging

print("----- WSGI SCRIPT IS BEING ACCESSED -----", file=sys.stderr)

# Configure logging VERY EARLY - this might help catch early issues
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG) # Log to stderr
logger = logging.getLogger(__name__)

logger.debug("WSGI file loading...")

# Get the absolute path of the current directory
project_home = os.path.dirname(os.path.abspath(__file__), "..", "..")
logger.debug(f"Project home: {project_home}")

if project_home not in sys.path:
    sys.path.insert(0, project_home)
    logger.debug(f"Updated sys.path: {sys.path}")

logger.debug("Attempting to import MyFlaskApp...")
try:
    logger.info("Importing MyFlaskApp...")
    from src.ui_flask.app import MyFlaskApp
    logger.info("Creating MyFlaskApp instance...")
    my_flask_app_wrapper = MyFlaskApp()
    logger.info("Successfully created MyFlaskApp instance")
    app = my_flask_app_wrapper.app
    logger.info("Successfully set 'app' variable")
except Exception as e:
    logger.error(f"CRITICAL ERROR IN WSGI FILE: {e}", exc_info=True)
    raise
