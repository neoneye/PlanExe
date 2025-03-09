"""
Shorten the long consolidated assumptions to a shorter markdown document.

PROMPT> python -m src.assume.shorten_assumptions_markdown
"""
import os
import json
import time
import logging
from math import ceil
from typing import Optional
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from llama_index.core.llms import ChatMessage, MessageRole
from src.format_json_for_use_in_query import format_json_for_use_in_query
from src.markdown_util.fix_bullet_lists import fix_bullet_lists

logger = logging.getLogger(__name__)

SHORTEN_ASSUMPTIONS_MARKDOWN_SYSTEM_PROMPT = """
You are a content formatter designed to transform project markdown document into a shorter Markdown document. Your ONLY task is to generate and simplify the Markdown document itself, and NOTHING ELSE.

# Output Requirements:
- ABSOLUTELY NO INTRODUCTORY OR CONCLUDING TEXT. Do NOT add any extra sentences or paragraphs before or after the Markdown document.
- Enclose the ENTIRE Markdown document within the following delimiters:
    - **Start Delimiter:** [START_MARKDOWN]
    - **End DelIMITER:** [END_MARKDOWN]
- Use ONLY the provided text. Do NOT add any external information.

# Markdown Formatting Instructions:
- **Headings:** Use only two levels of headings:
    - Top-level heading for the document title: `# Top Level Heading`
    - Second-level headings for section titles: `## Section Title`
    - DO NOT use any heading levels beyond these two.
- **Document Structure:**
    - The input is markdown and may contain multiple topics.
    - Do not invent or add sections that are not referenced in the input.
    - If the input text is messy, then make it more readable.
    - If the input text contains redundant info needlessly repeated, then remove the redundancy.
- **Lists:** Format lists with Markdown bullet points using a hyphen followed by a space:
    ```markdown
    - Item 1
    - Item 2
    - Item 3
    ```
- **Strategic Bolding:** Bold key project elements, critical actions, and desired outcomes to enhance scannability. For example, bold terms such as **innovation**, **efficiency**, **sustainability**, and **collaboration**. Ensure that each section contains at least one bolded key term where applicable.
- **Expansion:** Expand on the provided content with additional explanatory paragraphs where needed, but do NOT add information that is not present in the input.
- **Delimiters Enforcement:** Ensure that the entire Markdown document is wrapped exactly within [START_MARKDOWN] and [END_MARKDOWN] with no additional text outside these delimiters.
- Ensure that all topics present in the input JSON are covered and organized in a clear, readable format.
"""

@dataclass
class ShortenAssumptionsMarkdown:
    system_prompt: Optional[str]
    user_prompt: str
    response: str
    markdown: str
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'ShortenAssumptionsMarkdown':
        """
        Invoke LLM with a json document that is the raw pitch.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid query.")

        system_prompt = SHORTEN_ASSUMPTIONS_MARKDOWN_SYSTEM_PROMPT.strip()
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
        
        logger.debug(f"User Prompt:\n{user_prompt}")

        logger.debug("Starting LLM chat interaction.")
        start_time = time.perf_counter()
        chat_response = llm.chat(chat_message_list)
        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        response_content = chat_response.message.content

        start_delimiter = "[START_MARKDOWN]"
        end_delimiter = "[END_MARKDOWN]"

        start_index = response_content.find(start_delimiter)
        end_index = response_content.find(end_delimiter)

        if start_index != -1 and end_index != -1:
            markdown_content = response_content[start_index + len(start_delimiter):end_index].strip()
        else:
            markdown_content = response_content  # Use the entire content if delimiters are missing
            logger.warning("Output delimiters not found in LLM response.")

        # The bullet lists are supposed to be preceded by 2 newlines. 
        # However often there is just 1 newline. 
        # This fix makes sure there are 2 newlines before bullet lists.
        markdown_content = fix_bullet_lists(markdown_content)

        json_response = {}
        json_response['response_content'] = response_content
        json_response['markdown'] = markdown_content

        result = ShortenAssumptionsMarkdown(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            markdown=markdown_content,
            metadata=metadata,
        )
        logger.debug("CleanupPitch instance created successfully.")
        return result    

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        d['markdown'] = self.markdown
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

    def save_markdown(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.markdown)
    
if __name__ == "__main__":
    from src.llm_factory import get_llm

    path = os.path.join(os.path.dirname(__file__), 'test_data', 'shorten_assumptions_markdown1', 'consolidate_assumptions.md')
    with open(path, 'r', encoding='utf-8') as f:
        the_markdown = f.read()

    model_name = "ollama-llama3.1"
    # model_name = "ollama-qwen2.5-coder"
    llm = get_llm(model_name)

    query = the_markdown
    input_bytes_count = len(query.encode('utf-8'))
    print(f"Query: {query}")
    result = ShortenAssumptionsMarkdown.execute(llm, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")

    output_bytes_count = len(result.markdown.encode('utf-8'))
    print(f"\n\nInput bytes count: {input_bytes_count}")
    print(f"Output bytes count: {output_bytes_count}")
    bytes_saved = input_bytes_count - output_bytes_count
    print(f"Bytes saved: {bytes_saved}")
    print(f"Percentage saved: {bytes_saved / input_bytes_count * 100:.2f}%")

