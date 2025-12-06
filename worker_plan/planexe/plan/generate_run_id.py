"""Shim to keep existing imports working."""

from worker_plan_api.generate_run_id import RUN_ID_PREFIX, generate_run_id

__all__ = ["RUN_ID_PREFIX", "generate_run_id"]
