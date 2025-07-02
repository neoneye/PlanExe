"""
Experiments using LlamaIndex's MockLLM.
No use of PlanExe's llm_factory.
No use of Pydantic for structured output.

PROMPT> python -m planexe.proof_of_concepts.run_mockllm
"""
from llama_index.core.llms import MockLLM
from llama_index.core.llms import ChatMessage, MessageRole

llm = MockLLM(
    max_tokens=32,
)

messages = [
    ChatMessage(
        role=MessageRole.USER,
        content="List names of 3 planets in the solar system. Comma separated. No other text.",
    )
]
print("connecting to llm...")
response = llm.chat(messages)
print(f"response:\n{response!r}")
