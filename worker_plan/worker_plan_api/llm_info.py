from dataclasses import dataclass
from enum import Enum

__all__ = ["OllamaStatus", "LLMConfigItem", "LLMInfo"]


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
