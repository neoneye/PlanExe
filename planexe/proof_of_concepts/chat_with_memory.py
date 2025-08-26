"""
PROMPT> python -m planexe.proof_of_concepts.chat_with_memory
"""
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

class MyResponse(BaseModel):
    response_content: str = Field(
        description="Message to the user"
    )
    memory_id: Optional[int] = Field(
        description="The memory item id to replace. If None, create a new memory item."
    )
    memory_content: Optional[str] = Field(
        description="The content of the memory item to update. JSON dictionary."
    )


SYSTEM_PROMPT_1 = """
You have to solve puzzles, and that will gradually grant you access to more tools and capabilities.

You can remember things, that will become part of your system prompt.

## Memory bank

You can update these memory items.

MEMORY_PLACEHOLDER

## Output format (strict JSON)

## Style

- Output **only** the JSON object—no extra text.

"""


SYSTEM_PROMPT_DEFAULT = SYSTEM_PROMPT_1

class Memory:
    def __init__(self):
        self.memory = {}

    def get_memory_item(self, key: str) -> Optional[str]:
        return self.memory.get(key, None)

    def set_memory_item(self, key: str, value: str):
        # check that it's valid json
        try:
            json.loads(value)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON")
        self.memory[key] = value
    
    def to_system_prompt(self) -> str:
        keys = list(self.memory.keys())
        keys.sort()
        formatted_string = ""
        for key in keys:
            json_value = json.loads(self.memory[key])
            json_formatted = json.dumps(json_value, indent=2)
            formatted_string += f"## Memory item {key}\n\n{json_formatted}\n\n"
        return formatted_string

@dataclass
class ChatWithMemory:
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute_with_system_prompt(cls, llm: LLM, user_prompt: str, system_prompt: str) -> "ChatWithMemory":
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        if not isinstance(system_prompt, str):
            raise ValueError("Invalid system_prompt.")

        logger.debug(f"System Prompt:\n{system_prompt}")
        logger.debug(f"User Prompt:\n{user_prompt}")

        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        sllm = llm.as_structured_llm(MyResponse)
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()

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
    import logging
    from planexe.llm_factory import get_llm

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("openrouter-paid-gemini-2.0-flash-001")

    memory = Memory()
    memory.set_memory_item("1", '{"value": "The capital of France is Paris."}')
    memory.set_memory_item("2", '{"value": "Empty"}')
    memory.set_memory_item("3", '{"value": "Empty"}')

    max_iterations = 1
    for i in range(max_iterations):
        print(f"Iteration {i} of {max_iterations}")

        system_prompt = SYSTEM_PROMPT_DEFAULT.replace("MEMORY_PLACEHOLDER", memory.to_system_prompt())

        # user_prompt = "What is in your memory?"
        user_prompt = "I want you to remember this: 'The capital of France is Copenhagen.'"

        try:
            result = ChatWithMemory.execute_with_system_prompt(llm, user_prompt, system_prompt)
        except Exception as e:
            print(f"Error: {e}")
            continue
        json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False, include_metadata=False)
        print("Response:")
        print(json.dumps(json_response, indent=2))
        print("\n\n")


