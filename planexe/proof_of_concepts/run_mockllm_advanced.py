"""
Experiments using LlamaIndex's MockLLM.
No use of PlanExe's llm_factory.
No use of Pydantic for structured output.

PROMPT> python -m planexe.proof_of_concepts.run_mockllm_advanced
"""
from llama_index.core.llms import MockLLM, ChatMessage, MessageRole
import itertools

class CustomMockLLM(MockLLM):
    def __init__(self, responses=None, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'responses', responses or ["Mock response"])
        object.__setattr__(self, 'response_cycle', itertools.cycle(self.responses))

    def _generate_text(self, length: int) -> str:
        return next(self.response_cycle)

llm = CustomMockLLM(
    max_tokens=10,
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
