"""
Helper class for structured LLM interactions.
"""
import time
from math import ceil
import logging
from typing import TypeVar, Generic, Type
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from src.llm_util.intercept_last_response import InterceptLastResponse

logger = logging.getLogger(__name__)

T = TypeVar('T')

class StructuredLLMInteraction(Generic[T]):
    """
    Helper class for structured LLM interactions with type parameters.
    """
    def __init__(self, llm: LLM, response_type: Type[T]):
        """
        Initialize the structured LLM interaction helper.
        
        Args:
            llm: The LLM instance to use
            response_type: The type to structure the response as
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        
        self.llm = llm
        self.response_type = response_type
        self.sllm = llm.as_structured_llm(response_type)

    def chat(self, system_prompt: str, user_prompt: str) -> tuple[T, dict]:
        """
        Perform a structured chat interaction with the LLM.
        
        Args:
            system_prompt: The system prompt to use
            user_prompt: The user prompt to use
            
        Returns:
            A tuple containing:
            - The structured response of type T
            - A dictionary containing metadata about the interaction
        """
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

        intercept_last_response = InterceptLastResponse()
        self.llm.callback_manager.add_handler(intercept_last_response)
        start_time = time.perf_counter()
        
        try:
            chat_response = self.sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e
        finally:
            self.llm.callback_manager.remove_handler(intercept_last_response)

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        logger.info(f"RAW response:\n{intercept_last_response.intercepted_response!r}")

        metadata = dict(self.llm.metadata)
        metadata["llm_classname"] = self.llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        return chat_response.raw, metadata 