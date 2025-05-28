"""
Intercept the raw response data from the LLM, so that it can be used for troubleshooting what is wrong with the LLM response.

PlanExe uses structured output a lot. However LlamaIndex does not provide any way to intercept the raw response data from the LLM.
This is my workaround to intercept the raw response data from the LLM.

PROMPT> python -m src.llm_util.raw_collector
"""
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from llama_index.core.instrumentation import get_dispatcher
from llama_index.core.instrumentation.events.base import BaseEvent
from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler
from llama_index.core.instrumentation.events.llm import LLMChatInProgressEvent
from typing import Any, Dict

RAW_COLLECTOR_ID_TAG = "raw_collector_id"

@dataclass
class RawCollectorItem:
    buffer: list[str] = field(default_factory=list)

    @property
    def full(self) -> str:
        return "".join(self.buffer)

class RawCollector(BaseEventHandler):
    model_config = {'extra': 'allow'} 
    
    @classmethod
    def class_name(cls) -> str:
        return "RawCollector"

    @classmethod
    def singleton(cls) -> 'RawCollector':
        """
        This is a singleton.
        On first access, it is installed into the root dispatcher of LlamaIndex.
        Subsequent access will return the same instance.
        """
        if not hasattr(cls, '_instance'):
            instance = cls()
            cls._instance = instance
            get_dispatcher().add_event_handler(instance)
        return cls._instance
    
    def __init__(self):
        super().__init__()
        self.raw_items: Dict[str, RawCollectorItem] = {}

    def handle(self, event: BaseEvent, **kwargs: Any) -> Any:
        tags = event.tags
        if RAW_COLLECTOR_ID_TAG not in tags:
            return
        id = tags[RAW_COLLECTOR_ID_TAG]
        if id not in self.raw_items:
            return

        # The delta is None when the content is cleaned up json.
        # The delta is not None when the content is the raw response, that is incomplete json until reaching the end of the stream.
        if isinstance(event, LLMChatInProgressEvent) and event.response.delta:
            self.add_to_raw_item_with_id(id, event.response.delta)

    def register_raw_item_with_id(self, id: str) -> None:
        self.raw_items[id] = RawCollectorItem()

    def add_to_raw_item_with_id(self, id: str, delta: str) -> None:
        self.raw_items[id].buffer.append(delta)

    def get_raw_item_with_id(self, id: str) -> RawCollectorItem:
        return self.raw_items[id]
    
    def remove_raw_item_with_id(self, id: str) -> None:
        del self.raw_items[id]


if __name__ == "__main__":
    from src.llm_factory import get_llm
    from enum import Enum
    from llama_index.core.instrumentation.dispatcher import instrument_tags
    from llama_index.core.llms import ChatMessage, MessageRole

    class CostType(str, Enum):
        cheap = 'cheap'
        medium = 'medium'
        expensive = 'expensive'


    class ExtractDetails(BaseModel):
        location: str = Field(description="Name of the location.")
        cost: CostType = Field(description="Cost of the plan.")
        summary: str = Field(description="What is this about.")

    SYSTEM_PROMPT = "Fill out the details as best you can."

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
    raw_collector = RawCollector.singleton()
    raw_collector.register_raw_item_with_id(track_id)
    with instrument_tags({RAW_COLLECTOR_ID_TAG: track_id}):
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
