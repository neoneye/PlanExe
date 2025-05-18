"""
Create a patch to the document that addresses the problem.

PROMPT> python -m src.refine.solve_problem
"""
import logging
import time
from math import ceil
from pydantic import BaseModel, Field
from llama_index.core.llms.llm import LLM
from llama_index.core.llms import ChatMessage, MessageRole

from src.refine.patch import Patch

logger = logging.getLogger(__name__)

class DocumentDetails(BaseModel):
    rationale: str = Field(
        description="Why this range has to be changed"
    )
    patch: str = Field(
        description="Diff of the old and new content with the SEARCH and REPLACE markers"
    )


MY_SYSTEM_PROMPT = """
You can only modify the `document.md` content found between the <start-of-document> and <end-of-document> markers.

Over multiple refinements, the goal is that the document satisfies the SMART criteria.

In the 'rationale' field, explain the reason for the proposed changes.

The 'patch' field must contain the proposed changes using the following specific patch format. This format indicates the text to *find* in the document and the text to *replace* it with.

<<<<<<< SEARCH
[The exact text currently in the document that needs to be replaced]
=======
[The exact new text that will replace the old text. This section can be empty.]
>>>>>>> REPLACE

Anything outside these specific markers (<<<<<<< SEARCH, =======, >>>>>>> REPLACE) within the 'patch' field content will be ignored. Ensure the content between the markers accurately reflects the FIND and REPLACE text.

"""

DOCUMENT_MARKDOWN = """
# Introduction
placeholder-introduction

# Insights
placeholder-insights

# Conclusion
placeholder-conclusion
"""

MY_USER_PROMPT = """
SMART Criteria:
- S (Specific): Create a concise introductory document defining Artificial General Intelligence (AGI), highlighting its core concept, contrasting it with Narrow AI (ANI), and briefly mentioning its hypothetical status and potential.
- M (Measurable): The document must clearly state a definition of AGI, explicitly mention its difference from ANI, and be between 150 and 250 words in length. It should also be presented as plain text.
- A (Achievable): This is achievable using publicly available information about AGI and current AI concepts.
- R (Relevant): The document serves as the necessary starting content for testing and developing the multi-agent system's document handling and editing capabilities in a realistic (though simple) context.
- T (Time-bound): The document must be created now, before the multi-agent system begins its operational cycle.

file 'document.md':
<start-of-document>
DOCUMENT_MARKDOWN_PLACEHOLDER
<end-of-document>
"""

class SolveProblem:
    def __init__(self, llm: LLM):
        self.llm = llm

    def perform_refinement(self):
        document_markdown = DOCUMENT_MARKDOWN.strip()
        user_prompt = MY_USER_PROMPT.strip()
        user_prompt = user_prompt.replace("DOCUMENT_MARKDOWN_PLACEHOLDER", document_markdown)

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

        # Ensure the patch string from the LLM is correctly extracted and parsed
        # The LLM is expected to put the patch string into the 'patch' field of the Pydantic model
        # The Patch.create method expects the string containing the patch markers
        patch_string_from_llm = chat_response.raw.patch
        
        try:
            patch = Patch.create(patch_string_from_llm)
            print(patch)

            document_markdown_with_patch = patch.apply(document_markdown)
            print("\n--- Patched Document ---")
            print(document_markdown_with_patch)
            print("------------------------")

        except ValueError as e:
             logger.error(f"Failed to apply patch: {e}")
             # Print the raw patch string from the LLM for debugging
             print("\n--- Raw Patch String from LLM (Failed to Parse) ---")
             print(patch_string_from_llm)
             print("---------------------------------------------------")
             raise e


    def run_loop(self, max_iterations: int = 1):
        for i in range(max_iterations):
            logger.info(f"Start iteration {i+1} of {max_iterations}.")
            try:
                self.perform_refinement()
            except Exception as e:
                logger.error(f"Iteration {i+1} failed: {e}")
                # Decide if you want to stop or continue after failure
                # For now, let's stop on failure
                break
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

    instance = SolveProblem(llm)
    instance.run_loop(max_iterations=1)
