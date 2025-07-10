"""
Strategic Variant Analysis (SVA), explore the solution space.

Step 1:
- Brainstorm what key "dials" can be turned to change the outcome of the plan. (Identifies 20 dials, the LLM takes a long time to do this, and it often looses focus.)
- For each dial, identify the possible values.

Step 2:
- moving from a brainstormed list to a focused set of strategic levers.
- Applying the 80/20 rule here means finding the ~20% of dials (the "vital few," i.e., your 4-5 most significant) that will dictate ~80% of the project's strategic outcome. This is a curation process based on strategic importance, not random sampling.

Step 3:
- With all the permutations of the dials and their values, take 20 random samples.
- 80/20 rule: Identify the most significant 4 samples. Discard the rest.

PROMPT> python -m planexe.strategic_variant_analysis.sva_brainstorm_dials
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
from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

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
    review_dial: str = Field(
        description="Did you forget any important values? Or is this too weak a dial? 30 words."
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
Your job is to perform a Strategic Variant Analysis (SVA) by identifying the critical "dials" a planner can turn to shape a project's outcome. You must follow a strict set of rules and a step-by-step process.

# Core Principles of a Strategic Dial

You MUST follow these rules when creating dials.

## Rule #1: Dials are INPUTS, not OUTCOMES (KPIs)
A dial is a strategic INPUT choice that a planner makes. It is NOT a desired OUTCOME, target, or Key Performance Indicator (KPI).
- **ANALOGY:** A dial is the **oven temperature** you set (an input decision). It is NOT how **well-cooked the cake is** (an outcome).
- **GOOD DIAL (INPUT):** "R&D Investment Strategy" with values like "Focus on high-risk/high-reward tech" vs. "Focus on maturing proven tech."
- **BAD DIAL (OUTCOME/KPI):** "Innovation Success Rate" with values like "90% success," "70% success."

## Rule #2: Respect all Constraints
A constraint is a fact or requirement from the project description that is NOT negotiable.
- **CRITICAL:** Offering a choice that violates a stated constraint is a major error.
- **EXAMPLE:** If a project is mandated to be an "iOS mobile app," a dial offering an "Android version" is invalid.

## Rule #3: Prioritize Foundational, Independent Dials
- **PRIMARY DIALS:** Primary dials should be the 3-5 most foundational choices that shape the entire project (e.g., core risk posture, budget philosophy, IP strategy).
- **REDUNDANCY:** Avoid creating multiple dials for the same core choice. For example, 'IP Strategy' and 'Knowledge Sharing Protocol' are likely part of the same strategic decision.
- **AVOID LAZY VALUES:** Do not use vague values like "Hybrid" or false dichotomies like "Proactive vs. Reactive." If a hybrid approach is an option, describe it, e.g., "Hybrid: Core R&D in-house, partner on non-core tech."

# Your Task: Step-by-Step Instructions

**Step 1: Analyze Core Tensions**
Deeply analyze the project's fundamental trade-offs (e.g., speed vs. quality, risk vs. budget). Your analysis will become the `strategic_rationale`.

**Step 2: Propose 20 Dials**
Create a list of exactly 20 dials according to the rules above. For each dial, provide:
- `dial_index`: A unique integer index starting from 1.
- `name`: A clear, concise name for the INPUT DECISION.
- `values`: 2-4 distinct, descriptive strategic choices.
- `review_dial`: **CRITICAL SELF-ASSESSMENT.** Briefly justify why this is a valid input dial and not an outcome/KPI. Mention a potential weakness if you see one.

**Step 3: Write the Final Summary**
In the `summary` field, critically evaluate your entire list of 20 dials. Identify the SINGLE most significant flaw in your own output (e.g., a major redundancy, a missing critical dial like budget or timeline) and explain why it is a problem. This is a test of your self-assessment.
"""

@dataclass
class SVABrainstormDials:
    system_prompt: Optional[str]
    user_prompt: str
    response: str
    metadata: dict

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str) -> 'SVABrainstormDials':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
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

        def execute_function(llm: LLM) -> dict:
            sllm = llm.as_structured_llm(DocumentDetails)
            chat_response = sllm.chat(chat_message_list)
            metadata = dict(llm.metadata)
            metadata["llm_classname"] = llm.class_name()
            return {
                "chat_response": chat_response,
                "metadata": metadata
            }

        start_time = time.perf_counter()
        try:
            result = llm_executor.run(execute_function)
        except PipelineStopRequested:
            # Re-raise PipelineStopRequested without wrapping it
            raise
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(result["chat_response"].message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        json_response = result["chat_response"].raw.model_dump()

        metadata = result["metadata"]
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = SVABrainstormDials(
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
    from planexe.llm_util.llm_executor import LLMModelFromName
    from planexe.prompt.prompt_catalog import PromptCatalog

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_simple_plan_prompts()
    # prompt_item = prompt_catalog.find("a6bef08b-c768-4616-bc28-7503244eff02")
    prompt_item = prompt_catalog.find("19dc0718-3df7-48e3-b06d-e2c664ecc07d")
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    model_names = [
        "ollama-llama3.1",
        # "openrouter-paid-gemini-2.0-flash-001",
        # "openrouter-paid-qwen3-30b-a3b"
    ]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    print(f"Query: {query}")
    result = SVABrainstormDials.execute(llm_executor, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))
