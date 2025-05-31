print("----- WSGI SCRIPT IS BEING ACCESSED -----", file=sys.stderr)

import sys
import os
import logging

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
    # ADJUST THIS IMPORT PATH BASED ON YOUR ACTUAL FILE STRUCTURE
    # Assuming wsgi.py is in the root and app.py is in src/ui_flask/
    from src.ui_flask.app import MyFlaskApp
    logger.debug("Successfully imported MyFlaskApp")

    logger.debug("Creating MyFlaskApp instance...")
    my_flask_app_wrapper = MyFlaskApp()
    logger.debug("Successfully created MyFlaskApp instance")

    # This is the variable that PythonAnywhere will look for
    application = my_flask_app_wrapper.app # CRITICAL: it must be the Flask app instance
    logger.debug("WSGI 'application' configured with Flask app instance")
    app = application
    logger.debug("WSGI 'app' configured with Flask app instance")

except Exception as e:
    logger.error(f"CRITICAL ERROR IN WSGI FILE: {e}", exc_info=True)
    # If you have an error here, the 'application' object might not be set,
    # and uWSGI will fail silently from the perspective of your error.log
    # This error *should* go to stderr, which PythonAnywhere *should* capture.
    raise # Re-raise the exception to make sure it's visible if possible