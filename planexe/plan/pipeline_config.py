"""
Global configuration for the PlanExe pipeline.
"""
from dataclasses import dataclass

@dataclass(slots=True)
class PipelineConfig:
    """Runtime-mutable settings for the PlanExe pipeline."""
    enable_csv_export: bool = False

PIPELINE_CONFIG = PipelineConfig()
