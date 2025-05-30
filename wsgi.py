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
    logger.debug(f"llama_index path: {llama_index.__file__}")
    
    # Try to import the specific module that's failing
    try:
        from llama_index.core.llms.llm import LLM
        logger.debug("Successfully imported LLM from llama_index.core.llms.llm")
    except ImportError as e:
        logger.error(f"Failed to import LLM: {e}")
        logger.debug("Trying to list available modules in llama_index:")
        import inspect
        for name, obj in inspect.getmembers(llama_index):
            if not name.startswith('_'):  # Skip private members
                logger.debug(f"  {name}: {type(obj)}")
    
except ImportError as e:
    logger.error(f"Failed to import llama_index: {e}")

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