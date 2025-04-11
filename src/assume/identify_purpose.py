"""
Determine what kind of plan is to be conducted.
- **Business:** Profit-Driven, aimed at generating profit.
- **Personal:** Personal stuff, not aimed at generating profit.
- **Other:** Doesn't fit into the above categories.

PROMPT> python -m src.assume.identify_purpose
"""
import time
from math import ceil
import logging
from typing import Optional
from enum import Enum
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class PlanPurpose(str, Enum):
    personal = 'personal'
    business = 'business'
    other = 'other'

class PlanPurposeInfo(BaseModel):
    """
    Identify the purpose of the plan to be performed.
    """
    topic: str = Field(description="The subject of the plan.")
    purpose_detailed: str = Field(
        description="Detailed purpose of the plan, such as: health, healthier habits, product, market trend, strategic planning, project management."
    )
    purpose: PlanPurpose = Field(
        description="Purpose of the plan."
    )

IDENTIFY_PURPOSE_SYSTEM_PROMPT = """
You are an expert analyst specializing in classifying the purpose of plans or analyses based *solely on the provided prompt*. Your task is to categorize provided topics into one of three types: "personal," "business," or "other." Respond ONLY with a valid JSON object containing "topic", "purpose_detailed", and "purpose".

*   **Personal:** Focuses *strictly* on an individual's own goals, well-being, development, finances, health, hobbies, skills, family matters, personal technology choices/setups, or simple personal tasks. Not aimed at organizational goals or profit. **If the prompt explicitly states it's a personal project (e.g., "my hobby," "for my learning"), classify as personal, even if the task is complex.**
    *   *Examples:* Managing personal finances, planning a fitness routine, finding a lost item, watering houseplants, planning a personal vacation, building a custom OS *as a stated hobby*.

*   **Business:** Relates to the planning, strategy, operation, funding, or execution of activities undertaken by **organizations**. This includes companies, non-profits, government agencies, research institutions, or other organized groups. Covers commercial ventures, **large-scale projects (construction, infrastructure, scientific expeditions, historical replicas), program development (social, environmental, public health), initiative design,** strategy, operational planning, logistics, supply chain, marketing (including **content creation like blog posts for promotion**), sales, finance, HR, market analysis, **regulatory compliance strategy**, product development, establishing new ventures (even historical), funding acquisition, or applying business frameworks. The goal is typically organizational success, mission achievement, market positioning, or profit.
    *   *Examples:* Launching a new product, analyzing competitor activity, **planning a city metro line construction**, **developing a funded program to reduce poverty**, **planning a manned mission to establish a moon base**, **designing a pollution monitoring program**, analyzing a company's supply chain, **writing blog posts about tourism attractions**, evaluating the commercial potential of a historical invention, **planning the construction of a historical replica for display/tourism**.

*   **Other:** Topics that are **primarily theoretical, abstract, purely analytical without a specified organizational context, or direct requests for technical implementation (like coding specific functions) detached from a larger plan.** This includes exploring abstract concepts, **creating a report or analysis *without* a stated organizational purpose for it**, designing theoretical simulations, or writing specific code snippets *unless the prompt frames it within a larger business/product strategy*.
    *   *Examples:* Simulating pandemic effects *theoretically*, writing a Python script for a bouncing ball *as a standalone request*, analyzing the philosophical implications of AI, comparing linguistic theories, **creating a general report on microplastics *if no organizational context is given***.

Focus on the *core activity requested* and the *implied actor* (individual vs. organization). Large scale, funding, and infrastructure often imply an organizational actor (`business`).

Example 1:
Input: Improving my public speaking skills for work presentations.
Output: {"topic": "Public speaking skills", "purpose_detailed": "Skills Development", "purpose": "personal"}

Example 2:
Input: Launching a new marketing campaign for our SaaS product.
Output: {"topic": "New marketing campaign", "purpose_detailed": "Marketing Strategy", "purpose": "business"}

Example 3:
Input: Analyze the market potential for lab-grown diamonds in the jewelry industry.
Output: {"topic": "Lab-grown diamond market", "purpose_detailed": "Market Analysis", "purpose": "business"}

Example 4:
Input: Write a function to calculate Fibonacci numbers recursively.
Output: {"topic": "Fibonacci function", "purpose_detailed": "Programming Task", "purpose": "other"}

Example 5:
Input: Plan a program to improve sanitation in rural villages, funded by an international NGO.
Output: {"topic": "Rural sanitation program", "purpose_detailed": "Social Program Planning", "purpose": "business"}

Example 6:
Input: Make a 64bit x86 OS in Rust. This is my hobby project for learning.
Output: {"topic": "Rust OS Development", "purpose_detailed": "Personal Hobby Project", "purpose": "personal"}

Input: Write a blog post reviewing the best hiking trails in the Alps for a travel website.
Output: {"topic": "Hiking trail blog post", "purpose_detailed": "Content Marketing", "purpose": "business"}
"""

@dataclass
class IdentifyPurpose:
    """
    Take a look at the vague description of an idea and determine its purpose.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'IdentifyPurpose':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = IDENTIFY_PURPOSE_SYSTEM_PROMPT.strip()

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

        sllm = llm.as_structured_llm(PlanPurposeInfo)
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

        plan_purpose_instance: PlanPurposeInfo = chat_response.raw
        json_response = plan_purpose_instance.model_dump()
        purpose_value = plan_purpose_instance.purpose.value
        json_response['purpose'] = purpose_value

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        markdown = cls.convert_to_markdown(plan_purpose_instance)

        result = IdentifyPurpose(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
            markdown=markdown
        )
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
    def convert_to_markdown(plan_purpose_info: PlanPurposeInfo) -> str:
        """
        Convert the raw document details to markdown.
        """
        rows = []

        if plan_purpose_info.purpose == PlanPurpose.personal:
            rows.append("This is a personal plan, focused on individual well-being and development.")
        elif plan_purpose_info.purpose == PlanPurpose.business:
            rows.append("This is a business plan, focused on organizational or commercial objectives.")
        elif plan_purpose_info.purpose == PlanPurpose.other:
            rows.append("This plan doesn't clearly fit into personal or business categories.")
        else:
            rows.append(f"Invalid plan purpose. {plan_purpose_info.purpose}")

        rows.append(f"\n**Topic:** {plan_purpose_info.topic}")
        rows.append(f"\n**Detailed Purpose:** {plan_purpose_info.purpose_detailed}")
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from src.prompt.prompt_catalog import PromptCatalog
    from src.llm_factory import get_llm
    from pandas import DataFrame
    from tqdm import tqdm
    import os
    import json

    llm = get_llm("ollama-llama3.1", temperature=0.0)

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_example_swot_prompts()
    # prompt_catalog.load_simple_plan_prompts()
    prompt_items = prompt_catalog.all()

    # Limit the number of prompt items to process
    prompt_items = prompt_items[:3]

    # Create a DataFrame to store the results
    df = DataFrame(columns=['data', 'expected', 'purpose', 'purpose_detail', 'topic', 'duration', 'error', 'status'])
    for prompt_item in prompt_items:
        expected = 'other'
        if 'business' in prompt_item.tags:
            expected = 'business'
        elif 'personal' in prompt_item.tags:
            expected = 'personal'
        new_row = {
            "data": prompt_item.prompt,
            "expected": expected,
            "purpose": None,
            "purpose_detail": None,
            "topic": None,
            "duration": None,
            "error": False,
            "status": "pending"
        }
        # Append row to the dataframe
        df.loc[len(df)] = new_row        

    # Invoke the LLM for each prompt
    count_correct = 0
    count_incorrect = 0
    count_error = 0
    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        data = row['data']
        try:
            identify_purpose = IdentifyPurpose.execute(llm, data)
            json_response = identify_purpose.to_dict(include_metadata=True, include_system_prompt=False, include_user_prompt=False)
            df.at[index, 'purpose'] = json_response['purpose']
            df.at[index, 'purpose_detail'] = json_response['purpose_detailed']
            df.at[index, 'topic'] = json_response['topic']
            df.at[index, 'duration'] = json_response['metadata']['duration']

            if row['expected'] == json_response['purpose']:
                status = "correct"
                count_correct += 1
            else:
                status = "incorrect"
                count_incorrect += 1
            df.at[index, 'status'] = status
        except Exception as e:
            print(f"Error at index {index}: {e}")
            df.at[index, 'error'] = True
            df.at[index, 'status'] = "error"
            count_error += 1
    print(df)
    df.to_csv('plan_purpose.csv', index=False) 

    print(f"count correct: {count_correct}")
    print(f"count incorrect: {count_incorrect}")
    print(f"count error: {count_error}")
