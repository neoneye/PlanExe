"""
Run all tests in the current directory and subdirs.
PROMPT> python test.py
"""
import logging
import unittest

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
loader = unittest.TestLoader()
tests = loader.discover(pattern="test_*.py", start_dir=".")
runner = unittest.TextTestRunner(buffer=False)
runner.run(tests)
