"""
Convert the raw json pitch to a markdown document.

PROMPT> python -m src.pitch.convert_pitch_to_markdown
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

logger = logging.getLogger(__name__)

CONVERT_PITCH_TO_MARKDOWN_SYSTEM_PROMPT = """
You are a content formatter designed to transform complex project pitches into compelling Markdown documents.
Your task is to generate a detailed and well-structured document that covers all aspects of the pitch.

# Example of a response

```markdown
# Top Level

## Second Level

Paragraph with text. Use bullet points for lists.
- I'm a bullet point
- Another bullet point
- Yet another bullet point

## Second Level

Lorem ipsum.
```

# Instructions

- **Expand on each section**: For short sections, expand them into multiple paragraphs if necessary to provide a comprehensive overview.
- **Use detailed examples**: If possible, include real-world examples or case studies that demonstrate the effectiveness of the project.
- **Break down complex ideas**: Simplify and break down any complex ideas into understandable points.
- **Enhance with visuals**: Suggest including relevant images, charts, or videos if appropriate to enhance the presentation.
- **Use storytelling techniques**: Incorporate a narrative style where possible to make the pitch more engaging and persuasive.
- Use ONLY the provided text. Do not add external information (website addresses, contact details, dates, etc.).
- Do not remove any sections or section text unless it is irrelevant.
- The reformatted pitch must cover the same topics as the original JSON object.
- Use newlines before and after headings.
- Bold important keywords or phrases, like **very important words**.
- Markdown headings: Use `# Top Level` for the document title. Use `## Second Level` for section titles. Do NOT use more than two levels of headings.
- Don't bold headings or subheadings, since they are already formatted.
- Ensure that each section is expanded and detailed.

"""

@dataclass
class ConvertPitchToMarkdown:
    system_prompt: Optional[str]
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'ConvertPitchToMarkdown':
        """
        Invoke LLM with a json document that is the raw pitch.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid query.")

        system_prompt = CONVERT_PITCH_TO_MARKDOWN_SYSTEM_PROMPT.strip()
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

        raw_content = chat_response.message.content

        cleanedup_markdown = str(raw_content)
        # remove ```markdown from the beginning
        cleanedup_markdown = cleanedup_markdown.replace("```markdown", "")
        # remove ``` from the end
        cleanedup_markdown = cleanedup_markdown.replace("```", "")
        cleanedup_markdown = cleanedup_markdown.strip()

        json_response = {}
        json_response['raw_content'] = raw_content
        json_response['markdown'] = cleanedup_markdown

        result = ConvertPitchToMarkdown(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        logger.debug("CleanupPitch instance created successfully.")
        return result    

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
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

if __name__ == "__main__":
    from src.llm_factory import get_llm

    basepath = os.path.join(os.path.dirname(__file__), 'test_data')

    def load_json(relative_path: str) -> dict:
        path = os.path.join(basepath, relative_path)
        print(f"loading file: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            the_json = json.load(f)
        return the_json

    pitch_json = load_json('lunar_base-pitch.json')

    model_name = "ollama-llama3.1"
    # model_name = "ollama-qwen2.5-coder"
    llm = get_llm(model_name)

    query = format_json_for_use_in_query(pitch_json)
    print(f"Query: {query}")
    result = ConvertPitchToMarkdown.execute(llm, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.response['markdown']}")
