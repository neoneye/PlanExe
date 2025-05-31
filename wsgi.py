import sys
import os
import logging

print("----- WSGI SCRIPT IS BEING ACCESSED -----", file=sys.stderr)

# Configure logging VERY EARLY - this might help catch early issues
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG) # Log to stderr
logger = logging.getLogger(__name__)

logger.debug("WSGI file loading...")

# Get the absolute path of the current directory
project_home = os.path.dirname(os.path.abspath(__file__))
logger.debug(f"Project home: {project_home}")

if project_home not in sys.path:
    sys.path.insert(0, project_home) # Use insert(0, ...) for higher precedence
    logger.debug(f"Updated sys.path: {sys.path}")

# Make sure this import is correct for your project structure
# If app.py is in src/ui_flask/app.py relative to project_home:
# from src.ui_flask.app import MyFlaskApp
# If app.py is in the same directory as wsgi.py:
# from app import MyFlaskApp

logger.debug("Attempting to import MyFlaskApp...")
try:
    # from src.ui_flask.app import MyFlaskApp # Comment this out temporarily
    logger.info("SKIPPING MyFlaskApp import for bus error test") # Add this
    # application = None # Temporarily set application to None or a dummy
except Exception as e:
    logger.error(f"CRITICAL ERROR IN WSGI FILE: {e}", exc_info=True)
    raise
