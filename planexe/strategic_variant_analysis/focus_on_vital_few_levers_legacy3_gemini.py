"""
This was generated with Gemini 2.5 Pro.
It's not particular good, but it's better than the others.
My hypothesis is that I should enrich the potential levers with more information, before I attempt to 80/20 filter them,
so the LLM can make a better assessment.

Focus on the "Vital Few" Levers
- This module takes a brainstormed list of potential strategic levers.
- It applies the 80/20 rule by using an LLM to assess the strategic importance of each lever.
- The goal is to identify the ~20% of levers (the "vital few," e.g., 4-6) that will dictate ~80% of the project's strategic outcome.
- The output is a curated list of the most significant levers, along with the rationale for their selection.

PROMPT> python -m planexe.strategic_variant_analysis.focus_on_vital_few_levers_legacy3_gemini
"""
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field

from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested
from planexe.strategic_variant_analysis.identify_potential_levers import Lever

logger = logging.getLogger(__name__)

# The target number of vital levers to select.
TARGET_VITAL_LEVER_COUNT = 5

class StrategicImportance(str, Enum):
    """Enum to indicate the strategic importance of a lever for the project's outcome."""
    critical = 'Critical'  # A fundamental lever that defines the project's core strategy or viability.
    high = 'High'          # A lever controlling a major trade-off (e.g., cost, scope, quality) with significant impact.
    medium = 'Medium'      # A lever that offers meaningful optimization but doesn't alter the core strategy.
    low = 'Low'            # A tactical or operational choice with limited strategic ripple effects.

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

# Prompt designed to guide the LLM in applying the 80/20 principle to strategic levers.
FOCUS_LEVERS_SYSTEM_PROMPT = """
You are a Chief Strategy Officer (CSO) responsible for guiding high-stakes projects. Your task is to apply the 80/20 principle (Pareto Principle) to a brainstormed list of strategic levers for a given project plan.

**Goal:** Identify the "vital few" levers (the ~20%) that will determine the vast majority (~80%) of the project's strategic outcome.

**Input:** You will receive the original project plan and a numbered list of candidate levers.

**Evaluation Criteria:**
Evaluate each lever's **Strategic Importance**. A lever's importance is determined by its ability to influence the project's fundamental success factors. You MUST assess this based on:
1.  **Impact on Core Trade-offs:** Does the lever control a fundamental conflict, such as Speed vs. Quality, Cost vs. Scope, or Innovation vs. Feasibility?
2.  **Influence on Viability:** Can a decision on this lever make or break the project's business case, technical feasibility, or market acceptance?
3.  **Magnitude of Consequence:** Do the options within the lever lead to vastly different strategic pathways and outcomes?

**Strategic Importance Rating Definitions (Assign ONE per lever):**
-   **Critical:** Absolutely essential. This lever controls a foundational pillar of the project's strategy or a go/no-go decision. The entire project architecture or business model hinges on this choice.
-   **High:** Very important. This lever governs a major strategic trade-off that will significantly impact key metrics like cost, timeline, scope, or quality.
-   **Medium:** Useful for optimization. This lever influences important aspects but does not fundamentally alter the core strategic direction. It's more about "how well" than "what."
-   **Low:** Tactical or operational. This lever concerns implementation details or has limited ripple effects on the overall strategy.

**Output Requirements:**
You MUST respond with a single JSON object that strictly adheres to the `VitalLeversAssessmentResult` schema.
-   You MUST provide an assessment for **every single lever** in the input list.
-   The `justification` for each assessment MUST be concise and explicitly link the lever to the project's core goals, risks, or the strategic trade-offs it controls. Do not give generic reasons.
-   The final `summary` must provide a holistic view of the most important levers as a group and what strategic tensions they collectively manage.

**Example Justification:** "Critical because it dictates the entire technology stack, which directly controls the project's long-term scalability and talent acquisition risks identified in the plan."
"""

@dataclass
class FocusOnVitalFewLevers:
    """
    Analyzes brainstormed levers to identify the "vital few" based on strategic importance.
    """
    system_prompt: str
    user_prompt: str
    brainstormed_levers: list[Lever]
    assessment_result: VitalLeversAssessmentResult
    vital_levers: list[Lever]
    metadata: dict

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str, brainstormed_levers_responses: list[dict]) -> 'FocusOnVitalFewLevers':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")

        # Step 1: Flatten and deduplicate the list of all brainstormed levers
        all_levers = []
        seen_lever_names = set()
        for response in brainstormed_levers_responses:
            for lever_data in response.get('levers', []):
                # Use a normalized name for deduplication
                normalized_name = lever_data.get('name', '').lower().strip()
                if normalized_name and normalized_name not in seen_lever_names:
                    try:
                        seen_lever_names.add(normalized_name)
                        all_levers.append(Lever(**lever_data))
                    except TypeError as e:
                        logger.error(f"Error creating Lever object from data: {lever_data}. Error: {e}")
                        logger.error("Ensure input data keys match the Lever Pydantic model: 'lever_index', 'name', 'consequences', 'options', 'review_lever'.")
                        raise
        
        if not all_levers:
            raise ValueError("No valid levers found in the brainstormed responses.")
        
        logger.info(f"Consolidated {len(all_levers)} unique levers from brainstormed responses.")

        # Step 2: Prepare the input for the LLM
        # Format the list of levers for the prompt
        formatted_levers_list = []
        for i, lever in enumerate(all_levers):
            # The Lever model uses `lever_index`, which is what we should use.
            formatted_levers_list.append(f"{lever.lever_index}. **{lever.name}**: {lever.review_lever}")
        
        levers_prompt_text = "\n".join(formatted_levers_list)
        
        # This will be the user prompt for this specific step
        focus_prompt = (
            f"**Project Plan:**\n{user_prompt}\n\n"
            f"**Candidate Levers List:**\n"
            f"Please assess the strategic importance of the following {len(all_levers)} levers based on the project plan:\n\n"
            f"{levers_prompt_text}"
        )

        system_prompt = FOCUS_LEVERS_SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=focus_prompt)
        ]

        # Step 3: Run the LLM to get the assessment
        def execute_function(llm: LLM) -> dict:
            sllm = llm.as_structured_llm(VitalLeversAssessmentResult)
            chat_response = sllm.chat(chat_message_list)
            metadata = dict(llm.metadata)
            metadata["llm_classname"] = llm.class_name()
            return {
                "chat_response": chat_response,
                "metadata": metadata
            }
        
        try:
            result = llm_executor.run(execute_function)
            assessment_result = result["chat_response"].raw
            metadata = result["metadata"]
        except PipelineStopRequested:
            raise
        except Exception as e:
            logger.error("LLM chat interaction for focusing levers failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e
            
        # Step 4: Select the "vital few" levers based on the assessment
        vital_levers = cls.select_top_levers(
            all_levers=all_levers,
            assessment=assessment_result,
            target_count=TARGET_VITAL_LEVER_COUNT
        )
        logger.info(f"Selected {len(vital_levers)} vital levers.")

        return cls(
            system_prompt=system_prompt,
            user_prompt=focus_prompt,
            brainstormed_levers=all_levers,
            assessment_result=assessment_result,
            vital_levers=vital_levers,
            metadata=metadata
        )

    @staticmethod
    def select_top_levers(all_levers: list[Lever], assessment: VitalLeversAssessmentResult, target_count: int) -> list[Lever]:
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
        
        selected_indices = set()
        
        # Prioritize in order: Critical -> High -> Medium -> Low
        for importance_level in [StrategicImportance.critical, StrategicImportance.high, StrategicImportance.medium, StrategicImportance.low]:
            if len(selected_indices) >= target_count:
                break
            indices_to_add = assessments_by_importance[importance_level]
            for index in indices_to_add:
                selected_indices.add(index)

        # Retrieve the full Lever objects for the selected indices, preserving original order if possible.
        all_levers_by_index = {lever.lever_index: lever for lever in all_levers}
        vital_levers = [all_levers_by_index[i] for i in sorted(list(selected_indices)) if i in all_levers_by_index]
        
        # If we have more than the target, we must trim. We will trim from the lowest importance included.
        if len(vital_levers) > target_count:
            importance_map = {ass.lever_index: ass.strategic_importance for ass in assessment.lever_assessments}
            sort_order = {StrategicImportance.critical: 0, StrategicImportance.high: 1, StrategicImportance.medium: 2, StrategicImportance.low: 3}
            
            vital_levers.sort(key=lambda lever: sort_order.get(importance_map.get(lever.lever_index), 99))
            vital_levers = vital_levers[:target_count]

        return vital_levers

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        """Returns a dictionary representation, including the final list of vital levers."""
        d = {
            "assessment_result": self.assessment_result.model_dump(),
            "vital_levers": [lever.model_dump() for lever in self.vital_levers]
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
            json.dump(self.to_dict(), f, indent=2)

    def save_vital_levers(self, file_path: str) -> None:
        """Saves just the final list of vital levers to a file."""
        vital_levers_dict = {
            "levers": [lever.model_dump() for lever in self.vital_levers]
        }
        with open(file_path, 'w') as f:
            json.dump(vital_levers_dict, f, indent=2)


if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- Step 1: Load and Parse the Custom Text File ---
    # This block replaces the previous logic for loading sample JSON.
    # It now loads the user-specified .txt file and parses it.
    test_data_file = "planexe/strategic_variant_analysis/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt"
    
    if not os.path.exists(test_data_file):
        logger.error(f"Test data file not found at: {test_data_file}")
        exit(1)

    with open(test_data_file, 'r', encoding='utf-8') as f:
        test_data_content = f.read()

    # Parse the content into the project plan and the levers JSON string
    try:
        plan_part, levers_part = test_data_content.split("file: 'potential_levers.json':")
        query = plan_part.replace("file: 'plan.txt':", "").strip()
        levers_json_str = levers_part.strip()
        raw_levers_list = json.loads(levers_json_str)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"Failed to parse the test data file. Ensure it contains the 'file: 'potential_levers.json':' separator and valid JSON. Error: {e}")
        exit(1)

    # Adapt the parsed data to the format expected by the Lever Pydantic model
    adapted_levers = []
    for i, raw_lever in enumerate(raw_levers_list):
        adapted_levers.append({
            "lever_index": i,  # Use the list index as the lever_index
            "name": raw_lever.get("name"),
            "consequences": raw_lever.get("consequences"),
            "options": raw_lever.get("options"),
            "review_lever": raw_lever.get("review")  # Map 'review' to 'review_lever'
        })
        
    # The execute method expects a list of responses, where each response has a 'levers' key.
    brainstormed_responses = [{"levers": adapted_levers}]


    # --- Step 2: Focus on the Vital Few ---
    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    print(f"Original Query:\n{query}\n")
    
    focus_result = FocusOnVitalFewLevers.execute(
        llm_executor=llm_executor,
        user_prompt=query,
        brainstormed_levers_responses=brainstormed_responses
    )
    
    # --- Step 3: Display and Save Results ---
    print("\n--- Assessment Result ---")
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