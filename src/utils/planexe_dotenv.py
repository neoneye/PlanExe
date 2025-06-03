"""
Load PlanExe's .env file, containing secrets such as API keys, like: OPENROUTER_API_KEY.

PROMPT> python -m src.utils.planexe_dotenv
"""
from dataclasses import dataclass
import os
from typing import Optional
from dotenv import dotenv_values

@dataclass
class PlanExeDotEnv:
    dotenv_path: str
    dotenv_isfile: bool
    dotenv_dict: dict[str, str]

    @classmethod
    def load(cls):
        dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
        dotenv_isfile = os.path.isfile(dotenv_path)
        dotenv_dict = dotenv_values(dotenv_path=dotenv_path)
        return cls(
            dotenv_path=dotenv_path, 
            dotenv_isfile=dotenv_isfile,
            dotenv_dict=dotenv_dict
        )

    def get(self, key: str) -> Optional[str]:
        return self.dotenv_dict.get(key)
    
    def __repr__(self):
        return f"PlanExeDotEnv(dotenv_path={self.dotenv_path}, dotenv_isfile={self.dotenv_isfile}, dotenv_dict.keys()={self.dotenv_dict.keys()})"

if __name__ == "__main__":
    dotenv = PlanExeDotEnv.load()
    print(dotenv)
