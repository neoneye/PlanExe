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

CONVERT_PITCH_TO_MARKDOWN_SYSTEM_PROMPT_1 = """
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

CONVERT_PITCH_TO_MARKDOWN_SYSTEM_PROMPT_2 = """
You are a content formatter designed to transform project pitches into compelling and easily scannable Markdown documents. Your ONLY task is to generate the Markdown document itself, and NOTHING ELSE.

# Output Requirements:

-   **ABSOLUTELY NO INTRODUCTORY OR CONCLUDING TEXT.** Do NOT add any sentences or paragraphs before or after the Markdown document. Your output should consist *EXCLUSIVELY* of the Markdown content.
-   **Use OUTPUT DELIMITERS:** Enclose the ENTIRE Markdown document within the following delimiters:
    -   **Start Delimiter:** `[START_MARKDOWN]`
    -   **End Delimiter:** `[END_MARKDOWN]`
-   **Follow ALL Formatting Instructions (See Below).**

# Markdown Formatting Instructions (High Priority):

-   **Headings:** Use standard Markdown heading syntax:
    -   Top-level heading (document title): `# Top Level Heading`
    -   Second-level headings (section titles): `## Second Level Heading`
    -   **DO NOT USE "UNDERLINE-STYLE" HEADINGS** (e.g., "Heading\n-------")
-   **Lists:** Use Markdown bullet points (`-`) for lists:
    ```markdown
    - Item 1
    - Item 2
    - Item 3
    ```
-   **Strategic Bolding:** Your #1 Goal is to make the document EASY TO SCAN and UNDERSTAND AT A GLANCE. Imagine someone quickly scanning the document: **THE BOLDED WORDS SHOULD TELL A COMPELLING STORY ON THEIR OWN.**
    -   **Apply Bolding Strategically:**
        1.  **Core Project Elements (High Priority):** ALWAYS bold the words that represent the fundamental ELEMENTS of the project itself.
        2.  **Key Actions & Outcomes (High Priority):** ALWAYS bold the words that describe the KEY ACTIONS and DESIRED OUTCOMES of the project.
        3.  **Key Benefits & Value Propositions (Medium Priority):** Bold words and phrases that emphasize the DIRECT BENEFITS and specific VALUE the project offers.
    -   **Bolding Style Guidelines:** Be Precise, Prioritize Nouns and Verbs, Aim for Scannability, and Maintain Balance.
    -   **What to AVOID:** Do NOT bold headings, articles, prepositions, or long strings of words.

# Example Markdown Document:

```markdown
# Project Title

## Section 1: Introduction

This section provides an overview of the project. Key aspects include **innovation**, **sustainability**, and **impact**.

- Benefit 1: Increased efficiency
- Benefit 2: Reduced costs
- Benefit 3: Enhanced security

## Section 2: Goals and Objectives

Our primary goal is to **achieve significant results** in a timely manner.

This project will **transform the industry** and **unlock new opportunities**.
content_copy
download
Use code with caution.
Python
Other Formatting Instructions (Secondary Importance)

Expand on each section: For short sections, expand them into multiple paragraphs if necessary.

Use detailed examples: Include real-world examples (without confidential information).

Break down complex ideas: Simplify ideas into understandable points.

Enhance with visuals: Suggest relevant images (without specific URLs).

Use storytelling techniques: Incorporate a narrative style.

Verb Enhancement: Replace weak verbs with stronger alternatives.

General Restrictions

Use ONLY the provided text. Do NOT add external information.

Do not remove any sections unless irrelevant.

The reformatted pitch must cover the same topics.

Use newlines before and after headings.

Ensure each section is detailed.
"""

CONVERT_PITCH_TO_MARKDOWN_SYSTEM_PROMPT_3 = """
You are a content formatter. Your task is to transform a project pitch into a well-structured Markdown document.

# Instructions:

1.  **Create a Markdown Document:** Generate a Markdown document with the following sections, using the provided text:
    -   Top-level heading (document title)
    -   Introduction
    -   Project Overview
    -   Goals and Objectives
    -   Risks and Mitigation Strategies
    -   Metrics for Success
    -   Stakeholder Benefits
    -   Ethical Considerations
    -   Collaboration Opportunities
    -   Long-term Vision

2.  **Use Two-Level Headings:**
    -   Use `# Top Level Heading` for the document title.
    -   Use `## Second Level Heading` for all section titles.
    -   **DO NOT use more than two levels of headings (no `###` or deeper).**

3.  **Use ONLY the provided text.** Do not add external information.

4.  **Enclose the ENTIRE Markdown document** within `[START_MARKDOWN]` and `[END_MARKDOWN]` delimiters.
"""

CONVERT_PITCH_TO_MARKDOWN_SYSTEM_PROMPT_4 = """
You are a content formatter. Your task is to transform a project pitch into a well-structured Markdown document.

# Instructions:

1.  **Create a Markdown Document:** Generate a Markdown document with the following sections, using the provided text:
    -   Top-level heading (document title)
    -   Introduction
    -   Project Overview
    -   Goals and Objectives
    -   Risks and Mitigation Strategies
    -   Metrics for Success
    -   Stakeholder Benefits
    -   Ethical Considerations
    -   Collaboration Opportunities
    -   Long-term Vision

2.  **Use Two-Level Headings:**
    -   Use `# Top Level Heading` for the document title.
    -   Use `## Second Level Heading` for all section titles.
    -   **DO NOT use underline style headings.**

3.  **Format Lists Correctly:** When creating lists, ensure that the list items are properly formatted with bullet points and have adequate spacing. Ensure that your bullet points are followed by a space. Here's how to format a list in Markdown:

    ```markdown
    - Item 1
    - Item 2
    - Item 3
    ```

    Make sure there's a space between the bullet point (`-`) and the start of the list item's text.

4.  **Use ONLY the provided text.** Do not add external information.

5.  **Enclose the ENTIRE Markdown document** within `[START_MARKDOWN]` and `[END_MARKDOWN]` delimiters.
"""

CONVERT_PITCH_TO_MARKDOWN_SYSTEM_PROMPT = CONVERT_PITCH_TO_MARKDOWN_SYSTEM_PROMPT_1

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

        # remove ```markdown from the beginning
        markdown_content = markdown_content.replace("```markdown", "")
        # remove ``` from the end
        markdown_content = markdown_content.replace("```", "")

        json_response = {}
        json_response['response_content'] = response_content
        json_response['markdown'] = markdown_content

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
