"""
An LLM with predefined responses, to be used for testing.

PROMPT> python -m planexe.llm_util.response_mockllm
"""
from typing import Any, Sequence
from llama_index.core.llms import MockLLM, ChatResponse, ChatMessage, MessageRole
import itertools

class ResponseMockLLM(MockLLM):
    """
    An LLM with predefined responses, cycle through them.
    """
    def __init__(self, responses: list[str], **kwargs):
        # Length of the longest the response
        max_tokens = max(len(response) for response in responses)
        super().__init__(max_tokens=max_tokens, **kwargs)
        object.__setattr__(self, 'responses', responses or ["Mock response"])
        object.__setattr__(self, 'response_cycle', itertools.cycle(self.responses))

    def raise_exception_if_needed(self, response_text: str) -> None:
        """
        If the response starts with "raise:message", then raise an exception with the message.
        """
        if response_text.startswith("raise:"):
            raise Exception(response_text.split(":", 1)[1])

    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        """
        Override the chat method to return our predefined responses.
        """
        response_text = next(self.response_cycle)
        self.raise_exception_if_needed(response_text)
        # Create a ChatResponse with the assistant message
        assistant_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=response_text
        )
        return ChatResponse(message=assistant_message)

    def _generate_text(self, length: int) -> str:
        message = next(self.response_cycle)
        self.raise_exception_if_needed(message)
        return message

if __name__ == "__main__":
    from llama_index.core.llms import ChatMessage, MessageRole
    llm = ResponseMockLLM(
        responses=["Mercury, Venus, Earth", "Hydrogen, Helium, Hafnium"]
    )

    message1 = ChatMessage(
        role=MessageRole.USER,
        content="List names of 3 planets in the solar system. Comma separated. No other text.",
    )
    response1 = llm.chat([message1])
    print(f"response1:\n{response1!r}")

    message2 = ChatMessage(
        role=MessageRole.ASSISTANT,
        content=response1.message.content
    )
    message3 = ChatMessage(
        role=MessageRole.USER,
        content="List 3 items from the periodic table. Comma separated. No other text.",
    )
    response2 = llm.chat([message1, message2, message3])
    print(f"response2:\n{response2!r}")
