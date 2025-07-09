"""
Strategic Variant Analysis (SVA), explore the solution space.

- Identify what key "dials" can be turned to change the outcome of the plan.
- For each dial, identify the possible values.
- With all the permutations of the dials and their values, take 20 random samples.
- 80/20 rule: Identify the most significant 4 samples. Discard the rest.

PROMPT> python -m planexe.plan.strategic_variant_analysis8020
"""
import json
import time
import logging
from math import ceil
from typing import Optional
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole

logger = logging.getLogger(__name__)

class Dial(BaseModel):
    dial_index: int = Field(
        description="Index of this dial."
    )
    name: str = Field(
        description="Name of this dial."
    )
    values: list[str] = Field(
        description="2-5 values for this dial."
    )
    is_primary: bool = Field(
        description="True if this a primary dial. False if this is a secondary dial."
    )
    out_of_the_box: str = Field(
        description="Suggest yet another value. Use 20 words to describe the value."
    )

class DocumentDetails(BaseModel):
    strategic_rationale: str = Field(
        description="A concise strategic analysis (around 100 words) of the project's core tensions and trade-offs. This rationale must JUSTIFY why the selected dials are the most critical levers for decision-making. For example, explain how the chosen dials navigate the fundamental conflicts between speed, cost, scope, and quality."
    )
    dials: list[Dial] = Field(
        description="Propose 20 dials."
    )
    summary: str = Field(
        description="Are these dials well picked? Are they well balanced? Are they well thought out? Point out flaws. 100 words."
    )

STRATEGIC_VARIANT_ANALYSIS_SYSTEM_PROMPT = """
Your job is to perform a Strategic Variant Analysis (SVA) by first deeply analyzing a project's core strategic tensions, and then identifying the dials that a planner can use to navigate these tensions.

**Follow this three-step reasoning process:**

**Step 1: Analyze the Core Tensions.**
Before selecting any dials, first analyze the fundamental trade-offs inherent in the project description. Is the main conflict between speed and quality? Is it between pursuing a safe, proven approach versus investing in high-risk, next-generation R&D? Is it about managing a fixed budget versus achieving an ambitious scope? Your analysis of these tensions is the most important part of your task.

**Step 2: Derive the Primary Dials from Your Analysis.**
Based on the core tensions you identified, propose 10 primary dials. These dials represent the most critical, high-level strategic choices. Each dial must be a powerful lever that cannot be easily replaced or inferred by another dial. Review your chosen dials to ensure they are independent and not redundant.

A strategic dial is an **INPUT DECISION** about resource allocation, primary objective (the 'why'), risk appetite, or implementation model (the 'how'). It is NOT a technical outcome (e.g., 'efficiency %') or the name of a trade-off itself (e.g., 'Cost vs. Quality'). The VALUES for each dial must be descriptive strategic choices.

**CRITICAL:** Your dials MUST address the project's **primary constraints.** Look for any specific figures, resources, timelines, or mandatory goals mentioned in the user's text and ensure your dials provide a way to manage them. If a project requirement is stated as a fact, it is a constraint, not a dial.

**EXAMPLE for a new product launch project:**
- **GOOD DIAL (INPUT DECISION):** "Go-to-Market Strategy" with values: ["Target early adopters in a niche market", "Broad launch targeting the mass market", "Partner-led distribution"]
- **BAD DIAL (OUTCOME):** "Market Share Percentage"
- **BAD DIAL (TENSION):** "Reach vs. Budget"
- **BAD DIAL (CONSTRAINT):** "Product Name" (if the name is already decided and stated in the prompt)

**Step 3: Propose Secondary Dials.**
After defining the primary dials, propose 10 secondary dials. These should focus on more granular operational policies, implementation details, or secondary project goals that are subordinate to the primary strategic choices.

**Final Output:**
Assemble your reasoning and the dials into the required JSON format.
- The 'strategic_rationale' field must contain your analysis of the core tensions from Step 1 and justify why your chosen primary dials are the most critical levers.
- In the 'summary' field, you are required to **critically evaluate your own proposed dials.** Point out at least one potential weakness, flaw, or redundancy in your list and explain why it might be problematic. This is a test of your self-assessment capability.
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
    # prompt_item = prompt_catalog.find("a6bef08b-c768-4616-bc28-7503244eff02")
    prompt_item = prompt_catalog.find("19dc0718-3df7-48e3-b06d-e2c664ecc07d")
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    model_name = "ollama-llama3.1"
    # model_name = "openrouter-paid-gemini-2.0-flash-001"
    # model_name = "openrouter-paid-qwen3-30b-a3b"
    llm = get_llm(model_name)

    print(f"Query: {query}")
    result = StrategicVariantAnalysis.execute(llm, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))
