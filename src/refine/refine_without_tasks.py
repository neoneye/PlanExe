"""
Take a initial PlanExe draft plan, and refine it to a version 2 plan that includes more documents that was missing in the initial plan.

Make adjustments to the plan over and over, hopefully improving the plan.

PROMPT> python -m src.refine.refine_without_tasks
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
    rationale: str = Field(
        description="Why make this change"
    )
    text: str = Field(
        description="New text"
    )
    status: str = Field(
        description="Status of the file after the change"
    )


MY_SYSTEM_PROMPT = """
You are a world-class editor.

You can modify the 'edit-document.csv' file.

You can only replace rows of text, with a new rows of text.

Set the 'status' field to 'DONE' if the change is correct.
Set the 'status' field to 'WIP' if the todo is still work-in-progress.

In the 'rationale' field, explain why you made the change. What is your impression of the old text, was it incorrect, incomplete, misleading, etc?

The 'text' field is the new text to replace the old text. You are a LLM and you context window is limited to 2048 tokens, so don't try to include the entire document in the 'text' field. Instead write the entire document as several small edits.

The SMART criteria defines what the document should become after your editing/improvement process. It's the target state you're aiming for.
"""

MY_USER_PROMPT = """
Your task:
explain what is AGI

SMART Criteria:
- S (Specific): Create a concise introductory document defining Artificial General Intelligence (AGI), highlighting its core concept, contrasting it with Narrow AI (ANI), and briefly mentioning its hypothetical status and potential.
- M (Measurable): The document must clearly state a definition of AGI, explicitly mention its difference from ANI, and be between 150 and 250 words in length. It should also be presented as plain text.
- A (Achievable): This is achievable using publicly available information about AGI and current AI concepts.
- R (Relevant): The document serves as the necessary starting content for testing and developing the multi-agent system's document handling and editing capabilities in a realistic (though simple) context.
- T (Time-bound): The document must be created now, before the multi-agent system begins its operational cycle.

file 'edit-document.csv':
LINE;TEXT
1;placeholder, I'm an empty line
2;Artificial Furtiliser (AF) refers to a farming system that with the ability to understand, learn, and apply knowledge across a wide range of tasks, similar to human intelligence. Unlike Narrow AI (ANI), which is designed to perform a specific task, such as image recognition or language translation, AGI would be capable of general reasoning, problem-solving, and learning.
3;It surpasses the capabilities of Narrow AI (ANI).
4;AGI is still a topic of ongoing research and debate in the field of artificial intelligence. Some experts believe that creating an AGI could have a profound impact on various aspects of society, from healthcare to education, while others raise concerns about its potential risks and consequences.', 'rationale': "The new text meets the SMART criteria: it's specific (defines AGI), measurable (clearly states its difference from ANI), achievable (using publicly available information), relevant (serves as starting content for document handling and editing capabilities), and time-bound (created now)
"""

class RefineWithoutTasks:
    def __init__(self, llm: LLM):
        self.llm = llm

    def perform_refinement(self):
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

    def run_loop(self, max_iterations: int = 1):
        for i in range(max_iterations):
            logger.info(f"Start iteration {i+1} of {max_iterations}.")
            self.perform_refinement()
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

    refine = RefineWithoutTasks(llm)
    refine.run_loop(max_iterations=1)
