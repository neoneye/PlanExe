"""
Strategic Variant Analysis (SVA), explore the solution space.

Step 1:
- Brainstorm what key "levers" can be pulled to change the outcome of the plan.
- For each level, identify the possible values.

Step 2:
- moving from a brainstormed list to a focused set of strategic levers.
- Applying the 80/20 rule here means finding the ~20% of levers (the "vital few," i.e., your 4-5 most significant) that will dictate ~80% of the project's strategic outcome. This is a curation process based on strategic importance, not random sampling.

Step 3:
- With all the permutations of the levers and their values, take 20 random samples.
- 80/20 rule: Identify the most significant 4 samples. Discard the rest.

PROMPT> python -m planexe.strategic_variant_analysis.identify_potential_levers
"""
import json
import logging
from typing import Optional
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logger = logging.getLogger(__name__)

class Lever(BaseModel):
    lever_index: int = Field(
        description="Index of this lever."
    )
    name: str = Field(
        description="Name of this lever."
    )
    consequences: str = Field(
        description="Briefly describe the likely second-order effects or consequences of pulling this lever (e.g., 'Choosing a high-risk tech strategy will likely increase talent acquisition difficulty and require a larger contingency budget.'). 30 words."
    )
    options: list[str] = Field(
        description="2-5 options for this lever."
    )
    review_lever: str = Field(
        description="Critique this lever. State the core trade-off it controls (e.g., 'Controls Speed vs. Quality'). Then, identify one specific weakness in how its options address that trade-off."
    )

class DocumentDetails(BaseModel):
    strategic_rationale: str = Field(
        description="A concise strategic analysis (around 100 words) of the project's core tensions and trade-offs. This rationale must JUSTIFY why the selected levers are the most critical levers for decision-making. For example, explain how the chosen levers navigate the fundamental conflicts between speed, cost, scope, and quality."
    )
    levers: list[Lever] = Field(
        description="Propose exactly 5 levers."
    )
    summary: str = Field(
        description="Are these levers well picked? Are they well balanced? Are they well thought out? Point out flaws. 100 words."
    )

class LeverCleaned(BaseModel):
    """
    The Lever class has some ugly field names, that guide the LLM for what to generate. Changing them and the LLM can't generate as good results.
    This class has nicer field names for the final output.
    """
    id: str = Field(
        description="String that identifies this lever. Starts with 'Lever-1' and is incremented for each lever."
    )
    name: str = Field(
        description="Name of this lever."
    )
    consequences: str = Field(
        description="Briefly describe the likely second-order effects or consequences of pulling this lever (e.g., 'Choosing a high-risk tech strategy will likely increase talent acquisition difficulty and require a larger contingency budget.'). 30 words."
    )
    options: list[str] = Field(
        description="2-5 options for this lever."
    )
    review: str = Field(
        description="Critique this lever. State the core trade-off it controls (e.g., 'Controls Speed vs. Quality'). Then, identify one specific weakness in how its options address that trade-off."
    )

IDENTIFY_POTENTIAL_LEVERS_SYSTEM_PROMPT = """
You are an expert strategic analyst. Generate solution space parameters following these directives:

1. **Output Requirements**
   - You must generate EXACTLY 5 levers per response. Do not generate more or fewer than 5 levers.
   - Format options as discrete JSON list items with 3 QUALITATIVE choices:
     ```json
     "options": ["Descriptive Strategic Choice", "Descriptive Strategic Choice", "Descriptive Strategic Choice"]
     ```

2. **Lever Quality Standards**
   - Consequences MUST:
     • Chain three SPECIFIC effects: "Immediate: [effect] → Systemic: [impact] → Strategic: [implication]"
     • Include measurable outcomes: "Systemic: 25% faster scaling through..."
     • Explicitly describe trade-offs between core tensions
   - Options MUST:
     • Represent distinct strategic pathways (not just labels)
     • Include at least one unconventional/innovative approach
     • Show clear progression: conservative → moderate → radical
     • NO prefixes (e.g., "Option A:", "Choice 1:")

3. **Strategic Framing**
   - Name levers as strategic concepts (e.g., "Material Adaptation Strategy")
   - Frame options as complete strategic approaches
   - Ensure levers challenge core project assumptions

4. **Validation Protocols**
   - For `review_lever`:
     • State the trade-off explicitly: "Controls [Tension A] vs. [Tension B]."
     • Identify a specific weakness: "Weakness: The options fail to consider [specific factor]."
   - For `summary`:
     • Identify ONE critical missing dimension
     • Prescribe CONCRETE addition: "Add '[full strategic option]' to [lever]"

5. **Prohibitions**
   - NO prefixes/labels in options (e.g., "Option A:", "Choice 1:")
   - NO generic option labels (e.g., "Optimize X", "Tolerate Y")
   - NO placeholder consequences
   - NO "[specific innovative option]" placeholders
   - NO value sets without clear strategic progression

6. **Option Structure Enforcement**
   - Radical option must include emerging tech/business model
   - Maintain parallel grammatical structure across options
   - Ensure options are self-contained descriptions
"""

@dataclass
class IdentifyPotentialLevers:
    system_prompt: Optional[str]
    user_prompt: str
    raw_responses: list[DocumentDetails]
    levers: list[LeverCleaned]
    metadata: dict

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str) -> 'IdentifyPotentialLevers':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        system_prompt = IDENTIFY_POTENTIAL_LEVERS_SYSTEM_PROMPT.strip()
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

        raw_responses: list[DocumentDetails] = []
        for user_prompt_index, user_prompt_item in enumerate(user_prompt_list, start=1):
            logger.info(f"Processing user_prompt_index: {user_prompt_index} of {len(user_prompt_list)}")
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

            raw_responses.append(result["chat_response"].raw)

        # from the raw_responses, extract the levers into a flatten list
        levers_raw: list[Lever] = []
        for raw_response in raw_responses:
            levers_raw.extend(raw_response.levers)

        # Clean the raw levers
        levers_cleaned: list[LeverCleaned] = []
        for i, lever in enumerate(levers_raw, start=1):
            lever_cleaned = LeverCleaned(
                id=f"Lever-{i}",
                name=lever.name,
                consequences=lever.consequences,
                options=lever.options,
                review=lever.review_lever,
            )
            levers_cleaned.append(lever_cleaned)

        metadata = {}

        result = IdentifyPotentialLevers(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_responses=raw_responses,
            levers=levers_cleaned,
            metadata=metadata,
        )
        return result    

    def to_dict(self, include_raw_responses=True, include_cleaned_levers=True, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = {}
        if include_raw_responses:
            d["raw_responses"] = [response.model_dump() for response in self.raw_responses]
        if include_cleaned_levers:
            d['levers'] = [lever.model_dump() for lever in self.levers]
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
    result = IdentifyPotentialLevers.execute(llm_executor, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))
