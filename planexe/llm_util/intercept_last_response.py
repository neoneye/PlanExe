"""
Intercept the raw response data from the LLM, so that it can be used for troubleshooting what is wrong with the LLM response.

PlanExe uses structured output a lot. However LlamaIndex does not provide an easy way to intercept the raw response data from the LLM.
This is my workaround to intercept the raw response data from the LLM.

PROMPT> python -m planexe.llm_util.intercept_last_response
"""
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole, ChatResponse
from llama_index.core.callbacks.schema import CBEventType, EventPayload
from llama_index.core.callbacks.base_handler import BaseCallbackHandler

from typing import (
    Any,
    Dict,
    List,
    Optional
)

class InterceptLastResponse(BaseCallbackHandler):
    def __init__(
        self,
        event_starts_to_ignore: Optional[List[CBEventType]] = None,
        event_ends_to_ignore: Optional[List[CBEventType]] = None,
    ) -> None:
        self.intercepted_response: Optional[str] = None
        super().__init__(
            event_starts_to_ignore=event_starts_to_ignore or [],
            event_ends_to_ignore=event_ends_to_ignore or [],
        )

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        return

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        return

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        # print(f"on_event_end event_type: {event_type}")
        # print(f"payload: {payload}")
        # print(f"event_id: {event_id}")
        # print(f"kwargs: {kwargs}")

        if event_type != CBEventType.LLM:
            return
        if payload is None:
            return
        if EventPayload.RESPONSE not in payload:
            return
        response = payload[EventPayload.RESPONSE]
        if not isinstance(response, ChatResponse):
            return
        intercepted_response = response.message.content
        # print(f"intercepted_response: {intercepted_response!r}")
        self.intercepted_response = intercepted_response


if __name__ == "__main__":
    from planexe.llm_factory import get_llm
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

    intercept_last_response = InterceptLastResponse()
    llm.callback_manager.add_handler(intercept_last_response)
    chat_response = sllm.chat(messages)
    llm.callback_manager.remove_handler(intercept_last_response)

    print(f"\nchat_response: {chat_response.raw.model_dump()}")

    print(f"\nRAW response:\n{intercept_last_response.intercepted_response!r}")
