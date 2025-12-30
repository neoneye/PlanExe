"""Shim to keep existing imports working."""

from worker_plan_api.prompt_catalog import PromptCatalog, PromptItem

__all__ = ["PromptCatalog", "PromptItem"]
