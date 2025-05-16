"""
Take a initial PlanExe draft plan, and refine it to a version 2 plan that includes more documents that was missing in the initial plan.

Make adjustments to the plan over and over, hopefully improving the plan.

PROMPT> python -m src.self_improve.self_improve_with_tasks
"""
import logging
import time
from math import ceil
from pydantic import BaseModel, Field
from llama_index.core.llms.llm import LLM
from llama_index.core.llms import ChatMessage, MessageRole

logger = logging.getLogger(__name__)

class DocumentDetails(BaseModel):
    range_start: int = Field(
        description="Line number where the change starts"
    )
    range_end: int = Field(
        description="Line number where the change ends"
    )
    text: str = Field(
        description="New text"
    )
    rationale: str = Field(
        description="Why make this change"
    )
    status: str = Field(
        description="Status of the file after the change"
    )


MY_SYSTEM_PROMPT = """
You are a world-class editor.

The 'todo-list.csv' file contains a list of tasks.
You job is to complete the task with status 'WIP' (work-in-progress).
Start from the top of the list and work your way down.

You can modify the 'edit-document.csv' file.

You can only replace rows of text, with a new rows of text.

Set the 'status' field to 'DONE' if the change is correct.
Set the 'status' field to 'WIP' if the todo is still work-in-progress.
"""

MY_USER_PROMPT = """
file 'todo-list.csv':
STATUS;TASK DESCRIPTION
DONE;initialization
WIP;explain what is AGI in 50 words
PENDING;check that the explanation is correct

file 'edit-document.csv':
LINE;TEXT
1;placeholder, I'm an empty line
2;placeholder, I'm an empty line
3;placeholder, I'm an empty line
"""

class SelfImprove:
    def __init__(self, llm: LLM):
        self.llm = llm

    def perform_self_improvement(self):
        user_prompt = MY_USER_PROMPT.strip()

        system_prompt = MY_SYSTEM_PROMPT.strip()

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

        sllm = llm.as_structured_llm(DocumentDetails)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        json_response = chat_response.raw.model_dump()
        print(json_response)

    def run_self_improvement_loop(self, max_iterations: int = 1):
        for i in range(max_iterations):
            logger.info(f"Start iteration {i+1} of {max_iterations}.")
            self.perform_self_improvement()
            logger.info(f"End iteration {i+1} of {max_iterations}.")

if __name__ == "__main__":
    import logging
    from src.llm_factory import get_llm

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    llm = get_llm("ollama-llama3.1")

    self_improve = SelfImprove(llm)
    self_improve.run_self_improvement_loop(max_iterations=1)
