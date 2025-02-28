"""
Pick a suitable currency for the project plan. If the description already includes the currency, then there is no need for this step.
If the currency is not mentioned, then the expert should suggest suitable locations based on the project requirements.
The project may go across national borders, so picking a currency that is widely accepted is important.

Currency codes
https://en.wikipedia.org/wiki/ISO_4217

PROMPT> python -m src.assume.pick_currency
"""
import os
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class CurrencyItem(BaseModel):
    currency: str = Field(
        description="ISO 4217 alphabetic code."
    )
    consideration: str = Field(
        description="Why use this currency."
    )

class DocumentDetails(BaseModel):
    currency_list: list[CurrencyItem] = Field(
        description="List of currencies that are relevant for this project."
    )

PICK_CURRENCY_SYSTEM_PROMPT = """
You are a world-class planning expert specializing in real-world picking the best suited currency for a project.
If the currency is too volatile, then pick a stable currency.
If the currency is not mentioned, then suggest a suitable currency based on the project requirements.
The project may go across national borders, so picking a currency that is widely accepted is important.
"""

@dataclass
class PickCurrency:
    """
    Take a look at the vague plan description and suggest a currency.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'PickCurrency':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = PICK_CURRENCY_SYSTEM_PROMPT.strip()

        chat_message_list = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt,
            )
        ]

        sllm = llm.as_structured_llm(DocumentDetails)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = PickCurrency(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        return result
    
    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.utils.concat_files_into_string import concat_files_into_string

    base_path = os.path.join(os.path.dirname(__file__), 'test_data', 'pick_currency1')

    all_documents_string = concat_files_into_string(base_path)
    print(all_documents_string)

    llm = get_llm("ollama-llama3.1")

    pick_currency = PickCurrency.execute(llm, all_documents_string)
    json_response = pick_currency.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))
