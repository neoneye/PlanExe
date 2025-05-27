from enum import Enum
from src.llm_factory import get_llm
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler

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
token_counter = TokenCountingHandler()
sllm = llm.as_structured_llm(
    ExtractDetails,
    callback_manager=CallbackManager([token_counter])
)

raw_text_chunks = []
for chunk in sllm.stream_chat(messages):
    if chunk.delta:
        raw_text_chunks.append(chunk.delta)
    if chunk.raw:
        print(f"type of raw: {type(chunk.raw)}")
        print("raw: ", chunk.raw)
        print("Partial object:", chunk.raw.model_dump())

response_str = "".join(raw_text_chunks)
print(f"\n\nFull response str\n{response_str}\n")

print("Token counts:")
print(f"total_llm_token_count: {token_counter.total_llm_token_count}")
print(f"prompt_llm_token_count: {token_counter.prompt_llm_token_count}")
print(f"completion_llm_token_count: {token_counter.completion_llm_token_count}")
print(f"total_embedding_token_count: {token_counter.total_embedding_token_count}")
