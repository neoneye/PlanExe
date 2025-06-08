from enum import Enum
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

class PipelineEnvironmentEnum(Enum):
    """Enum for environment variable names used in the pipeline."""
    RUN_ID_DIR = "RUN_ID_DIR"
    LLM_MODEL = "LLM_MODEL"
    SPEED_VS_DETAIL = "SPEED_VS_DETAIL"

@dataclass
class PipelineEnvironment:
    """Dataclass to hold environment variable values."""
    run_id_dir: Optional[str] = None
    llm_model: Optional[str] = None
    speed_vs_detail: Optional[str] = None

    @classmethod
    def from_env(cls) -> "PipelineEnvironment":
        """Create an PipelineEnvironment instance from environment variables."""
        return cls(
            run_id_dir=os.environ.get(PipelineEnvironmentEnum.RUN_ID_DIR.value),
            llm_model=os.environ.get(PipelineEnvironmentEnum.LLM_MODEL.value),
            speed_vs_detail=os.environ.get(PipelineEnvironmentEnum.SPEED_VS_DETAIL.value)
        )
    
    def get_run_id_dir(self) -> Path:
        """Get the run_id_dir.
        
        Returns:
            Path: The absolute path to the run directory.
            
        Raises:
            ValueError: If run_id_dir is None, not an absolute path, or not a directory.
        """
        if self.run_id_dir is None:
            raise ValueError("run_id_dir is not set")
            
        path = Path(self.run_id_dir)
        if not path.is_absolute():
            raise ValueError(f"run_id_dir must be an absolute path, got: {self.run_id_dir}")
            
        if not path.is_dir():
            raise ValueError(f"run_id_dir must be a directory, got: {self.run_id_dir}")
            
        return path
