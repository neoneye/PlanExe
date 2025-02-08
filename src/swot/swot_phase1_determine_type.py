"""
Determine what kind of SWOT analysis is to be conducted.

PROMPT> python -m src.swot.swot_phase1_determine_type
"""
import time
from math import ceil
import logging
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class SWOTAnalysisTypeEnum(str, Enum):
    personal = 'personal'
    business = 'business'
    other = 'other'

class SWOTAnalysisType(BaseModel):
    """
    Identify what kind of SWOT analysis to be performed.
    """
    topic: str = Field(description="The subject of the SWOT analysis.")
    swot_analysis_type_detailed: str = Field(
        description="Type of SWOT analysis, such as: health, healthier habits, product, market trend, strategic planning, project management."
    )
    swot_analysis_type: SWOTAnalysisTypeEnum = Field(
        description="Type of SWOT analysis."
    )

SYSTEM_PROMPT_IDENTIFY_SWOT_ANALYSIS_TYPE = """
You are an expert analyst specializing in classifying SWOT analysis topics. Your task is to categorize provided topics into one of three types: "personal," "business," or "other."

*   **Personal:** This category includes topics related to individual well-being, personal development, habits, skills, and personal goals. Examples include personal finances, health, time management, and skill development.

*   **Business:** This category includes topics related to organizations, companies, products, services, markets, and business strategies. Examples include launching a new product, improving market share, and analyzing competitor activity.

*   **Other:** This category includes topics that don't clearly fit into either "personal" or "business," such as abstract concepts, societal issues, or general research topics.

Your response should be a JSON object with the following keys: "topic", "swot_analysis_type_detailed" and "swot_analysis_type". The "swot_analysis_type" key should be one of the three enumerated values: "personal", "business" or "other." The "swot_analysis_type_detailed" should be a more specific description of the type of analysis.

Focus on the *subject* of the analysis. A topic about "personal digital organization" is personal, even if the methods used could be applied in a business context.

Example 1:
Input: Improving my public speaking skills.
Output: {"topic": "Public speaking", "swot_analysis_type_detailed": "Skills Development", "swot_analysis_type": "personal"}

Example 2:
Input: Launching a new marketing campaign for our product.
Output: {"topic": "New marketing campaign", "swot_analysis_type_detailed": "Marketing Strategy", "swot_analysis_type": "business"}

Example 3:
Input: Which Linux distribution is best for a software developer like me?
Output: {"topic": "Linux and development", "swot_analysis_type_detailed": "Personal Software Setup", "swot_analysis_type": "personal"}
"""

def swot_phase1_determine_type(llm: LLM, user_prompt: str) -> dict:
    """
    Invoke LLM to identify what kind of SWOT analysis is to be conducted.
    """
    if not isinstance(llm, LLM):
        raise ValueError("Invalid LLM instance.")
    if not isinstance(user_prompt, str):
        raise ValueError("Invalid user_prompt.")

    system_prompt = SYSTEM_PROMPT_IDENTIFY_SWOT_ANALYSIS_TYPE.strip()

    logger.debug(f"System Prompt:\n{system_prompt}")
    logger.debug(f"User Prompt:\n{user_prompt}")

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

    sllm = llm.as_structured_llm(SWOTAnalysisType)
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

    swot_analysis_type_instance: SWOTAnalysisType = chat_response.raw
    json_response = swot_analysis_type_instance.model_dump()
    type_value = swot_analysis_type_instance.swot_analysis_type.value
    json_response['swot_analysis_type'] = type_value

    metadata = dict(llm.metadata)
    metadata["llm_classname"] = llm.class_name()
    metadata["duration"] = duration
    metadata["response_byte_count"] = response_byte_count
    json_response['metadata'] = metadata
    return json_response

if __name__ == "__main__":
    from src.prompt.prompt_catalog import PromptCatalog
    from src.llm_factory import get_llm
    from pandas import DataFrame
    from tqdm import tqdm
    import os
    import json

    llm = get_llm("ollama-llama3.1", temperature=0.0)

    prompt_catalog = PromptCatalog()
    prompt_catalog.load(os.path.join(os.path.dirname(__file__), 'data', 'example_swot_prompt.jsonl'))
    prompt_items = prompt_catalog.all()

    # Limit the number of prompt items to process
    prompt_items = prompt_items[:3]

    # Create a DataFrame to store the results
    df = DataFrame(columns=['data', 'type', 'type_detail', 'topic', 'duration', 'error'])
    for prompt_item in prompt_items:
        new_row = {
            "data": prompt_item.prompt,
            "type": None,
            "type_detail": None,
            "topic": None,
            "duration": None,
            "error": False
        }
        # Append row to the dataframe
        df.loc[len(df)] = new_row        

    # Invoke the LLM for each prompt
    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        data = row['data']
        try:
            json_response = swot_phase1_determine_type(llm, data)
            # print(json.dumps(json_response, indent=2))
            df.at[index, 'type'] = json_response['swot_analysis_type']
            df.at[index, 'type_detail'] = json_response['swot_analysis_type_detailed']
            df.at[index, 'topic'] = json_response['topic']
            df.at[index, 'duration'] = json_response['metadata']['duration']
        except Exception as e:
            print(f"Error at index {index}: {e}")
            df.at[index, 'error'] = True

    print(df)
    df.to_csv('swot_analysis_type.csv', index=False)
