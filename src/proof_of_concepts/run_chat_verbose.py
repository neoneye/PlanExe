"""
Show as much as possible of what is going on.

The POST request, the response.
"""
from src.llm_factory import get_llm
from llama_index.core.llms import ChatMessage
import logging
import sys
import llama_index.core

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

llama_index.core.set_global_handler("simple")

llm = get_llm("deepseek-chat")

messages = [
    ChatMessage(
        role="system", content="You are a pirate with a colorful personality"
    ),
    ChatMessage(role="user", content="What is your name"),
]
chat_response = llm.chat(messages)

print(f"\n\nResponse str\n{chat_response}")
print(f"\n\nResponse repr\n{chat_response.__repr__()}")
print(f"\n\nUSAGE:\n{chat_response.raw.usage}")
