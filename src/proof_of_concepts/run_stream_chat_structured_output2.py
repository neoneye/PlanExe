from enum import Enum
from dataclasses import dataclass, field
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

@dataclass
class RawItem:
    buffer: list[str] = field(default_factory=list)

    @property
    def full(self) -> str:
        return "".join(self.buffer)

class RawCollector(BaseEventHandler):
    model_config = {'extra': 'allow'} 
    
    @classmethod
    def class_name(cls) -> str:
        return "RawCollector"
    
    def __init__(self):
        super().__init__()
        self.raw_items: Dict[str, RawItem] = {}

    def handle(self, event: BaseEvent, **kwargs: Any) -> Any:
        tags = event.tags
        if "raw_collect_id" not in tags:
            return
        id = tags["raw_collect_id"]
        if id not in self.raw_items:
            return

        # The delta is None when the content is cleaned up json.
        # The delta is not None when the content is the raw response, that is incomplete json until reaching the end of the stream.
        if isinstance(event, LLMChatInProgressEvent) and event.response.delta:
            self.add_to_raw_item_with_id(id, event.response.delta)

    def register_raw_item_with_id(self, id: str) -> None:
        self.raw_items[id] = RawItem()

    def add_to_raw_item_with_id(self, id: str, delta: str) -> None:
        self.raw_items[id].buffer.append(delta)

    def get_raw_item_with_id(self, id: str) -> RawItem:
        return self.raw_items[id]
    
    def remove_raw_item_with_id(self, id: str) -> None:
        del self.raw_items[id]

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

track_id = "item1"
raw_collector.register_raw_item_with_id(track_id)
with instrument_tags({"raw_collect_id": track_id}):
    index = 0
    for chunk in sllm.stream_chat(messages):
        print(f"\nindex: {index} chunk: {chunk}")
        if chunk.raw:
            print(f"type of raw: {type(chunk.raw)}")
            print("raw: ", chunk.raw)
            print("Partial object:", chunk.raw.model_dump())

        index += 1

raw_item = raw_collector.get_raw_item_with_id(track_id)
print(f"\nRAW FROM SERVER:\n{raw_item.full!r}")

raw_collector.remove_raw_item_with_id(track_id)
