import logging
import os
import json
from enum import Enum
from dataclasses import dataclass
from dotenv import dotenv_values
from typing import Optional, Any, Dict
from llama_index.core.llms.llm import LLM
from llama_index.llms.mistralai import MistralAI
from llama_index.llms.ollama import Ollama
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.openai import OpenAI
from llama_index.llms.together import TogetherLLM
from llama_index.llms.groq import Groq
from llama_index.llms.lmstudio import LMStudio
from llama_index.llms.openrouter import OpenRouter
from src.llm_util.ollama_info import OllamaInfo

# You can disable this if you don't want to send app info to OpenRouter.
SEND_APP_INFO_TO_OPENROUTER = True

logger = logging.getLogger(__name__)

__all__ = ["get_llm", "LLMInfo"]

# Load .env values and merge with system environment variables.
# This one-liner makes sure any secret injected by Hugging Face, like OPENROUTER_API_KEY
# overrides what’s in your .env file.
_dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
_dotenv_dict = {**dotenv_values(dotenv_path=_dotenv_path), **os.environ}

_config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "llm_config.json"))


def load_config(config_path: str) -> Dict[str, Any]:
    """Loads the configuration from a JSON file."""
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Warning: llm_config.json not found at {config_path}. Using default settings.")
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

class OllamaStatus(str, Enum):
    no_ollama_models = 'no ollama models in the llm_config.json file'
    ollama_not_running = 'ollama is NOT running'
    mixed = 'Mixed. Some ollama models are running, but some are NOT running.'
    ollama_running = 'Ollama is running'


@dataclass
class LLMConfigItem:
    id: str
    label: str

@dataclass
class LLMInfo:
    llm_config_items: list[LLMConfigItem]
    ollama_status: OllamaStatus
    error_message_list: list[str]

    @classmethod
    def obtain_info(cls) -> 'LLMInfo':
        """
        Returns a list of available LLM names.
        """

        # Probe each Ollama service endpoint just once.
        error_message_list = []
        ollama_info_per_host = {}
        count_running = 0
        count_not_running = 0
        for config_id, config in _llm_configs.items():
            if config.get("class") != "Ollama":
                continue
            arguments = config.get("arguments", {})
            model = arguments.get("model", None)
            base_url = arguments.get("base_url", None)

            if base_url in ollama_info_per_host:
                # Already got info for this host. No need to get it again.
                continue

            ollama_info = OllamaInfo.obtain_info(base_url=base_url)
            ollama_info_per_host[base_url] = ollama_info

            running_on = "localhost" if base_url is None else base_url

            if ollama_info.is_running:
                count_running += 1
            else:
                count_not_running += 1

            if ollama_info.is_running == False:
                print(f"Ollama is not running on {running_on}. Please start the Ollama service, in order to use the models via Ollama.")
            elif ollama_info.error_message:
                print(f"Error message: {ollama_info.error_message}")
                error_message_list.append(ollama_info.error_message)

        # Get info about the each LLM config item that is using Ollama.
        llm_config_items = []
        for config_id, config in _llm_configs.items():
            if config.get("class") != "Ollama":
                item = LLMConfigItem(id=config_id, label=config_id)
                llm_config_items.append(item)
                continue
            arguments = config.get("arguments", {})
            model = arguments.get("model", None)
            base_url = arguments.get("base_url", None)

            ollama_info = ollama_info_per_host[base_url]

            is_model_available = ollama_info.is_model_available(model)
            if is_model_available:
                label = config_id
            else:
                label = f"{config_id} ❌ unavailable"
            
            if ollama_info.is_running and not is_model_available:
                error_message = f"Problem with config `\"{config_id}\"`: The model `\"{model}\"` is not available in Ollama. Compare model names in `llm_config.json` with the names available in Ollama."
                error_message_list.append(error_message)
            
            item = LLMConfigItem(id=config_id, label=label)
            llm_config_items.append(item)

        if count_not_running == 0 and count_running > 0:
            ollama_status = OllamaStatus.ollama_running
        elif count_not_running > 0 and count_running == 0:
            ollama_status = OllamaStatus.ollama_not_running
        elif count_not_running > 0 and count_running > 0:
            ollama_status = OllamaStatus.mixed
        else:
            ollama_status = OllamaStatus.no_ollama_models

        return LLMInfo(
            llm_config_items=llm_config_items, 
            ollama_status=ollama_status,
            error_message_list=error_message_list,
        )

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
        logger.error(f"LLM '{llm_name}' not found in config.json. Falling back to hardcoded defaults.")
        raise ValueError(f"Unsupported LLM name: {llm_name}")

    config = _llm_configs[llm_name]
    class_name = config.get("class")
    arguments = config.get("arguments", {})

    # Substitute environment variables
    arguments = substitute_env_vars(arguments, _dotenv_dict)

    # Override with any kwargs passed to get_llm()
    arguments.update(kwargs)

    if class_name == "OpenRouter" and SEND_APP_INFO_TO_OPENROUTER:
        # https://openrouter.ai/rankings
        # https://openrouter.ai/docs/api-reference/overview#headers
        arguments_extra = {
            "additional_kwargs": {
                "extra_headers": {
                    "HTTP-Referer": "https://github.com/neoneye/PlanExe",
                    "X-Title": "PlanExe"
                }
            }
        }
        arguments.update(arguments_extra)

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
