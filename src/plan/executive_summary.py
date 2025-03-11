"""
One-pager that summarizes the plan.

- The executive summary should always be placed at the beginning of the report.
- It's designed to be read first. Its purpose is to provide a high-level overview of the report's contents so that readers can quickly understand the key findings and recommendations.
- It helps readers decide how to engage with the rest of the report. Knowing the key takeaways upfront allows readers to prioritize which sections they need to read in detail.
- It provides context for the rest of the report. Having a clear understanding of the report's purpose and main findings makes it easier to interpret the details presented in the body of the report.

The primary target audience for the executive summary is senior management, executives, investors, and other key decision-makers. These individuals typically have limited time and need to quickly understand the most important information in the report.

PROMPT> python -m src.plan.executive_summary
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
from src.markdown_util.fix_bullet_lists import fix_bullet_lists
from src.markdown_util.remove_bold_formatting import remove_bold_formatting

logger = logging.getLogger(__name__)

EXECUTIVE_SUMMARY_SYSTEM_PROMPT = """
You are an expert at creating executive summaries from project planning documents. Your task is to convert the input Markdown into a concise, one-page summary that provides a high-level overview of the project's key points. The executive summary should be placed at the beginning of the report and is designed to be read first by senior management, executives, investors, and other key decision-makers.

**Output Requirements:**
- Wrap the output exactly in [START_MARKDOWN] and [END_MARKDOWN] (no text before or after).
- Use only plain Markdown (no bold formatting or other styling).
- Retain headings using only '#' and '##'. Convert any deeper levels to these.
- Use bullet lists with a hyphen and a space.
- Condense paragraphs, remove redundancy, and combine similar sections.
- Preserve key details (e.g., assumptions, risks, recommendations) without summarizing or providing commentary.

**Structure of the Executive Summary:**
1. **Project Overview:** Provide a brief description of the project, its goals, and its significance.
2. **Key Objectives:** List the main objectives of the project in bullet points.
3. **Scope:** Summarize the project's scope, including key activities and deliverables.
4. **Key Risks and Mitigation Strategies:** Highlight the most critical risks and how they will be addressed.
5. **Expected Outcomes:** Describe the anticipated benefits and impacts of the project.
6. **Call to Action:** End with a clear call to action, encouraging stakeholders to engage with the project.

**Tone and Style:**
- Use clear, concise, and professional language.
- Avoid technical jargon and overly complex sentences.
- Focus on the most important information that decision-makers need to know.

**Audience:**
- The primary audience is senior management, executives, investors, and other key decision-makers who have limited time and need to quickly understand the project's value and key takeaways.
"""

@dataclass
class ExecutiveSummary:
    system_prompt: Optional[str]
    user_prompt: str
    response: str
    markdown: str
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'ExecutiveSummary':
        """
        Invoke LLM with a long markdown document that needs an executive summary.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        user_prompt = user_prompt.strip()
        user_prompt = remove_bold_formatting(user_prompt)

        system_prompt = EXECUTIVE_SUMMARY_SYSTEM_PROMPT.strip()
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

        markdown_content = fix_bullet_lists(markdown_content)
        markdown_content = remove_bold_formatting(markdown_content)

        json_response = {}
        json_response['response_content'] = response_content
        json_response['markdown'] = markdown_content

        result = ExecutiveSummary(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            markdown=markdown_content,
            metadata=metadata,
        )
        logger.debug("ExecutiveSummary instance created successfully.")
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

    path = os.path.join(os.path.dirname(__file__), 'test_data', 'shorten_markdown1', 'physical_locations.md')
    with open(path, 'r', encoding='utf-8') as f:
        the_markdown = f.read()

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    query = the_markdown
    input_bytes_count = len(query.encode('utf-8'))
    print(f"Query: {query}")
    result = ExecutiveSummary.execute(llm, query)

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

