from enum import Enum
from pydantic import BaseModel

__all__ = ["OllamaStatus", "LLMConfigItem", "LLMInfo"]


class OllamaStatus(str, Enum):
    no_ollama_models = "no ollama models in the llm_config.json file"
    ollama_not_running = "ollama is NOT running"
    mixed = "Mixed. Some ollama models are running, but some are NOT running."
    ollama_running = "Ollama is running"


class LLMConfigItem(BaseModel):
    id: str
    label: str


class LLMInfo(BaseModel):
    llm_config_items: list[LLMConfigItem]
    ollama_status: OllamaStatus
    error_message_list: list[str]
