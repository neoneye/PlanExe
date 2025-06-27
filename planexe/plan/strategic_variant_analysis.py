"""
Strategic Variant Analysis (SVA), explore the solution space.

- Identify what key "dials" can be turned to change the outcome of the plan.
- For each dial, identify the possible values.
- With all the permutations of the dials and their values, take 20 random samples.
- 80/20 rule: Identify the most significant 4 samples. Discard the rest.

PROMPT> python -m planexe.plan.strategic_variant_analysis
"""
import os
import json
import time
import logging
from math import ceil
from typing import Optional
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from planexe.markdown_util.fix_bullet_lists import fix_bullet_lists

logger = logging.getLogger(__name__)

class DocumentDetails(BaseModel):
    brainstorm_about_dials: str = Field(
        description="Rationale about what 'dials' really impacts this project. 100 words."
    )
    dial1_name: str = Field(
        description="Name of the 1st dial."
    )
    dial1_values: list[str] = Field(
        description="List of values for the 1st dial."
    )
    dial2_name: str = Field(
        description="Name of the 2nd dial."
    )
    dial2_values: list[str] = Field(
        description="List of values for the 2nd dial."
    )
    dial3_name: str = Field(
        description="Name of the 3nd dial."
    )
    dial3_values: list[str] = Field(
        description="List of values for the 3nd dial."
    )
    summary: str = Field(
        description="Are these dials well picked? Are they well balanced? Are they well thought out? 100 words."
    )

STRATEGIC_VARIANT_ANALYSIS_SYSTEM_PROMPT = """
Your job is to perform a Strategic Variant Analysis (SVA) to explore the solution space.

- Identify what key "dials" can be turned to change the outcome of the plan.
- For each dial, identify the possible values.

After you have identified the dials and corresponding values, your job is over.
Another AI will take over and perform the following steps:
- With all the permutations of the dials and their values, take 20 random samples.
- 80/20 rule: Identify the most significant 4 samples. Discard the rest.
- Remaining are the most promising variants.

Remember: Your output must be valid JSON and nothing else.
"""

@dataclass
class StrategicVariantAnalysis:
    system_prompt: Optional[str]
    user_prompt: str
    response: str
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'StrategicVariantAnalysis':
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        system_prompt = STRATEGIC_VARIANT_ANALYSIS_SYSTEM_PROMPT.strip()
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

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = StrategicVariantAnalysis(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
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
    
if __name__ == "__main__":
    from planexe.llm_factory import get_llm
    from planexe.prompt.prompt_catalog import PromptCatalog

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_simple_plan_prompts()
    prompt_item = prompt_catalog.find("a6bef08b-c768-4616-bc28-7503244eff02")
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    print(f"Query: {query}")
    result = StrategicVariantAnalysis.execute(llm, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))
