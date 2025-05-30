from enum import Enum
from dataclasses import dataclass
import os
from typing import Optional

class PipelineEnvironmentEnum(Enum):
    """Enum for environment variable names used in the pipeline."""
    RUN_ID = "RUN_ID"
    LLM_MODEL = "LLM_MODEL"
    SPEED_VS_DETAIL = "SPEED_VS_DETAIL"

@dataclass
class PipelineEnvironment:
    """Dataclass to hold environment variable values."""
    run_id: Optional[str] = None
    llm_model: Optional[str] = None
    speed_vs_detail: Optional[str] = None

    @classmethod
    def from_env(cls) -> "PipelineEnvironment":
        """Create an PipelineEnvironment instance from environment variables."""
        return cls(
            run_id=os.environ.get(PipelineEnvironmentEnum.RUN_ID.value),
            llm_model=os.environ.get(PipelineEnvironmentEnum.LLM_MODEL.value),
            speed_vs_detail=os.environ.get(PipelineEnvironmentEnum.SPEED_VS_DETAIL.value)
        )
