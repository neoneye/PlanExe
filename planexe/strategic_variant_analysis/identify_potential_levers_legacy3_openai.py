"""
Strategic Variant Analysis (SVA), explore the solution space.

Step 1:
- Brainstorm what key "dials" can be turned to change the outcome of the plan.
- For each dial, identify the possible values.

Step 2:
- moving from a brainstormed list to a focused set of strategic levers.
- Applying the 80/20 rule here means finding the ~20% of dials (the "vital few," i.e., your 4-5 most significant) that will dictate ~80% of the project's strategic outcome. This is a curation process based on strategic importance, not random sampling.

Step 3:
- With all the permutations of the dials and their values, take 20 random samples.
- 80/20 rule: Identify the most significant 4 samples. Discard the rest.

PROMPT> python -m planexe.strategic_variant_analysis.identify_potential_levers_legacy3_openai
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
    consequences: str = Field(
        description="Briefly describe the likely second-order effects or consequences of turning this dial (e.g., 'Choosing a high-risk tech strategy will likely increase talent acquisition difficulty and require a larger contingency budget.'). 30 words."
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

# Prompt made with OpenAI GPT-4.1
STRATEGIC_VARIANT_ANALYSIS_SYSTEM_PROMPT = """
You are the Strategic Variant Analysis (SVA) agent. Your role is to analyze high-level project prompts, identify adjustable strategic and technical parameters (“dials”), and generate alternative plans by varying these dials. The goal is to explore the space of possible solutions and uncover near-optimal or robust strategies.

You must generate exactly 5 dials per response. Do not generate more or fewer than 5 dials. Each dial should be distinct, actionable, and interdependent with at least one other dial.

Guidelines for SVA Analysis:

1. For every project prompt:
   - Extract the primary objectives, constraints, and success metrics.
   - Identify and list the key “dials” (parameters or levers) that could be adjusted to change the project outcome.

2. When generating dials (adjustable parameters or levers) for a plan:
   - Assume that real-world dials are not independent; setting one dial can affect the feasibility, desirability, or outcomes of others.
   - For each dial, briefly note which other dials it is likely to interact with, and the possible directions of these interactions.
   - Favor dials that represent meaningful trade-offs or constraints rather than isolated technical toggles.
   - Avoid trivial, redundant, or obviously orthogonal dials.
   - Each dial’s review of interactions must reference only dials present in the same list. Do not mention outcomes, KPIs, or metrics as if they are dials.
   - The consequences field must be a project-specific statement of the trade-off, not a placeholder or variable name.
   - The review_dial field must not be empty, and must always explain how the dial interacts with at least one other dial from the same list.
   - Dial names must use a consistent, human-readable style throughout each response.
   - The summary must explain, in one or two sentences, why the highlighted interdependencies matter for the overall system or plan.

3. For each dial you generate:
   - Explicitly name every other dial it interacts with, and describe if the interaction is positive (synergy) or negative (trade-off).
   - Use the format: “Changing [This Dial] will likely cause [Other Dial] to [increase/decrease/require adjustment] because [reason].”
   - At the end, summarize the strongest 2–3 dial interdependencies in a short paragraph.
   - Propose at least two “dial bundles”—specific, plausible combinations of dial settings that may represent local optima or distinct strategies.

4. Generate a diverse set of plan variants by systematically varying combinations of dials, especially where strong interactions exist.

5. When presenting results:
   - Summarize each variant’s key characteristics, anticipated outcomes, and notable risks or upside.
   - Clearly highlight which dials had the most significant impact and where interdependencies drove emergent effects.

You must always document your reasoning and make interdependencies explicit in your analysis.
"""

@dataclass
class SVABrainstormDials:
    system_prompt: Optional[str]
    user_prompt: str
    responses: list[str]
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

        user_prompt_list = [
            user_prompt,
            "more",
            "more",
        ]

        responses = []
        for user_prompt_index, user_prompt_item in enumerate(user_prompt_list):
            logger.info(f"Processing user_prompt_index: {user_prompt_index}")
            chat_message_list.append(
                ChatMessage(
                    role=MessageRole.USER,
                    content=user_prompt_item,
                )
            )

            def execute_function(llm: LLM) -> dict:
                sllm = llm.as_structured_llm(DocumentDetails)
                chat_response = sllm.chat(chat_message_list)
                metadata = dict(llm.metadata)
                metadata["llm_classname"] = llm.class_name()
                return {
                    "chat_response": chat_response,
                    "metadata": metadata
                }

            try:
                result = llm_executor.run(execute_function)
            except PipelineStopRequested:
                # Re-raise PipelineStopRequested without wrapping it
                raise
            except Exception as e:
                logger.debug(f"LLM chat interaction failed: {e}")
                logger.error("LLM chat interaction failed.", exc_info=True)
                raise ValueError("LLM chat interaction failed.") from e
            
            chat_message_list.append(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=result["chat_response"].raw.model_dump(),
                )
            )

            responses.append(result["chat_response"].raw.model_dump())


        metadata = {}

        result = SVABrainstormDials(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            responses=responses,
            metadata=metadata,
        )
        return result    

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = {
            "responses": self.responses.copy()
        }
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

    logging.basicConfig(level=logging.DEBUG)

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
