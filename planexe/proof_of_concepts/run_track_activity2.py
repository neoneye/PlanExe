"""
Usage:
python -m planexe.proof_of_concepts.run_track_activity2
"""
import json
import traceback
import logging
from datetime import datetime
from enum import Enum
from planexe.llm_factory import get_llm
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.instrumentation import get_dispatcher
from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler
from llama_index.core.instrumentation.events.llm import LLMChatStartEvent, LLMChatEndEvent
from llama_index.core.instrumentation.dispatcher import instrument_tags

logger = logging.getLogger(__name__)

class TrackActivity(BaseEventHandler):
    model_config = {'extra': 'allow'}
    
    def __init__(self, jsonl_file_path: str, write_to_logger: bool = False):
        super().__init__()
        self.jsonl_file_path = jsonl_file_path
        self.write_to_logger = write_to_logger
    
    @classmethod
    def class_name(cls) -> str:
        return "TrackActivity"

    def handle(self, event):
        if isinstance(event, (LLMChatStartEvent, LLMChatEndEvent)):
            # Create event record with timestamp and backtrace
            event_record = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event.__class__.__name__,
                "event_data": json.loads(event.model_dump_json()),
                "backtrace": traceback.format_stack()
            }
            
            # Append to JSONL file
            with open(self.jsonl_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event_record) + '\n')
            
            # Write to logger if enabled
            if self.write_to_logger:
                logger.info(f"{event.__class__.__name__}: {event!r}")


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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

jsonl_file_path = "activity_log.jsonl"

root = get_dispatcher()
root.add_event_handler(TrackActivity(jsonl_file_path=jsonl_file_path, write_to_logger=True))

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
    response = sllm.chat(messages)
    print(f"response:\n{response!r}")
