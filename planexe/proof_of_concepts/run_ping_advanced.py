"""
Ping the LLM to check if it is running.

PROMPT> python -m planexe.proof_of_concepts.run_ping_advanced
"""
from planexe.llm_factory import get_llm
from llama_index.core.llms import ChatMessage
import json
from pydantic import BaseModel
from llama_index.core.llms import ChatMessage, MessageRole

model = "ollama-llama3.1"

llm = get_llm(model)

user_prompt = "location=unspecified, eventcount=8, weather=rainy, role=agent, state=empty, name=Simon"

PING_SYSTEM_PROMPT = """
You are an expert at extracting specific details from unstructured data and mapping them to predefined fields. Your task is to identify and extract the values related to weather, event_count, and state from the input data, and then assign those values to the corresponding fields in a Python dictionary.

Even if the labels in the input data are slightly different from the field names, you should use your understanding of the data to map the values correctly. For example, "eventcnt" should be mapped to the "event_count" field.

Example Input:
age=77, eventcount=5, id=1809246, climate=cold, role=freighter, status=active, name=Ripley, location=Nostromo

Example Output:
{'weather': 'cold', 'count': '5', 'state': 'active'}

Example Input:
name=Bob, location=Paris, attendees=100, condition=hot, state=finish

Example Output:
{'weather': 'hot', 'count': '100', 'state': 'finish'}
"""

class ExtractDetails(BaseModel):
    weather: str = "sunshine"
    count: str = "999"
    state: str = "start"

system_prompt = PING_SYSTEM_PROMPT.strip()

chat_message_list = [
    ChatMessage(
        role=MessageRole.SYSTEM,
        content=system_prompt,
    ),
    ChatMessage(
        role=MessageRole.USER,
        content=user_prompt,
    )
]
sllm = llm.as_structured_llm(ExtractDetails)
chat_response = sllm.chat(chat_message_list)

raw = chat_response.raw
#print(f"raw:\n{raw}\n\n")

json_data = raw.model_dump()
print(json.dumps(json_data, indent=2))

