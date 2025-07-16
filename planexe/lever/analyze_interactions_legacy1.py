"""
This was generated with Gemini 2.5 Pro.

Step 3.5: Analyze Interaction Effects Between Vital Levers

- This module takes the "vital few" levers identified in the filtering step.
- It uses an LLM to perform a systems analysis, identifying the 2-3 most significant
  synergistic or conflicting relationships between pairs or triplets of levers.
- This reveals deeper strategic insights, showing how decisions in one area
  amplify or constrain options in another.

PROMPT> python -m planexe.lever.analyze_interactions_legacy1
"""
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, ValidationError

from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

# This model should match the structure of the levers in your 'vital_levers' file.
# Using a unified model as previously recommended would be ideal here.
class VitalLever(BaseModel):
    name: str
    description: str
    options: List[str]
    # We only need these fields for the analysis, but include others for robust loading
    lever_index: int
    consequences: str
    review_lever: str


logger = logging.getLogger(__name__)


# --- Pydantic Models for Structured Output ---

class InteractionType(str, Enum):
    """The nature of the relationship between levers."""
    SYNERGY = "Synergy"      # Levers amplify each other's positive effects (1+1=3).
    CONFLICT = "Conflict"    # Levers work against each other, creating trade-offs or friction (1+1=0.5).

class LeverInteraction(BaseModel):
    """Describes a single significant interaction between two or more levers."""
    interacting_levers: List[str] = Field(
        description="A list of 2 or 3 lever names that have a strong interaction."
    )
    interaction_type: InteractionType = Field(
        description="The nature of the interaction: 'Synergy' or 'Conflict'."
    )
    description: str = Field(
        description="A clear explanation (50-70 words) of *how* and *why* these levers interact. Describe the mechanism of the synergy or conflict."
    )
    strategic_implication: str = Field(
        description="Actionable advice for a decision-maker (30-50 words). What should they do with this knowledge? E.g., 'These levers must be decided in tandem,' or 'Prioritizing X in Lever 1 forces a specific choice in Lever 2.'"
    )

class InteractionAnalysisResult(BaseModel):
    """The complete analysis of all significant lever interactions."""
    summary: str = Field(
        description="A high-level overview (40-60 words) of the core strategic dynamic. What is the central tension or opportunity revealed by these interactions?"
    )
    interactions: List[LeverInteraction] = Field(
        description="A list of the 2-3 most significant lever interactions."
    )


# --- LLM Prompt ---

ANALYZE_INTERACTIONS_SYSTEM_PROMPT = """
You are a master strategist and systems thinker, acting as a consultant to a major project's steering committee. Your task is to analyze the critical interaction effects between a given set of 'vital few' strategic levers. Your insights must be sharp, actionable, and expose the deep dynamics of the project.

**Goal:** Identify the 2-3 most significant **interaction effects** (synergies or conflicts) among the provided levers. Go beyond the obvious.

**Interaction Definitions:**
-   **Synergy (1+1=3):** Two or more levers amplify each other. Choosing a specific option in one lever makes an option in another lever dramatically more effective or even possible.
-   **Conflict (Antagonism):** Two or more levers work against each other. A choice in one lever creates a strong constraint, trade-off, or friction that makes a choice in another lever difficult, expensive, or ineffective.

**Input:** You will receive the project plan and a list of the vital levers, including their names, descriptions, and options.

**Output Requirements:**
You MUST respond with a single JSON object that strictly adheres to the `InteractionAnalysisResult` schema.

1.  **`summary` Field:**
    -   This MUST be a **synthesis of the core strategic dynamic**. Do not just label it.
    -   Identify the central tension or opportunity revealed by the interactions as a whole.
    -   **Example of a GOOD summary:** "The core dynamic is a classic 'Innovator's Dilemma': The levers driving long-term technological leadership (Tech Pathway, Talent) are in direct conflict with those ensuring short-term stability and risk management (Governance)."

2.  **`interactions` List (For each item):**
    -   You MUST identify the 2-3 most impactful interactions (pairs or triplets).
    -   **`description` Field:** Explain the mechanism of the interaction by referencing **specific options** from the levers. Don't be generic.
        -   **Example of a GOOD description:** "A 'Conflict' exists because the 'Radical New Process Developments' option under the *Technological Innovation Pathway* requires high-risk, fast-paced experimentation, which is incompatible with the slow, deliberate approval process inherent in the 'Compliance-Based Governance' option."
    -   **`strategic_implication` Field:** This MUST be **prescriptive, actionable advice for a leader**. Answer the question "So what should we do?" Use an "If-Then" or "To-do" structure.
        -   **Example of a GOOD strategic_implication:** "**If** the committee commits to 'Emerging Technology Integration', **then** the 'Talent' and 'Governance' strategies **must** be decided concurrently, not sequentially, to ensure the organization can support this high-risk, high-reward path."

You will be judged on the clarity, depth, and actionable nature of your strategic insights. Avoid shallow restatements.
"""

@dataclass
class InteractionAnalysis:
    """Holds the full context and result of the interaction analysis."""
    project_plan: str
    vital_levers: List[VitalLever]
    analysis_result: InteractionAnalysisResult
    metadata: Dict[str, Any]

    def save(self, file_path: str) -> None:
        """Saves the interaction analysis to a JSON file."""
        output_data = {
            "metadata": {**self.metadata, "source_project_plan": self.project_plan},
            "analyzed_levers": [lever.model_dump() for lever in self.vital_levers],
            "interaction_analysis": self.analysis_result.model_dump()
        }
        with open(file_path, 'w') as f:
            json.dump(output_data, f, indent=2)


class AnalyzeLeverInteractions:
    @classmethod
    def execute(cls, llm_executor: LLMExecutor, project_plan: str, vital_levers: List[VitalLever]) -> InteractionAnalysis:
        if not vital_levers:
            raise ValueError("The list of vital levers cannot be empty.")

        logger.info(f"Analyzing interactions for {len(vital_levers)} vital levers.")

        # Format the input for the LLM
        formatted_levers_list = []
        for lever in vital_levers:
            # We need to load the full lever data from the previous step for this to work
            # For this example, we assume vital_levers_file contains name, desc, and options
            options_str = ", ".join(f"'{opt}'" for opt in lever.options)
            formatted_levers_list.append(
                f"**Lever: {lever.name}**\n"
                f"  - **Description**: {lever.description}\n"
                f"  - **Options**: [{options_str}]"
            )
        levers_prompt_text = "\n\n".join(formatted_levers_list)

        user_prompt = (
            f"**Project Plan:**\n{project_plan}\n\n"
            "---\n\n"
            f"**Vital Levers for Analysis:**\n"
            f"Based on the project plan, analyze the systemic interactions between the following {len(vital_levers)} levers. "
            f"Identify the 2-3 most critical synergies and conflicts.\n\n"
            f"{levers_prompt_text}"
        )

        system_prompt = ANALYZE_INTERACTIONS_SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt)
        ]

        def execute_function(llm: LLM) -> dict:
            sllm = llm.as_structured_llm(InteractionAnalysisResult)
            chat_response = sllm.chat(chat_message_list)
            metadata = dict(llm.metadata)
            metadata["llm_classname"] = llm.class_name()
            return {"chat_response": chat_response, "metadata": metadata}

        try:
            result = llm_executor.run(execute_function)
            analysis_result = result["chat_response"].raw
            metadata = result["metadata"]
        except PipelineStopRequested:
            raise
        except Exception as e:
            logger.error("LLM chat interaction for analyzing interactions failed.", exc_info=True)
            raise ValueError("LLM interaction failed.") from e

        return InteractionAnalysis(
            project_plan=project_plan,
            vital_levers=vital_levers,
            analysis_result=analysis_result,
            metadata=metadata
        )


if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- Step 1: Load inputs from previous pipeline steps ---
    # File containing the original project plan
    plan_data_file = "planexe/lever/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt"
    # File created by filter_levers_experimental2.py
    # IMPORTANT: This file must contain the 'description' for each lever.
    # I am using 'enriched_potential_levers.json' as the source for this example, assuming we filtered from it.
    vital_levers_file = "enriched_potential_levers.json"
    output_file = "lever_interactions.json"

    if not os.path.exists(plan_data_file) or not os.path.exists(vital_levers_file):
        logger.error(f"Required input file not found. Ensure '{plan_data_file}' and '{vital_levers_file}' exist.")
        exit(1)

    # Load project plan
    with open(plan_data_file, 'r', encoding='utf-8') as f:
        plan_part, _ = f.read().split("file: 'potential_levers.json':")
        project_plan = plan_part.replace("file: 'plan.txt':", "").strip()

    # Load vital levers (for this example, we'll just use the first 5 from the enriched file)
    with open(vital_levers_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    try:
        # Assuming the filter step selected the first 5 levers for demonstration
        levers_data = data['enriched_levers'][:5]
        # We need to map the fields from the enriched file to what VitalLever expects
        vital_levers_objects = []
        for i, lever_data in enumerate(levers_data):
            mapped_data = {
                "lever_index": i,
                "name": lever_data.get("name"),
                "description": lever_data.get("description"),
                "options": lever_data.get("options"),
                "consequences": lever_data.get("consequences"),
                "review_lever": lever_data.get("review") # Map "review" to "review_lever"
            }
            vital_levers_objects.append(VitalLever(**mapped_data))
            
    except (ValidationError, KeyError) as e:
        logger.error(f"Failed to parse vital levers file '{vital_levers_file}'. Error: {e}")
        exit(1)

    logger.info(f"Loaded project plan and {len(vital_levers_objects)} vital levers.")

    # --- Step 2: Execute the analysis ---
    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    try:
        interaction_result = AnalyzeLeverInteractions.execute(
            llm_executor=llm_executor,
            project_plan=project_plan,
            vital_levers=vital_levers_objects
        )

        # --- Step 3: Display and save results ---
        print("\n--- Interaction Analysis Result ---")
        print(json.dumps(interaction_result.analysis_result.model_dump(), indent=2))

        interaction_result.save(output_file)
        logger.info(f"Interaction analysis saved to '{output_file}'.")

    except ValueError as e:
        logger.error(f"An error occurred during the analysis: {e}")