"""
This was generated with Gemini 2.5 Pro.

PROMPT> python -m planexe.lever.focus_on_vital_few_levers_legacy4_gemini
"""
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Any

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, ValidationError

from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logger = logging.getLogger(__name__)

# The target number of vital levers to select.
TARGET_VITAL_LEVER_COUNT = 5

class StrategicImportance(str, Enum):
    """Enum to indicate the strategic importance of a lever for the project's outcome."""
    critical = 'Critical'  # A fundamental lever that defines the project's core strategy or viability.
    high = 'High'          # A lever controlling a major trade-off (e.g., cost, scope, quality) with significant impact.
    medium = 'Medium'      # A lever that offers meaningful optimization but doesn't alter the core strategy.
    low = 'Low'            # A tactical or operational choice with limited strategic ripple effects.

# A Pydantic model representing the structure of the enriched levers we will be loading.
class EnrichedLever(BaseModel):
    id: str
    name: str
    consequences: str
    options: List[str]
    review: str
    description: str
    original_index: int = -1

class LeverAssessment(BaseModel):
    """An assessment of a single strategic lever's importance."""
    lever_index: int = Field(
        description="The original index of the lever from the provided list."
    )
    lever_name: str = Field(
        description="The name of the lever being assessed."
    )
    strategic_importance: StrategicImportance = Field(
        description="The assessed strategic importance of this lever, based on the 80/20 principle."
    )
    justification: str = Field(
        description="Concise rationale (30-50 words) explaining WHY this lever has the assigned importance. Link it directly to the project's core goals, risks, or fundamental trade-offs. Example: 'Critical because it controls the fundamental go-to-market strategy, directly impacting revenue models and market penetration speed mentioned in the plan.'"
    )

class VitalLeversAssessmentResult(BaseModel):
    """The result of assessing and prioritizing a list of strategic levers."""
    lever_assessments: List[LeverAssessment] = Field(
        description="A list containing the assessment for every single lever provided in the input."
    )
    summary: str = Field(
        description="A strategic overview (50-70 words) of the prioritization. Explain which fundamental project tensions (e.g., 'Speed vs. Scalability', 'Cost vs. Innovation') the selected 'Critical' and 'High' impact levers address as a group. Mention if any key strategic dimensions seem to be missing from the provided levers."
    )

FOCUS_LEVERS_SYSTEM_PROMPT = """
You are a Chief Strategy Officer (CSO) responsible for guiding high-stakes projects. Your task is to apply the 80/20 principle (Pareto Principle) to a list of strategic levers for a given project plan.

**Goal:** Identify the "vital few" levers (the ~20%) that will determine the vast majority (~80%) of the project's strategic outcome.

**Input:** You will receive the original project plan and a numbered list of candidate levers, each with a name, a detailed description, and a brief review.

**Evaluation Criteria:**
Evaluate each lever's **Strategic Importance**. A lever's importance is determined by its ability to influence the project's fundamental success factors. You MUST base your assessment on the provided **description** and how it relates to the project plan. Consider:
1.  **Impact on Core Trade-offs:** Does the lever control a fundamental conflict, such as Speed vs. Quality, Cost vs. Scope, or Innovation vs. Feasibility?
2.  **Influence on Viability:** Can a decision on this lever make or break the project's business case, technical feasibility, or market acceptance?
3.  **Magnitude of Consequence:** Do the options within the lever lead to vastly different strategic pathways and outcomes?

**Strategic Importance Rating Definitions (Assign ONE per lever):**
-   **Critical:** Absolutely essential. This lever controls a foundational pillar of the project's strategy or a go/no-go decision.
-   **High:** Very important. This lever governs a major strategic trade-off that will significantly impact key metrics.
-   **Medium:** Useful for optimization. This lever influences important aspects but does not fundamentally alter the core strategic direction.
-   **Low:** Tactical or operational. This lever concerns implementation details with limited ripple effects.

**Output Requirements:**
You MUST respond with a single JSON object that strictly adheres to the `VitalLeversAssessmentResult` schema.
-   You MUST provide an assessment for **every single lever** in the input list.
-   The `justification` MUST be concise and explicitly link the lever to the project's core goals or risks.
-   The final `summary` must provide a holistic view of the most important levers as a group.

**Example Justification:** "Critical because its description shows it dictates the entire technology stack, which directly controls the project's long-term scalability and talent acquisition risks identified in the plan."
"""

@dataclass
class FocusOnVitalFewLevers:
    """
    Analyzes enriched levers to identify the "vital few" based on strategic importance.
    """
    system_prompt: str
    user_prompt: str
    enriched_levers: list[EnrichedLever]
    assessment_result: VitalLeversAssessmentResult
    vital_levers: list[EnrichedLever]
    metadata: dict

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, project_plan: str, enriched_levers: List[EnrichedLever]) -> 'FocusOnVitalFewLevers':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not enriched_levers:
            raise ValueError("No valid enriched levers were provided.")

        logger.info(f"Assessing {len(enriched_levers)} enriched levers to find the vital few.")

        # Step 1: Prepare the input for the LLM, now with richer details.
        formatted_levers_list = []
        for i, lever in enumerate(enriched_levers):
            lever.original_index = i
            formatted_levers_list.append(
                f"{i}. **{lever.name}**\n"
                f"   - **Description**: {lever.description}\n"
                f"   - **Review**: {lever.review}"
            )
        
        levers_prompt_text = "\n\n".join(formatted_levers_list)
        
        focus_prompt = (
            f"**Project Plan:**\n{project_plan}\n\n"
            f"**Candidate Levers List:**\n"
            f"Please assess the strategic importance of the following {len(enriched_levers)} levers based on the project plan and their detailed descriptions:\n\n"
            f"{levers_prompt_text}"
        )

        system_prompt = FOCUS_LEVERS_SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=focus_prompt)
        ]

        # Step 2: Run the LLM to get the assessment
        def execute_function(llm: LLM) -> dict:
            sllm = llm.as_structured_llm(VitalLeversAssessmentResult)
            chat_response = sllm.chat(chat_message_list)
            metadata = dict(llm.metadata)
            metadata["llm_classname"] = llm.class_name()
            return { "chat_response": chat_response, "metadata": metadata }
        
        try:
            result = llm_executor.run(execute_function)
            assessment_result = result["chat_response"].raw
            metadata = result["metadata"]
        except PipelineStopRequested:
            raise
        except Exception as e:
            logger.error("LLM chat interaction for focusing levers failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e
            
        # Step 3: Select the "vital few" levers based on the assessment
        vital_levers = cls.select_top_levers(
            all_levers=enriched_levers,
            assessment=assessment_result,
            target_count=TARGET_VITAL_LEVER_COUNT
        )
        logger.info(f"Selected {len(vital_levers)} vital levers.")

        return cls(
            system_prompt=system_prompt,
            user_prompt=focus_prompt,
            enriched_levers=enriched_levers,
            assessment_result=assessment_result,
            vital_levers=vital_levers,
            metadata=metadata
        )

    @staticmethod
    def select_top_levers(all_levers: list[EnrichedLever], assessment: VitalLeversAssessmentResult, target_count: int) -> list[EnrichedLever]:
        """Selects the most important levers based on their strategic importance rating."""
        assessments_by_importance = {
            StrategicImportance.critical: [],
            StrategicImportance.high: [],
            StrategicImportance.medium: [],
            StrategicImportance.low: []
        }

        for ass in assessment.lever_assessments:
            try:
                assessments_by_importance[ass.strategic_importance].append(ass.lever_index)
            except KeyError:
                logger.warning(f"Unknown strategic importance level '{ass.strategic_importance}' for lever {ass.lever_index}. Skipping.")
        
        selected_indices = []
        
        # Prioritize in order: Critical -> High -> Medium -> Low
        for importance_level in [StrategicImportance.critical, StrategicImportance.high, StrategicImportance.medium, StrategicImportance.low]:
            if len(selected_indices) >= target_count:
                break
            indices_to_add = assessments_by_importance[importance_level]
            # Add indices until we reach the target, don't add all from a level if it puts us over
            for index in indices_to_add:
                if len(selected_indices) < target_count:
                    selected_indices.append(index)
                else:
                    break

        # Retrieve the full Lever objects for the selected indices
        all_levers_by_index = {lever.original_index: lever for lever in all_levers}
        vital_levers = [all_levers_by_index[i] for i in selected_indices if i in all_levers_by_index]
        
        # Sort by original index to maintain some order
        vital_levers.sort(key=lambda x: x.original_index)

        return vital_levers

    def save_vital_levers(self, file_path: str) -> None:
        """Saves just the final list of vital levers to a file."""
        # The output format for the next script expects a simple dictionary for each lever.
        output_levers = []
        for lever in self.vital_levers:
            output_levers.append({
                "lever_index": lever.original_index,
                "name": lever.name,
                "options": lever.options,
                "consequences": lever.consequences,
                "review_lever": lever.review
            })

        vital_levers_dict = { "levers": output_levers }
        with open(file_path, 'w') as f:
            json.dump(vital_levers_dict, f, indent=2)


if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- Step 1: Load Project Plan and Enriched Levers ---
    plan_data_file = "planexe/lever/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt"
    enriched_levers_file = "enriched_potential_levers.json"
    
    if not os.path.exists(plan_data_file):
        logger.error(f"Plan data file not found at: {plan_data_file}")
        exit(1)
    if not os.path.exists(enriched_levers_file):
        logger.error(f"Enriched levers file not found at: {enriched_levers_file}. Please run enrich_potential_levers.py first.")
        exit(1)

    # Load the project plan (query) from the original text file
    with open(plan_data_file, 'r', encoding='utf-8') as f:
        test_data_content = f.read()
    try:
        plan_part, _ = test_data_content.split("file: 'potential_levers.json':")
        query = plan_part.replace("file: 'plan.txt':", "").strip()
    except ValueError:
        logger.error(f"Failed to parse the plan data file: {plan_data_file}")
        exit(1)

    # Load the enriched levers from the new JSON file
    with open(enriched_levers_file, 'r', encoding='utf-8') as f:
        enriched_data = json.load(f)
    try:
        levers_list = enriched_data.get('enriched_levers', [])
        enriched_levers_objects = [EnrichedLever(**lever) for lever in levers_list]
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Failed to parse the enriched levers file. Ensure it is valid JSON and matches the EnrichedLever schema. Error: {e}")
        exit(1)

    logger.info(f"Loaded project plan and {len(enriched_levers_objects)} enriched levers.")

    # --- Step 2: Focus on the Vital Few ---
    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)
    
    focus_result = FocusOnVitalFewLevers.execute(
        llm_executor=llm_executor,
        project_plan=query,
        enriched_levers=enriched_levers_objects
    )
    
    # --- Step 3: Display and Save Results ---
    print("\n--- Assessment Result Summary ---")
    print(focus_result.assessment_result.summary)
    
    print("\n--- Full Assessment ---")
    assessment_json = focus_result.assessment_result.model_dump_json(indent=2)
    print(assessment_json)
    
    vital_levers_count = len(focus_result.vital_levers)
    print(f"\n--- The {vital_levers_count} Vital Few Levers ---")
    vital_levers_output = {
        "levers": [lever.model_dump() for lever in focus_result.vital_levers]
    }
    print(json.dumps(vital_levers_output, indent=2))

    # Save the vital levers for the next step in the pipeline
    output_filename = "vital_levers_from_test_data.json"
    focus_result.save_vital_levers(output_filename)
    logger.info(f"Saved the {vital_levers_count} vital few levers to '{output_filename}'")