"""
Based on short description, make a longer description.

PROMPT> cd worker_plan
PROMPT> source .venv/bin/activate
PROMPT> python -m planexe.fiction.fiction_writer
"""
import json
import time
import logging
from math import ceil
from typing import Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class BookDraft(BaseModel):
    book_title: str = Field(description="Human readable title.")
    overview: str = Field(description="What is this about?")
    elaborate: str = Field(description="Details")
    background_story: str = Field(description="What is the background story.")
    blurb: str = Field(description="The back cover of the book. Immediately capture the readers attention.")
    goal: str = Field(description="What is the goal.")
    main_characters: list[str] = Field(description="List of characters in the story and their background story.")
    character_flaws: list[str] = Field(description="Character flaws relevant to the story.")
    plot_devices: list[str] = Field(description="Items that appear in the story.")
    possible_plot_ideas: list[str] = Field(description="List of story directions.")
    challenges: list[str] = Field(description="Things that could go wrong or be difficult.")
    chapter_title_list: list[str] = Field(description="Name of each chapter.")
    final_story: str = Field(description="Based on the above, what is the final story.")

@dataclass
class FictionWriter:
    """
    Given a short text, elaborate on it.
    """
    query: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, query: str, system_prompt: Optional[str]) -> 'FictionWriter':
        """
        Invoke LLM to write a fiction based on the query.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(query, str):
            raise ValueError("Invalid query.")

        chat_message_list = []
        if system_prompt:
            chat_message_list.append(
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=system_prompt,
                )
            )
        
        chat_message_list.append(ChatMessage(
            role=MessageRole.USER,
            content=query
        ))

        start_time = time.perf_counter()

        sllm = llm.as_structured_llm(BookDraft)
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.error(f"FictionWriter failed to chat with LLM: {e}")
            raise ValueError(f"Failed to chat with LLM: {e}")
        json_response = json.loads(chat_response.message.content)

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration

        result = FictionWriter(
            query=query,
            response=json_response,
            metadata=metadata
        )
        return result    

    def raw_response_dict(self, include_metadata=True, include_query=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_query:
            d['query'] = self.query
        return d

if __name__ == "__main__":
    from planexe.llm_factory import get_llm
    from planexe.prompt.prompt_catalog import PromptCatalog
    import os

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    system_prompt = "You are a fiction writer that has been given a short description to elaborate on."
    system_prompt = "You are a non-fiction writer that has been given a short description to elaborate on."

    prompt_catalog = PromptCatalog()
    prompt_catalog.load(os.path.join(os.path.dirname(__file__), 'data', 'simple_fiction_prompts.jsonl'))
    prompt_item = prompt_catalog.find("0e8e9b9d-95dd-4632-b47c-dcc4625a556d")

    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("lmstudio-qwen2.5-7b-instruct-1m")
    # llm = get_llm("openrouter-paid-gemini-2.0-flash-001")
    # llm = get_llm("ollama-qwen")
    # llm = get_llm("ollama-phi")
    # llm = get_llm("deepseek-chat")

    print(f"System: {system_prompt}")
    print(f"\n\nQuery: {query}")
    result = FictionWriter.execute(llm, query, system_prompt)

    print("\n\nResponse:")
    print(json.dumps(result.raw_response_dict(include_query=False), indent=2))
