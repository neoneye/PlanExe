"""
Run all tests in the current directory and subdirs.
PROMPT> python test.py

Behavior:
- If not already running with the worker_plan venv (preferred) or frontend_single_user venv, re-executes itself with the first one found so project deps are available.
- Keeps cwd at repo root and adds worker_plan to PYTHONPATH so worker_plan_internal/worker_plan_api imports resolve without extra setup.
- Then discovers and runs all test_*.py under the repo once.
"""
import os
import subprocess
import sys
from pathlib import Path
import logging
import unittest

# If we're not already using the worker_plan virtualenv, re-exec into it (fallback to frontend_single_user if worker venv is missing).
PROJECT_ROOT = Path(__file__).resolve().parent
_RERUN_ENV = "PLANEXE_TEST_RERUN"
if os.environ.get(_RERUN_ENV) != "1":
    worker_python = PROJECT_ROOT / "worker_plan" / ".venv" / "bin" / "python"
    frontend_python = PROJECT_ROOT / "frontend_single_user" / ".venv" / "bin" / "python"
    current_python = Path(sys.executable).resolve()
    worker_resolved = worker_python.resolve() if worker_python.is_file() else None
    target_python = worker_python if worker_python.is_file() else (frontend_python if frontend_python.is_file() else None)

    if target_python is None:
        sys.stderr.write(
            "No project virtualenv found. Please create one:\n"
            "  cd worker_plan && python3.13 -m venv .venv && source .venv/bin/activate && pip install -e .\n"
        )
        sys.exit(1)

    if worker_resolved is None or current_python != worker_resolved:
        env = os.environ.copy()
        env[_RERUN_ENV] = "1"
        extra_paths = [str(PROJECT_ROOT / "worker_plan")]
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = os.pathsep.join(extra_paths + ([existing] if existing else []))
        print(f"Re-running tests with venv interpreter: {target_python}", file=sys.stderr)
        subprocess.check_call([str(target_python), __file__], env=env, cwd=str(PROJECT_ROOT))
        sys.exit(0)

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
