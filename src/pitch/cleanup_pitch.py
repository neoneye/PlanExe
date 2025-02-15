"""
Clean up the raw json pitch.

PROMPT> python -m src.pitch.cleanup_pitch
"""
import os
import json
import time
import logging
from math import ceil
from typing import List, Optional
from uuid import uuid4
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms.llm import LLM
from llama_index.core.llms import ChatMessage, MessageRole
from src.format_json_for_use_in_query import format_json_for_use_in_query

logger = logging.getLogger(__name__)

class PrettyProjectPitch(BaseModel):
    markdown_formatted_pitch: str = Field(
        description="Formatted pitch."
    )

SYSTEM_PROMPT = """
You are a highly skilled content formatter, expert at transforming raw text into engaging and visually appealing documents. Your goal is to create a compelling and persuasive project pitch using proper Markdown headings, emojis, and a touch of enthusiasm.

**Instructions:**

1.  **Input:** You will receive a JSON object. This JSON object contains the raw text for a project pitch, organized into sections. The keys of the JSON object represent the section titles, and the values are the text content for that section.

2.  **Detailed Transformation Process:**
    *   **Iterate through each section** in the JSON object. For each section, perform the following steps:

        *   **Create a Compelling Markdown Heading:** Generate a clear, concise, and *enticing* heading for the section using **Markdown heading syntax** (e.g., `# Heading 1`, `## Heading 2`, `### Heading 3`). Choose the appropriate heading level to create a clear visual hierarchy. Use *multiple* relevant emojis in the heading to visually represent the section's theme and grab attention. Place the heading above the original text for that section. Aim for 2-4 emojis per heading, strategically placed for maximum impact.
        *   **Enhance with Emojis:** *Generously* add emojis throughout the text to highlight key points, add visual interest, and convey enthusiasm. Choose emojis that are appropriate for the context and target audience. Use emojis *at the end of sentences* to add emphasis and excitement. Try and add at least 3-5 emojis per section.
        *   **Structure with Bullet Points:** *Actively seek opportunities* to break the text into bulleted lists. If a section contains a list of items, benefits, risks, strategies, features, examples, or any other information that can be easily organized in a list format, *you must* convert it into a bulleted list. Use a checkmark emoji (✅) before each bullet point for positive aspects or completed tasks. Use other emojis to make these bullet points even more visually compelling. Use Markdown list syntax for bullet points.
        *   **Refine the Language:** Rewrite sentences to be more concise, impactful, and persuasive. Use active voice and strong verbs. Maintain the original meaning of the text, but *don't be afraid to add descriptive words and phrases to make the pitch more exciting*.
        *   **Emphasize Key Information:** Use bold text (**) within the paragraphs (but not in the headings, which are already emphasized by being headings) to highlight the *most critical* words, phrases, and figures. Aim to bold 3-5 key phrases per section.
        *   **Maintain the Original Structure:** Ensure that the overall structure and flow of the original document are preserved. The reformatted pitch should cover the same topics and present the information in a logical order.
        *   **Add a Blank Line:** After the heading but before the body text, add a blank line, to insert a newline.

    *   **Output**: Combine the transformed sections into a single, well-formatted string of Markdown.

3.  **Critical Restrictions:**
    *   **ABSOLUTELY NO EXTERNAL INFORMATION!** You must *only* use the text provided in the input JSON. Do not add any information that is not explicitly present in the JSON, even if it seems obvious or relevant. This includes:
        *   **Website Addresses:** If a website is specified using the placeholder "[insert website address here]," *do not* replace it with an actual website address. Leave the placeholder as it is.
        *   **Contact Details:** Do not invent or add any contact information (phone numbers, email addresses, social media links, etc.) unless they are already present in the JSON.
        *   **Dates:** Do not add any dates unless they are explicitly provided in the JSON.
        *   **Other Factual Information:** Stick strictly to the information provided.
    *   **Preserve placeholders**: do not add any content into them, leave them as they are
    *   **Do not remove any sections or section text unless it is irrelevant.**

4.  **Example the `markdown_formatted_pitch`:**

```markdown
# 🚀 Project Title: [Your Project Title] 🚀

## 🌟 Introduction: A Bold Vision for the Future! 🌟

[Reformatted introduction text with emojis and bolding.  End each sentence with an emoji.]

### ✅ Key Benefits: Why You Should Invest! ✅

*   ✅ **Increased productivity:** Get more done, faster! 🚀
*   ✅ **Reduced costs:** Save money and resources! 💰
*   ✅ **Improved collaboration:** Work together seamlessly! 🤝

[Continue formatting each section in a similar manner.]
"""

@dataclass
class CleanupPitch:
    system_prompt: Optional[str]
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'CleanupPitch':
        """
        Invoke LLM with a json document that is the raw pitch.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid query.")


        system_prompt = SYSTEM_PROMPT.strip()
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

        sllm = llm.as_structured_llm(PrettyProjectPitch)

        logger.debug("Starting LLM chat interaction.")
        start_time = time.perf_counter()
        chat_response = sllm.chat(chat_message_list)
        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        try:
            json_response = json.loads(chat_response.message.content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON.", exc_info=True)
            raise ValueError("Invalid JSON response from LLM.") from e

        result = CleanupPitch(
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
    result = CleanupPitch.execute(llm, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.response['markdown_formatted_pitch']}")
