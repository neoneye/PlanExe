"""
Step 5: Generate Strategic Scenarios

- This is the final step of the strategic analysis pipeline.
- It takes the filtered list of "vital few" levers as input.
- It uses an LLM to synthesize these levers into a small number of distinct,
  internally-coherent strategic scenarios.
- Each scenario represents a plausible pathway for the project, complete with a
  name, a strategic logic, and a specific setting for each vital lever.
- This transforms the analysis from a list of factors into a clear choice for decision-makers.

PROMPT> python -m planexe.lever.lever_scenario_synthesizer
"""
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, ValidationError

from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logger = logging.getLogger(__name__)

# --- Pydantic Models ---

# Represents a lever from the 'vital_levers' file
class VitalLever(BaseModel):
    lever_index: int
    name: str
    options: List[str]
    review_lever: str

# The final output models for a strategic scenario
class Scenario(BaseModel):
    scenario_name: str = Field(
        description="A descriptive, memorable name for the scenario (e.g., 'The Pioneer's Gambit', 'The Pragmatic Foundation')."
    )
    strategic_logic: str = Field(
        description="A brief (2-3 sentences) explanation of the scenario's core philosophy and how it resolves key project tensions."
    )
    lever_settings: Dict[str, str] = Field(
        description="A dictionary mapping each vital lever name to a specific chosen option. The chosen option MUST be one of the provided options for that lever."
    )

class ScenarioAnalysisResult(BaseModel):
    """The complete set of strategic scenarios."""
    analysis_title: str = Field(description="A fitting title for the overall strategic analysis.")
    core_tension: str = Field(
        description="A one-sentence summary of the central trade-off the scenarios are designed to explore (e.g., 'The central tension is between maximizing long-term technological dominance and ensuring short-term project viability and cost control.')."
    )
    scenarios: List[Scenario] = Field(
        description="A list of exactly 3 distinct strategic scenarios."
    )

# --- LLM Prompt ---

GENERATE_SCENARIOS_SYSTEM_PROMPT = """
You are a Chief Strategy Officer presenting the final, synthesized strategic options to the project's board of directors. You have already identified the project's 'vital few' levers. Your task is to weave these levers into 3 distinct, coherent, and actionable strategic scenarios.

**Goal:** Transform a list of levers and options into a clear choice between competing strategic pathways.

**Input:** You will receive the original project plan and the list of vital levers, including their names, descriptions, and options.

**Task:**
Generate exactly 3 strategic scenarios based on the provided levers. Each scenario must be a complete, internally-consistent combination of choices. Adhere to the `ScenarioAnalysisResult` JSON schema.

**Scenario Archetypes to Generate:**

1.  **The High-Risk / High-Reward Path ("The Pioneer"):** This scenario prioritizes innovation, speed, and technological leadership, accepting higher risks and costs. Select the most aggressive, forward-looking option for each lever to create this path.
2.  **The Balanced / Pragmatic Path ("The Builder"):** This scenario seeks a balance between innovation and stability. It aims for solid progress while managing risk. Select the moderate, most likely-to-succeed options for each lever.
3.  **The Low-Risk / Low-Cost Path ("The Consolidator"):** This scenario prioritizes stability, cost-control, and risk-aversion above all. It chooses the safest, most proven, and often most conservative options across the board.

For each scenario, ensure the `lever_settings` are logically consistent with its `strategic_logic`. For instance, a "Pioneer" scenario should not choose a "Compliance-Based Governance" option.
"""

@dataclass
class LeverScenarioSynthesizer:
    system_prompt: str
    user_prompt: str
    response: ScenarioAnalysisResult
    metadata: dict

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, project_context: str, raw_vital_levers: list[dict]) -> 'LeverScenarioSynthesizer':
        vital_levers = [VitalLever(**lever) for lever in raw_vital_levers]

        if not vital_levers:
            raise ValueError("The list of vital levers cannot be empty.")

        logger.info(f"Generating strategic scenarios from {len(vital_levers)} vital levers.")

        # Format the input for the LLM
        formatted_levers_list = []
        for lever in vital_levers:
            options_str = ", ".join(f"'{opt}'" for opt in lever.options)
            formatted_levers_list.append(
                f"**Lever: {lever.name}**\n"
                f"  - Description: {lever.review_lever}\n"
                f"  - Options: [{options_str}]"
            )
        levers_prompt_text = "\n\n".join(formatted_levers_list)

        user_prompt = (
            f"**Project Context:**\n{project_context}\n\n"
            "---\n\n"
            f"**Vital Levers & Options:**\n{levers_prompt_text}\n\n"
            "Please synthesize these levers into 3 distinct strategic scenarios as requested."
        )

        system_prompt = GENERATE_SCENARIOS_SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt)
        ]

        def execute_function(llm: LLM) -> dict:
            sllm = llm.as_structured_llm(ScenarioAnalysisResult)
            chat_response = sllm.chat(chat_message_list)
            metadata = dict(llm.metadata)
            metadata["llm_classname"] = llm.class_name()
            return {"chat_response": chat_response, "metadata": metadata}

        try:
            result = llm_executor.run(execute_function)
        except PipelineStopRequested:
            raise
        except Exception as e:
            logger.error("LLM chat interaction for generating scenarios failed.", exc_info=True)
            raise ValueError("LLM interaction failed.") from e
        return cls(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=result["chat_response"].raw,
            metadata=result["metadata"]
        )

    def to_dict(self, include_response=True, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = {}
        if include_response:
            d["response"] = self.response.model_dump()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        Path(file_path).write_text(json.dumps(self.to_dict(), indent=2))

    def save_clean(self, file_path: str) -> None:
        response_dict = self.response.model_dump()
        Path(file_path).write_text(json.dumps(response_dict, indent=2))

if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- Step 1: Load inputs from previous pipeline steps ---
    plan_data_file = "planexe/lever/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt"
    # This is the output file from the filtering step
    vital_levers_file = "vital_levers_from_test_data3.json"
    output_file = "strategic_scenarios.json"
    
    # ... (Error handling for file existence) ...

    # Load project plan
    with open(plan_data_file, 'r', encoding='utf-8') as f:
        plan_part, _ = f.read().split("file: 'potential_levers.json':")
        project_context = plan_part.replace("file: 'plan.txt':", "").strip()

    # Load vital levers
    with open(vital_levers_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    vital_levers = data['levers']

    logger.info(f"Loaded project plan and {len(vital_levers)} vital levers.")

    # --- Step 2: Execute the analysis ---
    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    try:
        scenarios_result = LeverScenarioSynthesizer.execute(
            llm_executor=llm_executor,
            project_context=project_context,
            raw_vital_levers=vital_levers
        )

        # --- Step 3: Display and save results ---
        print("\n--- Strategic Scenario Analysis ---")
        d = scenarios_result.to_dict(include_response=True, include_metadata=True, include_system_prompt=False, include_user_prompt=False)
        print(json.dumps(d, indent=2))

        scenarios_result.save_clean(output_file)
        logger.info(f"Strategic scenarios saved to '{output_file}'.")

    except ValueError as e:
        logger.error(f"An error occurred during scenario generation: {e}")