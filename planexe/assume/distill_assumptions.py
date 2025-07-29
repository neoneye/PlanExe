"""
From a list of verbose assumptions, distill the key assumptions, so it can fit within the LLM's token limit.

IDEA: Sometimes the input file has lots of assumptions, but the distilled has none or a few. Important assumptions are getting lost.
This problem occur with this LLM:
"openrouter-paid-gemini-2.0-flash-001"
The llama3.1 has no problems with it.

IDEA: Sometimes it recognizes that the project starts ASAP as an assumption. This is already part of the project description, this is not something new.
How do I suppress this kind of information from the output?

IDEA: If there is a mismatch between the number of assumptions in the input and the output.
Then it's likely that one or more assumptions are getting lost or introduced.
The number of assumptions should be the same in the input and output.
Ideally track the assumptions in the input with a uuid, that stays the same in the output.
If one of the input assumptions gets splitted into 2 assumptions, then the source id should be the same for both.

PROMPT> python -m planexe.assume.distill_assumptions
"""
import json
import time
from datetime import datetime
import logging
from math import ceil
from typing import Optional, Any
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms.llm import LLM
from llama_index.core.llms import ChatMessage, MessageRole

logger = logging.getLogger(__name__)

class AssumptionDetails(BaseModel):
    assumption_list: list[str] = Field(description="List of assumptions")

SYSTEM_PROMPT_1 = """
You are an intelligent **Planning Assistant** specializing in distilling project assumptions for efficient use by planning tools. Your primary goal is to condense a list of verbose assumptions into a concise list of key assumptions that have a significant strategic impact on planning and execution, while ensuring that all core assumptions are captured.

**Your instructions are:**

1.  **Identify All Core Assumptions with Strategic Impact:** Extract all of the most critical assumptions from the given list, focusing on assumptions that have a significant strategic impact on project planning and execution. Ensure that *all* of these types of assumptions are captured:
    - Scope and deliverables
    - Timeline and deadlines
    - Resources needed
    - External constraints
    - Dependencies between tasks
    - Stakeholders and their roles
    - Expected outcomes and success criteria
    - Financial factors (where provided)
    - Operational factors

2.  **Maintain Core Details:**
    *   Include crucial numeric values and any specific data points stated in the original assumptions that are strategically important.
    *   Distill the assumptions to their core details; remove redundant words and ensure the most important aspects are maintained.

3.  **Brevity is Essential:**
    *   Distill each assumption into a single, short, and clear sentence. Aim for each sentence to be approximately 10-15 words, and do not exceed 17 words.
    *   Avoid unnecessary phrases, repetition, and filler words.
    *   Do not add any extra text that is not requested in the output, only return a list of distilled assumptions in JSON.

4.  **JSON Output:**
    *   Output the distilled assumptions into a list in JSON format.
    *   The key should be "assumption_list" and its value is a JSON array of strings.

5.  **Ignore:**
    *   Do not include any information in the response other than the distilled list of assumptions.
    *   Do not comment on the quality or format of the original assumptions.
    *   Do not explain your reasoning.
    *   Do not attempt to add any information that is not provided in the original list of assumptions.

**Example output:**
{
  "assumption_list": [
    "The project will take 3 weeks.",
    "The team consists of 3 people.",
    ...
  ]
}
"""

SYSTEM_PROMPT_2 = """
You are an intelligent **Planning Assistant** specializing in distilling project assumptions for efficient use by planning tools. Your primary goal is to condense a list of verbose assumptions into a concise list of key assumptions that are critical for pre-planning assessment, SWOT analysis, and work breakdown structure (WBS).

**Your instructions are:**

1. **Prioritize Strategic Assumptions:**
   - Extract only the most significant assumptions that have the highest impact on project planning and execution.
   - Focus on assumptions that influence multiple downstream tasks and are essential for decision-making.
   - Emphasize assumptions that, if incorrect, could introduce significant risks or require major project adjustments.

2. **Limit the Number of Assumptions:**
   - Provide no more than **5 key assumptions**.
   - Ensure each assumption is unique and adds distinct value to the planning process.

3. **Ensure Direct Relevance to Planning Tools:**
   - The assumptions should directly support pre-planning assessment, SWOT analysis, and WBS creation.
   - Consider how each assumption feeds into these specific planning activities and contributes to actionable insights.

4. **Maintain Core Details with Strategic Focus:**
   - Include crucial numeric values and specific data points from the original assumptions that are strategically important.
   - Remove redundant or overlapping assumptions to ensure each one is unique and adds distinct value.

5. **Optimize Brevity and Precision:**
   - Distill each assumption into a single, short, and clear sentence.
   - Aim for each sentence to be approximately 10-15 words and do not exceed 17 words.
   - Use precise language to enhance clarity and avoid ambiguity.

6. **JSON Output:**
   - Output the distilled assumptions into a list in JSON format.
   - The key should be "assumption_list" and its value is a JSON array of strings.

7. **Ignore:**
   - Do not include any information in the response other than the distilled list of assumptions.
   - Do not comment on the quality or format of the original assumptions.
   - Do not explain your reasoning.
   - Do not attempt to add any information that is not provided in the original list of assumptions.

**Example output:**
{
  "assumption_list": [
    "The project will take 3 weeks.",
    "The team consists of 3 people.",
    ...
  ]
}
"""

SYSTEM_PROMPT = SYSTEM_PROMPT_1

@dataclass
class DistillAssumptions:
    system_prompt: Optional[str]
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str, **kwargs: Any) -> 'DistillAssumptions':
        """
        Invoke LLM with a bunch of assumptions and distill them.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid query.")

        # Obtain the current year as a string, eg. "1984"
        current_year_int = datetime.now().year
        current_year = str(current_year_int)

        # Replace the placeholder in the system prompt with the current year
        system_prompt = SYSTEM_PROMPT.strip()
        system_prompt = system_prompt.replace("CURRENT_YEAR_PLACEHOLDER", current_year)

        default_args = {
            'system_prompt': system_prompt
        }
        default_args.update(kwargs)

        system_prompt = default_args.get('system_prompt')
        logger.debug(f"System Prompt:\n{system_prompt}")
        if system_prompt and not isinstance(system_prompt, str):
            raise ValueError("Invalid system prompt.")

        chat_message_list = []
        if system_prompt:
            chat_message_list.append(
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=system_prompt,
                )
            )
        
        logger.debug(f"User Prompt:\n{user_prompt}")
        chat_message_user = ChatMessage(
            role=MessageRole.USER,
            content=user_prompt,
        )
        chat_message_list.append(chat_message_user)

        sllm = llm.as_structured_llm(AssumptionDetails)

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

        markdown = cls.convert_to_markdown(chat_response.raw)

        result = DistillAssumptions(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
            markdown=markdown
        )
        logger.debug("DistillAssumptions instance created successfully.")
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

    @staticmethod
    def convert_to_markdown(assumption_details: AssumptionDetails) -> str:
        """
        Convert the raw document details to markdown.
        """
        rows = []

        if len(assumption_details.assumption_list) > 0:
            for assumption in assumption_details.assumption_list:
                rows.append(f"- {assumption}")
        else:
            rows.append("**No distilled assumptions:** It's unusual that a plan has no assumptions. Please check if the input data is contains assumptions. Please report to the developer of PlanExe.")

        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    import os
    import logging
    from planexe.llm_factory import get_llm

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    path_to_assumptions_file = os.path.join(os.path.dirname(__file__), 'test_data', 'assumptions_solar_farm_in_denmark.json')
    with open(path_to_assumptions_file, 'r', encoding='utf-8') as f:
        assumptions_raw_data = f.read()

    plan_prompt = "Establish a solar farm in Denmark."
    query = (
        f"{plan_prompt}\n\n"
        "Today's date:\n2025-Jan-26\n\n"
        "Project start ASAP\n\n"
        f"assumption.json:\n{assumptions_raw_data}"
    )

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("deepseek-chat", max_tokens=8192)

    print(f"Query: {query}")
    result = DistillAssumptions.execute(llm, query)

    print("\n\nResponse:")
    print(json.dumps(result.to_dict(include_system_prompt=False, include_user_prompt=False), indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
