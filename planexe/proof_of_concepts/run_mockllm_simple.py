"""
Experiments using LlamaIndex's MockLLM.
No use of PlanExe's llm_factory.
No use of Pydantic for structured output.

PROMPT> python -m planexe.proof_of_concepts.run_mockllm_simple
"""
from llama_index.core.llms import MockLLM, ChatMessage, MessageRole

llm = MockLLM(
    max_tokens=10,
)

messages = [
    ChatMessage(
        role=MessageRole.USER,
        content="List names of 3 planets in the solar system. Comma separated. No other text.",
    )
]
response = llm.chat(messages)
print(f"response:\n{response!r}")
