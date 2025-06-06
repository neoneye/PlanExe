"""
Load PlanExe's .env file, containing secrets such as API keys, like: OPENROUTER_API_KEY.

PROMPT> python -m planexe.utils.planexe_dotenv
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import dotenv_values
from planexe.utils.planexe_config import PlanExeConfig, PlanExeConfigError

@dataclass
class PlanExeDotEnv:
    dotenv_path: Path
    dotenv_dict: dict[str, str]

    @classmethod
    def load(cls):
        config = PlanExeConfig.load()
        if config.dotenv_path is None:
            raise PlanExeConfigError("Required configuration file '.env' was not found. Cannot create a PlanExeDotEnv instance.")
        dotenv_path = config.dotenv_path
        dotenv_dict = dotenv_values(dotenv_path=dotenv_path)
        return cls(
            dotenv_path=dotenv_path, 
            dotenv_dict=dotenv_dict
        )

    def get(self, key: str) -> Optional[str]:
        return self.dotenv_dict.get(key)
    
    def __repr__(self):
        return f"PlanExeDotEnv(dotenv_path={self.dotenv_path!r}, dotenv_dict.keys()={self.dotenv_dict.keys()!r})"

if __name__ == "__main__":
    dotenv = PlanExeDotEnv.load()
    print(dotenv)
