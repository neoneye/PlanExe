from enum import Enum
from src.llm_factory import get_llm
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.instrumentation import get_dispatcher
from llama_index.core.instrumentation.events.base import BaseEvent
from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler
from llama_index.core.instrumentation.events.llm import LLMChatInProgressEvent, LLMChatEndEvent
from llama_index.core.instrumentation.dispatcher import instrument_tags

from typing import (
    Any,
    Dict,
    List,
    Optional
)

class RawCollector(BaseEventHandler):
    model_config = {'extra': 'allow'} 
    
    @classmethod
    def class_name(cls) -> str:
        return "RawCollector"
    
    def __init__(self):
        super().__init__()
        self._buffer: list[str] = []
        self.full_raw: Optional[str] = None

    def handle(self, event: BaseEvent, **kwargs: Any) -> Any:
        # The delta is None when the content is cleaned up json.
        # The delta is not None when the content is the raw response, that is incomplete json until reaching the end of the stream.
        if isinstance(event, LLMChatInProgressEvent) and event.response.delta:
            self._buffer.append(event.response.delta)

        if isinstance(event, LLMChatEndEvent):
            self.full_raw = "".join(self._buffer)

class CostType(str, Enum):
    cheap = 'cheap'
    medium = 'medium'
    expensive = 'expensive'


class ExtractDetails(BaseModel):
    location: str = Field(description="Name of the location.")
    cost: CostType = Field(description="Cost of the plan.")
    summary: str = Field(description="What is this about.")


SYSTEM_PROMPT = """
Fill out the details as best you can.
"""

raw_collector = RawCollector()
get_dispatcher().add_event_handler(raw_collector)

llm = get_llm("ollama-llama3.1")
# llm = get_llm("openrouter-paid-gemini-2.0-flash-001")
# llm = get_llm("deepseek-chat")
# llm = get_llm("together-llama3.3")
# llm = get_llm("groq-gemma2")

messages = [
    ChatMessage(
        role=MessageRole.SYSTEM,
        content=SYSTEM_PROMPT.strip()
    ),
    ChatMessage(
        role=MessageRole.USER,
        content="I want to visit to Mars."
    ),
]
sllm = llm.as_structured_llm(ExtractDetails)

with instrument_tags({"tag1": "tag1"}):
    index = 0
    for chunk in sllm.stream_chat(messages):
        print(f"\nindex: {index} chunk: {chunk}")
        if chunk.raw:
            print(f"type of raw: {type(chunk.raw)}")
            print("raw: ", chunk.raw)
            print("Partial object:", chunk.raw.model_dump())

        index += 1

print(f"\nRAW FROM SERVER ➜\n{raw_collector.full_raw!r}")
