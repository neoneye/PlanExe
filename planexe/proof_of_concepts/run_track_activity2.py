"""
Usage:
python -m planexe.proof_of_concepts.run_track_activity2
"""
from enum import Enum
from planexe.llm_factory import get_llm
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.instrumentation import get_dispatcher
from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler
from llama_index.core.instrumentation.events.llm import LLMChatStartEvent, LLMChatEndEvent
from llama_index.core.instrumentation.dispatcher import instrument_tags

class ActivityPrinter(BaseEventHandler):
    @classmethod
    def class_name(cls) -> str:
        return "ActivityPrinter"

    def handle(self, event):
        if isinstance(event, LLMChatStartEvent):
            print(f"LLMChatStartEvent: {event!r}")
        elif isinstance(event, LLMChatEndEvent):
            print(f"LLMChatEndEvent: {event!r}")


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

root = get_dispatcher()
root.add_event_handler(ActivityPrinter())

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
    response = sllm.chat(messages)
    print(f"response:\n{response!r}")
