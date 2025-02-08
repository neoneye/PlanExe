"""
Exercise the prompt caching mechanism. 

The CSV file is one message. 
The query is another message.

The server responds with a 'usage' dictionary containing stats.
CompletionUsage(completion_tokens=120, prompt_tokens=1639, total_tokens=1759, completion_tokens_details=None, prompt_tokens_details=PromptTokensDetails(audio_tokens=None, cached_tokens=0), prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=1639)
CompletionUsage(completion_tokens=489, prompt_tokens=1631, total_tokens=2120, completion_tokens_details=None, prompt_tokens_details=PromptTokensDetails(audio_tokens=None, cached_tokens=1600), prompt_cache_hit_tokens=1600, prompt_cache_miss_tokens=31)
CompletionUsage(completion_tokens=59, prompt_tokens=1630, total_tokens=1689, completion_tokens_details=None, prompt_tokens_details=PromptTokensDetails(audio_tokens=None, cached_tokens=1600), prompt_cache_hit_tokens=1600, prompt_cache_miss_tokens=30)
CompletionUsage(completion_tokens=1224, prompt_tokens=1632, total_tokens=2856, completion_tokens_details=None, prompt_tokens_details=PromptTokensDetails(audio_tokens=None, cached_tokens=1600), prompt_cache_hit_tokens=1600, prompt_cache_miss_tokens=32)

The first row, is a full cache miss.
The following requests are cache hits.
"""
import os
from src.llm_factory import get_llm
from llama_index.core.llms import ChatMessage

llm = get_llm("deepseek-chat")

path_csv = os.path.join(os.path.dirname(__file__), '..', 'wbs_table_for_cost_estimation', 'test_data', 'wbs_table.csv')
with open(path_csv, 'r') as f:
    data_csv = f.read()

messages_static = [
    ChatMessage(
        role="system", content="You are a CSV file expert. I have a CSV file that I need help with."
    ),
    ChatMessage(role="user", content=data_csv)
]

def run_query(query: str):
    messages = messages_static + [
        ChatMessage(role="user", content=query)
    ]
    chat_response = llm.chat(messages)

    print(f"\n\nResponse str\n{chat_response}")
    print(f"\n\nResponse repr\n{chat_response.__repr__()}")
    print(f"\n\nUSAGE:\n{chat_response.raw.usage}")

run_query("I need to know the number of rows and columns in this CSV file.")
run_query("What kind of data is this?")
run_query("What are the column names?")
run_query("Extract all the uuids.")
