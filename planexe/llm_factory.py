"""
Author: Claude Code using Sonnet 4
Date: 2025-09-22
PURPOSE: Simplified LLM factory using direct OpenAI client instead of complex llama-index system
SRP and DRY check: Pass - Single responsibility for LLM creation, removed complex dependencies
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any
from planexe.utils.planexe_llmconfig import PlanExeLLMConfig
from planexe.llm_util.simple_openai_llm import SimpleOpenAILLM

# This is a special case. It will cycle through the available LLM models, if the first one fails, try the next one.
SPECIAL_AUTO_ID = 'auto'
SPECIAL_AUTO_LABEL = 'Auto'

logger = logging.getLogger(__name__)

__all__ = ["get_llm", "LLMInfo", "get_llm_names_by_priority", "SPECIAL_AUTO_ID", "is_valid_llm_name"]

planexe_llmconfig = PlanExeLLMConfig.load()


class OllamaStatus(str, Enum):
    """Maintained for compatibility - not used in simplified system"""
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
        Returns info about available LLM models.
        Simplified version - no Ollama probing needed.
        """
        error_message_list = []
        llm_config_items = []

        # Add special auto option
        llm_config_items.append(LLMConfigItem(id=SPECIAL_AUTO_ID, label=SPECIAL_AUTO_LABEL))

        # Add all configured models
        for config_id, config in planexe_llmconfig.llm_config_dict.items():
            priority = config.get("priority", None)
            if priority:
                label_with_priority = f"{config_id} (prio: {priority})"
            else:
                label_with_priority = config_id

            item = LLMConfigItem(id=config_id, label=label_with_priority)
            llm_config_items.append(item)

        return LLMInfo(
            llm_config_items=llm_config_items,
            ollama_status=OllamaStatus.no_ollama_models,  # No Ollama in simplified system
            error_message_list=error_message_list,
        )


def get_llm_names_by_priority() -> list[str]:
    """
    Returns a list of LLM names sorted by priority.
    Lowest values comes first.
    """
    configs = [(name, config) for name, config in planexe_llmconfig.llm_config_dict.items()
               if config.get("priority") is not None]
    configs.sort(key=lambda x: x[1].get("priority", 0))
    return [name for name, _ in configs]


def is_valid_llm_name(llm_name: str) -> bool:
    """
    Returns True if the LLM name is valid, False otherwise.
    """
    return llm_name in planexe_llmconfig.llm_config_dict


def get_llm(llm_name: Optional[str] = None, **kwargs: Any) -> SimpleOpenAILLM:
    """
    Returns a SimpleOpenAILLM instance based on the simplified config.

    :param llm_name: The name/key of the LLM to instantiate.
                     If None, uses first model by priority.
    :param kwargs: Additional keyword arguments (maintained for compatibility).
    :return: An instance of SimpleOpenAILLM.
    """
    if not llm_name:
        # Get first model by priority
        llm_names = get_llm_names_by_priority()
        if not llm_names:
            raise ValueError("No LLM models configured")
        llm_name = llm_names[0]

    if llm_name == SPECIAL_AUTO_ID:
        logger.error(f"The special {SPECIAL_AUTO_ID!r} is not a LLM model that can be created. Please use a valid LLM name.")
        raise ValueError(f"The special {SPECIAL_AUTO_ID!r} is not a LLM model that can be created. Please use a valid LLM name.")

    if not is_valid_llm_name(llm_name):
        logger.error(f"Cannot create LLM, the llm_name {llm_name!r} is not found in llm_config.json.")
        raise ValueError(f"Cannot create LLM, the llm_name {llm_name!r} is not found in llm_config.json.")

    config = planexe_llmconfig.llm_config_dict[llm_name]

    # Extract model and provider from simplified config
    model = config.get("model")
    provider = config.get("provider")

    if not model or not provider:
        raise ValueError(f"LLM config for {llm_name!r} missing required 'model' or 'provider' field")

    try:
        return SimpleOpenAILLM(model=model, provider=provider, **kwargs)
    except Exception as e:
        logger.error(f"Failed to create LLM {llm_name}: {e}")
        raise ValueError(f"Failed to create LLM {llm_name}: {e}")


if __name__ == '__main__':
    # Test the simplified system
    llm_names = get_llm_names_by_priority()
    print("LLM names by priority:")
    for llm_name in llm_names:
        print(f"- {llm_name}")

    print("\nTesting the first LLM:")
    try:
        if llm_names:
            llm = get_llm(llm_name=llm_names[0])
            print(f"Successfully loaded LLM: {llm}")
            print("Testing completion...")
            result = llm.complete("Hello, how are you?")
            print(f"Response: {result}")
        else:
            print("No LLM models configured")
    except Exception as e:
        print(f"Error: {e}")