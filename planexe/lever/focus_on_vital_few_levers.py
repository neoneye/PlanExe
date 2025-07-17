"""
This was generated with Gemini 2.5 Pro.

PROMPT> python -m planexe.lever.focus_on_vital_few_levers
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
    lever_id: str
    name: str
    consequences: str
    options: List[str]
    review: str
    description: str
    synergy_text: str
    conflict_text: str
    original_index: int = -1

class LeverAssessment(BaseModel):
    """An assessment of a single strategic lever's importance."""
    lever_id: str = Field(
        description="The original lever_id from the provided list."
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
You are a Chief Strategy Officer (CSO) responsible for guiding high-stakes projects. Your task is to apply the 80/20 principle to a list of strategic levers, identifying the "vital few" that will drive the majority of the project's strategic outcome.

**Goal:** Identify the ~5 most critical levers from the provided list.

**Input:** You will receive the project plan and a numbered list of candidate levers. For each lever, you get:
- A `description` of its purpose.
- A `synergy_text` summarizing its positive connections to other levers.
- A `conflict_text` summarizing its trade-offs and negative connections.

**Evaluation Criteria:**
Evaluate each lever's **Strategic Importance**. A lever's importance is determined by its systemic impact. You MUST base your assessment on all the provided context. Consider:
1.  **Centrality & Connectivity:** Does the `synergy_text` and `conflict_text` show this lever is a "hub" that influences many others? Highly connected levers are more strategic.
2.  **Impact on Core Trade-offs:** Does the `conflict_text` reveal that this lever controls a fundamental project tension (e.g., Speed vs. Quality, Cost vs. Scope)?
3.  **Potential for Leverage:** Does the `synergy_text` suggest that getting this lever right could unlock significant value across the system?
4.  **Redundancy:** If several levers seem to address the same core issue (e.g., multiple levers about 'modularity'), identify the one that best represents the strategic choice and rank it higher. Rank the redundant ones lower.

**Strategic Importance Rating Definitions (Assign ONE per lever):**
-   **Critical:** Absolutely essential. A central "hub" lever that controls a foundational pillar of the project's strategy.
-   **High:** Very important. Governs a major strategic trade-off or has numerous strong interactions.
-   **Medium:** Useful for optimization but less connected to the core strategic conflicts.
-   **Low:** Tactical or potentially redundant with a more strategic lever.

**Output Requirements:**
-   You MUST respond with a single JSON object that strictly adheres to the `VitalLeversAssessmentResult` schema.
-   You MUST provide an assessment for **every single lever** in the input list.
-   The `justification` MUST be concise and reference the lever's connectivity or control over trade-offs.

**Example Justification:** "Critical because its synergy and conflict texts show it's a central hub connecting technology, governance, and materials. It controls the project's core risk/reward profile."
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
    def execute(cls, llm_executor: LLMExecutor, project_context: str, raw_levers_list: List[dict]) -> 'FocusOnVitalFewLevers':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not raw_levers_list:
            raise ValueError("No valid enriched levers were provided.")
        enriched_levers = [EnrichedLever(**lever) for lever in raw_levers_list]

        logger.info(f"Assessing {len(enriched_levers)} characterized levers to find the vital few.")

        # Convert Pydantic models to dictionaries for JSON serialization
        levers_dict = [lever.model_dump() for lever in enriched_levers]
        levers_json = json.dumps(levers_dict, indent=2)        
        focus_prompt = (
            f"**Project Context:**\n{project_context}\n\n"
            f"**Candidate Levers List:**\n"
            f"Please assess the strategic importance of the following {len(enriched_levers)} levers based on the project plan and their detailed characterizations:\n\n"
            f"{levers_json}"
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
                assessments_by_importance[ass.strategic_importance].append(ass.lever_id)
            except KeyError:
                logger.warning(f"Unknown strategic importance level '{ass.strategic_importance}' for lever {ass.lever_id}. Skipping.")
        
        selected_lever_ids: list[str] = []
        
        # Prioritize in order: Critical -> High -> Medium -> Low
        for importance_level in [StrategicImportance.critical, StrategicImportance.high, StrategicImportance.medium, StrategicImportance.low]:
            if len(selected_lever_ids) >= target_count:
                break
            lever_ids_to_add = assessments_by_importance[importance_level]
            # Add indices until we reach the target, don't add all from a level if it puts us over
            for lever_id in lever_ids_to_add:
                if len(selected_lever_ids) < target_count:
                    selected_lever_ids.append(lever_id)
                else:
                    break

        # Retrieve the full Lever objects for the selected lever_ids
        vital_levers = []
        for lever in all_levers:
            if lever.lever_id in selected_lever_ids:
                vital_levers.append(lever)

        return vital_levers

    def save_vital_levers(self, file_path: str) -> None:
        """Saves just the final list of vital levers to a file."""
        # The output format for the next script expects a simple dictionary for each lever.
        output_levers = []
        for lever in self.vital_levers:
            output_levers.append({
                "lever_id": lever.lever_id,
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
    from planexe.prompt.prompt_catalog import PromptCatalog

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_simple_plan_prompts()

    prompt_id = "19dc0718-3df7-48e3-b06d-e2c664ecc07d"
    prompt_item = prompt_catalog.find(prompt_id)
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    project_plan = prompt_item.prompt

    output_filename = f"focus_on_vital_few_levers_{prompt_id}.json"

    # --- Step 1: Load the enriched levers ---
    enrich_potential_levers_file = os.path.join(os.path.dirname(__file__), 'test_data', f'enrich_potential_levers_{prompt_id}.json')
    if not os.path.exists(enrich_potential_levers_file):
        logger.error(f"Enriched levers file not found at: {enrich_potential_levers_file!r}. Please run enrich_potential_levers.py first.")
        exit(1)

    with open(enrich_potential_levers_file, 'r', encoding='utf-8') as f:
        characterized_data = json.load(f)
    raw_levers_list = characterized_data.get('characterized_levers', [])

    logger.info(f"Loaded {len(raw_levers_list)} levers.")

    # --- Step 2: Focus on the Vital Few ---
    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)
    
    focus_result = FocusOnVitalFewLevers.execute(
        llm_executor=llm_executor,
        project_context=project_plan,
        raw_levers_list=raw_levers_list
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
    focus_result.save_vital_levers(output_filename)
    logger.info(f"Saved the {vital_levers_count} vital few levers to '{output_filename}'")