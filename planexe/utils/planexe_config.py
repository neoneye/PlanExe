"""
Locate PlanExe's config files, like .env and llm_config.json.

Finds config files by checking the following locations in order:
1. The directory specified by the PLANEXE_CONFIG_PATH environment variable. It must be an absolute path.
2. The current working directory (CWD).
3. The PlanExe project root directory (assumed to be two levels above this file's location).

Usage: without any PLANEXE_CONFIG_PATH environment variable.
PROMPT> python -m planexe.utils.planexe_config

Usage: with a PLANEXE_CONFIG_PATH environment variable set.
PROMPT> PLANEXE_CONFIG_PATH='/Users/neoneye/git/PlanExeGroup/PlanExe' python -m planexe.utils.planexe_config
"""
from dataclasses import dataclass
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class PlanExeConfig:
    """
    Holds the resolved paths to PlanExe configuration files and the env var value used.
    """
    planexe_config_path: Optional[str]
    dotenv_path: Optional[str]
    llm_config_json_path: Optional[str]

    @classmethod
    def load(cls) -> "PlanExeConfig":
        """
        Loads configuration paths by searching predefined locations.
        :return: An instance of PlanExeConfig with resolved paths.
        """
        planexe_config_path = cls.resolve_planexe_config_path()
        dotenv_path = cls.find_file_in_search_order(".env", planexe_config_path)
        llm_config_json_path = cls.find_file_in_search_order("llm_config.json", planexe_config_path)
        return cls(
            planexe_config_path=planexe_config_path, 
            dotenv_path=dotenv_path, 
            llm_config_json_path=llm_config_json_path
        )

    @classmethod
    def resolve_planexe_config_path(cls) -> Optional[str]:
        """
        Resolves and validates the PLANEXE_CONFIG_PATH environment variable.
        It's expected to be an absolute path to a directory.
        :return: An absolute path string if valid, otherwise None.
        """
        path = os.environ.get("PLANEXE_CONFIG_PATH")
        if path is None:
            logger.debug("PlanExeConfig.resolve_planexe_config_path() PLANEXE_CONFIG_PATH is not set")
            return None
        if not os.path.isabs(path):
            logger.error(f"PlanExeConfig.resolve_planexe_config_path() Ignoring invalid PLANEXE_CONFIG_PATH. It must be an absolute path to a directory, but it's not an absolute path: {path!r}")
            return None
        if not os.path.isdir(path):
            logger.error(f"PlanExeConfig.resolve_planexe_config_path() Ignoring invalid PLANEXE_CONFIG_PATH. It must be an absolute path to a directory, but it's not a directory: {path!r}")
            return None
        logger.debug(f"PlanExeConfig.resolve_planexe_config_path() Using PLANEXE_CONFIG_PATH: {path!r}")
        return path

    @classmethod
    def find_file_in_search_order(cls, filename: str, planexe_config_path: Optional[str]) -> Optional[str]:
        """
        Finds a specific configuration file based on a precedence of locations.

        Search order:
        1. Directory from validated PLANEXE_CONFIG_PATH (if provided and valid).
        2. Current Working Directory (CWD).
        3. PlanExe project root.

        :param filename: The name of the file to find (e.g., ".env").
        :param planexe_config_path: The validated absolute directory path from PLANEXE_CONFIG_PATH.
        :return: The absolute path to the file if found, otherwise None.
        """
        # Step 1: Check if PLANEXE_CONFIG_PATH is set and contains the file
        if planexe_config_path is not None: 
            # planexe_config_path is already a validated absolute dir path
            config_file_path = os.path.join(planexe_config_path, filename)
            if os.path.isfile(config_file_path):
                # config_file_path will be absolute here
                logger.debug(f"PlanExeConfig.find() planexe_config_path. Found {filename!r} at {config_file_path!r}")
                return config_file_path

        # Step 2: Check if file exists in current working directory
        cwd_file_path = os.path.abspath(os.path.join(os.getcwd(), filename))
        if os.path.isfile(cwd_file_path):
            logger.debug(f"PlanExeConfig.find() cwd. Found {filename!r} at {cwd_file_path!r}")
            return cwd_file_path

        # Step 3: Check if file exists in PlanExe root directory
        root_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", filename))
        if os.path.isfile(root_file_path):
            logger.debug(f"PlanExeConfig.find() root. Found {filename!r} at {root_file_path!r}")
            return root_file_path

        # If file is not found in any location, return None
        logger.error(f"PlanExeConfig.find(): {filename!r} not found in any of the search locations (ENV_VAR, CWD, Project Root).")
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    config = PlanExeConfig.load()
    print(f"config: {config!r}")
