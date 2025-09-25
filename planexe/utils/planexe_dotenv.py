"""
Load PlanExe's .env file, containing secrets such as API keys, like: OPENROUTER_API_KEY.

PROMPT> python -m planexe.utils.planexe_dotenv
"""
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional
from dotenv import dotenv_values
import logging
from planexe.utils.planexe_config import PlanExeConfig, PlanExeConfigError
from enum import Enum

logger = logging.getLogger(__name__)

class DotEnvKeyEnum(str, Enum):
    PATH_TO_PYTHON = "PATH_TO_PYTHON"
    PLANEXE_RUN_DIR = "PLANEXE_RUN_DIR"

@dataclass
class PlanExeDotEnv:
    dotenv_path: Path
    dotenv_dict: dict[str, str]

    @classmethod
    def load(cls):
        """
        Legacy load method for backward compatibility.
        For cloud environments, consider using load_hybrid() instead.
        """
        config = PlanExeConfig.load()
        if config.cloud_mode:
            logger.info("Cloud environment detected - using hybrid loading with environment variable priority")
            return cls.load_hybrid()

        # Original file-based loading for local development
        if config.dotenv_path is None:
            raise PlanExeConfigError("Required configuration file '.env' was not found. Cannot create a PlanExeDotEnv instance.")
        dotenv_path = config.dotenv_path
        env_before = os.environ.copy()
        dotenv_dict = dotenv_values(dotenv_path=dotenv_path)
        if env_before != os.environ:
            logger.error("PlanExeDotEnv.load() The dotenv_values() modified the environment variables. My assumption is that it doesn't do that. If you see this, please report it as a bug.")
            logger.error(f"PlanExeDotEnv.load() The dotenv_values() modified the environment variables. count before: {len(env_before)}, count after: {len(os.environ)}")
            logger.error(f"PlanExeDotEnv.load() The dotenv_values() modified the environment variables. content before: {env_before!r}, content after: {os.environ!r}")
        else:
            logger.debug(f"PlanExeDotEnv.load() Great!This is what is expected. The dotenv_values() did not modify the environment variables. number of items: {len(os.environ)}")
        return cls(
            dotenv_path=dotenv_path,
            dotenv_dict=dotenv_dict
        )

    @classmethod
    def load_hybrid(cls):
        """
        Cloud-native hybrid loading: Environment variables take priority over .env files.

        Priority order:
        1. Environment variables (Railway dashboard, Docker env, etc.)
        2. .env file contents (if available)
        3. Default values

        This method enables Railway and other cloud deployments to work without physical .env files.
        """
        config = PlanExeConfig.load()

        # Define all possible environment variables PlanExe might need
        env_var_keys = [
            # API Keys
            "OPENROUTER_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",

            # PlanExe Configuration
            "PLANEXE_RUN_DIR",
            "PLANEXE_CONFIG_PATH",
            "PATH_TO_PYTHON",

            # Database
            "DATABASE_URL",

            # System
            "PYTHONPATH",
            "PYTHONUNBUFFERED",
            "PORT"
        ]

        # Priority 1: Environment variables (Railway dashboard, etc.)
        dotenv_dict = {}
        env_var_count = 0
        for key in env_var_keys:
            env_value = os.environ.get(key)
            if env_value:
                dotenv_dict[key] = env_value
                env_var_count += 1

        logger.info(f"Loaded {env_var_count} environment variables from system environment")

        # Priority 2: .env file (if exists) - only for keys not already set
        file_var_count = 0
        if config.dotenv_path and config.dotenv_path.exists():
            logger.info(f"Loading .env file from: {config.dotenv_path}")
            file_dict = dotenv_values(dotenv_path=config.dotenv_path)
            for key, value in file_dict.items():
                if key not in dotenv_dict and value:  # Environment variables win
                    dotenv_dict[key] = value
                    file_var_count += 1

            logger.info(f"Loaded {file_var_count} additional variables from .env file")
        else:
            logger.info("No .env file found - using environment variables only (cloud mode)")

        # Use the config dotenv_path or create a virtual path
        dotenv_path = config.dotenv_path or Path("/app/.env")  # Virtual path for cloud

        total_vars = len(dotenv_dict)
        logger.info(f"Hybrid loading complete - total variables: {total_vars}")

        return cls(
            dotenv_path=dotenv_path,
            dotenv_dict=dotenv_dict
        )

    def update_os_environ(self):
        """
        Update the os.environ with the .env file content.
        """
        count_before = len(os.environ)
        os.environ.update(self.dotenv_dict)
        count_after = len(os.environ)
        logger.debug(f"PlanExeDotEnv.update_os_environ() Updated os.environ with the .env file content. number of items before: {count_before}, number of items after: {count_after}")

    def get(self, key: str) -> Optional[str]:
        return self.dotenv_dict.get(key)

    def get_absolute_path_to_file(self, key: str) -> Optional[Path]:
        """
        Resolves and validates the "key" variable.
        It's expected to be an absolute path to a file.
        If the key is not found, returns None.
        
        :return: A Path object if valid, otherwise None.
        """
        path_str = self.dotenv_dict.get(key)
        if path_str is None:
            logger.debug(f"{key} is not set")
            return None
            
        try:
            path_obj = Path(path_str)
        except Exception as e: # If path_str is bizarre
            logger.error(f"Invalid {key} string '{path_str!r}': {e!r}")
            return None
        if not path_obj.is_absolute():
            logger.error(f"{key} must be an absolute path: {path_obj!r}")
            return None
        if not path_obj.is_file():
            logger.error(f"{key} must be a file: {path_obj!r}")
            return None
        logger.debug(f"Using {key}: {path_obj!r}")
        return path_obj

    def get_absolute_path_to_dir(self, key: str) -> Optional[Path]:
        """
        Resolves and validates the "key" variable.
        It's expected to be an absolute path to a directory.
        If the key is not found, returns None.
        
        :return: A Path object if valid, otherwise None.
        """
        path_str = self.dotenv_dict.get(key)
        if path_str is None:
            logger.debug(f"{key} is not set")
            return None
            
        try:
            path_obj = Path(path_str)
        except Exception as e: # If path_str is bizarre
            logger.error(f"Invalid {key} string '{path_str!r}': {e!r}")
            return None
        if not path_obj.is_absolute():
            logger.error(f"{key} must be an absolute path: {path_obj!r}")
            return None
        if not path_obj.is_dir():
            logger.error(f"{key} must be a directory: {path_obj!r}")
            return None
        logger.debug(f"Using {key}: {path_obj!r}")
        return path_obj

    def __repr__(self):
        return f"PlanExeDotEnv(dotenv_path={self.dotenv_path!r}, dotenv_dict.keys()={self.dotenv_dict.keys()!r})"

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    dotenv = PlanExeDotEnv.load()
    print(dotenv)

    path_dir0 = dotenv.get_absolute_path_to_dir("SOME_DIR")
    print(f"DIR BEFORE: {path_dir0!r}")
    dotenv.dotenv_dict["SOME_DIR"] = "/tmp"
    path_dir1 = dotenv.get_absolute_path_to_dir("SOME_DIR")
    print(f"DIR AFTER: {path_dir1!r}")

    path_file0 = dotenv.get_absolute_path_to_file("SOME_FILE")
    print(f"FILE BEFORE: {path_file0!r}")
    dotenv.dotenv_dict["SOME_FILE"] = "/bin/sh"
    path_file1 = dotenv.get_absolute_path_to_file("SOME_FILE")
    print(f"FILE AFTER: {path_file1!r}")
