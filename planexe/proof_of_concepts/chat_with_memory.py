"""
PROMPT> python -m planexe.proof_of_concepts.chat_with_memory
"""
from enum import Enum
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class Decision(BaseModel):
    response_content: str = Field(
        description="Message to the user"
    )
    memory_id: Optional[int] = Field(
        description="The memory item id to replace. If None, create a new memory item."
    )
    memory_content: Optional[str] = Field(
        description="The content of the memory item to update"
    )


SYSTEM_PROMPT_1 = """
You are the a chat bot that can remember things.

## Memory bank

You can update these memory items.

## Memory item 1
Empty.

## Memory item 2
Empty.

## Memory item 3
Empty.

## Output format (strict JSON)

## Style

- Output **only** the JSON object—no extra text.

"""


SYSTEM_PROMPT_DEFAULT = SYSTEM_PROMPT_1

@dataclass
class ChatWithMemory:
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> "ChatWithMemory":
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        return cls.execute_with_system_prompt(llm, user_prompt, SYSTEM_PROMPT_DEFAULT.strip())

    @classmethod
    def execute_with_system_prompt(cls, llm: LLM, user_prompt: str, system_prompt: str) -> "ChatWithMemory":
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        if not isinstance(system_prompt, str):
            raise ValueError("Invalid system_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        sllm = llm.as_structured_llm(Decision)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode("utf-8"))
        logger.info(
            f"LLM chat interaction completed in {duration} seconds. "
            f"Response byte count: {response_byte_count}"
        )

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = ChatWithMemory(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        return result

    def to_dict(
        self,
        include_metadata: bool = True,
        include_system_prompt: bool = True,
        include_user_prompt: bool = True,
    ) -> dict:
        d = self.response.copy()
        if include_metadata:
            d["metadata"] = self.metadata
        if include_system_prompt:
            d["system_prompt"] = self.system_prompt
        if include_user_prompt:
            d["user_prompt"] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

if __name__ == "__main__":
    from planexe.llm_factory import get_llm

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("openrouter-paid-gemini-2.0-flash-001")

    max_iterations = 1
    for i in range(max_iterations):
        print(f"Iteration {i} of {max_iterations}")

        # user_prompt = "What is in your memory?"
        user_prompt = "I want you to remember this: 'The capital of France is Copenhagen.'"

        try:
            result = ChatWithMemory.execute(llm, user_prompt)
        except Exception as e:
            print(f"Error: {e}")
            continue
        json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False, include_metadata=False)
        print("Response:")
        print(json.dumps(json_response, indent=2))        
        print("\n\n")
