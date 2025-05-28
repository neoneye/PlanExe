from enum import Enum
from dataclasses import dataclass, field
from src.llm_factory import get_llm
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.instrumentation import get_dispatcher
from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler
from llama_index.core.instrumentation.events.llm import LLMChatInProgressEvent
from llama_index.core.instrumentation.dispatcher import instrument_tags

from typing import (
    Any,
    Dict,
    List,
    Optional
)

@dataclass
class InterceptedResponse:
    message_old: Optional[str] = None
    message_new: Optional[str] = None

    def push_message(self, message: str) -> None:
        if message == self.message_new:
            return
        self.message_old = self.message_new
        self.message_new = message


intercepted_response_delta_none = InterceptedResponse()
intercepted_response_delta_not_none = InterceptedResponse()

class ChatProgressPrinter(BaseEventHandler):
    """Print every streamed delta and the partially–parsed message."""

    @classmethod
    def class_name(cls) -> str:
        return "ChatProgressPrinter"

    def handle(self, event):
        if isinstance(event, LLMChatInProgressEvent):
            content = event.response.message.content
            if content is not None:
                if event.response.delta is None:
                    # When delta is None, then the content is cleaned up json.
                    intercepted_response_delta_none.push_message(content)
                else:
                    # When delta is not None, then the content is the raw response, that is incomplete json until reaching the end of the stream.
                    intercepted_response_delta_not_none.push_message(content)
            print(f"Δ  : {event.response.delta!r}")
            print(f"Acc : {event.response.message.content!r}")
            print(f"Tags : {event.tags!r}")


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
root.add_event_handler(ChatProgressPrinter())

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

print(f"\nintercepted_response_delta_none.message_old\n{intercepted_response_delta_none.message_old!r}")
print(f"\nintercepted_response_delta_none.message_new\n{intercepted_response_delta_none.message_new!r}")
print(f"\nintercepted_response_delta_not_none.message_old\n{intercepted_response_delta_not_none.message_old!r}")
print(f"\nintercepted_response_delta_not_none.message_new\n{intercepted_response_delta_not_none.message_new!r}")
