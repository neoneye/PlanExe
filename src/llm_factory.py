import os
import json
from dotenv import dotenv_values
from typing import Optional, Any, Dict
from llama_index.core.llms.llm import LLM
from llama_index.llms.ollama import Ollama
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.together import TogetherLLM
from llama_index.llms.groq import Groq
from llama_index.llms.lmstudio import LMStudio
from llama_index.llms.openrouter import OpenRouter

__all__ = ["get_llm", "get_available_llms"]

# Define paths and load environment variables and config
_dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
_dotenv_dict = dotenv_values(dotenv_path=_dotenv_path)
_config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "llm_config.json"))


def load_config(config_path: str) -> Dict[str, Any]:
    """Loads the configuration from a JSON file."""
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: config.json not found at {config_path}. Using default settings.")
        return {}
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from {config_path}: {e}")


_llm_configs = load_config(_config_path)


def substitute_env_vars(config: Dict[str, Any], env_vars: Dict[str, str]) -> Dict[str, Any]:
    """Recursively substitutes environment variables in the configuration."""

    def replace_value(value: Any) -> Any:
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            var_name = value[2:-1]  # Extract variable name
            if var_name in env_vars:
                return env_vars[var_name]
            else:
                print(f"Warning: Environment variable '{var_name}' not found.")
                return value  # Or raise an error if you prefer strict enforcement
        return value

    def process_item(item):
        if isinstance(item, dict):
            return {k: process_item(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [process_item(i) for i in item]
        else:
            return replace_value(item)

    return process_item(config)

def get_available_llms() -> list[str]:
    """
    Returns a list of available LLM names.
    """
    return list(_llm_configs.keys())

def get_llm(llm_name: Optional[str] = None, **kwargs: Any) -> LLM:
    """
    Returns an LLM instance based on the config.json file or a fallback default.

    :param llm_name: The name/key of the LLM to instantiate.
                     If None, falls back to DEFAULT_LLM in .env (or 'ollama-llama3.1').
    :param kwargs: Additional keyword arguments to override default model parameters.
    :return: An instance of a LlamaIndex LLM class.
    """
    if not llm_name:
        llm_name = _dotenv_dict.get("DEFAULT_LLM", "ollama-llama3.1")

    if llm_name not in _llm_configs:
        # If llm_name doesn't exits in _llm_configs, then we go through default settings
        print(f"Warning: LLM '{llm_name}' not found in config.json. Falling back to hardcoded defaults.")
        raise ValueError(f"Unsupported LLM name: {llm_name}")

    config = _llm_configs[llm_name]
    class_name = config.get("class")
    arguments = config.get("arguments", {})

    # Substitute environment variables
    arguments = substitute_env_vars(arguments, _dotenv_dict)

    # Override with any kwargs passed to get_llm()
    arguments.update(kwargs)

    # Dynamically instantiate the class
    try:
        llm_class = globals()[class_name]  # Get class from global scope
        return llm_class(**arguments)
    except KeyError:
        raise ValueError(f"Invalid LLM class name in config.json: {class_name}")
    except TypeError as e:
        raise ValueError(f"Error instantiating {class_name} with arguments: {e}")

if __name__ == '__main__':
    try:
        llm = get_llm(llm_name="ollama-llama3.1")
        print(f"Successfully loaded LLM: {llm.__class__.__name__}")
        print(llm.complete("Hello, how are you?"))
    except ValueError as e:
        print(f"Error: {e}")
