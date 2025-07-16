"""
This was generated with Gemini 2.5 Pro.
Enrich all levers with a "description" field.

- This module takes the brainstormed list of potential levers from the previous step.
- It uses an LLM to generate a detailed "description" for each lever.
- The description clarifies the lever's purpose, scope, mechanism, objectives, and key metrics, making it easier for stakeholders to understand and evaluate.
- This enrichment is done in batches to handle a large number of levers efficiently.
- The output is a new JSON file containing the original levers with the added description field.

PROMPT> python -m planexe.lever.enrich_potential_levers_legacy1
"""
import json
import logging
import os
from dataclasses import dataclass
from typing import List, Dict

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, ValidationError

from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logger = logging.getLogger(__name__)

# The number of levers to process in a single call to the LLM.
BATCH_SIZE = 5

# --- Pydantic Models for Data Structuring ---

class InputLever(BaseModel):
    """Represents a single lever loaded from the input file."""
    id: str
    name: str
    consequences: str
    options: List[str]
    review: str

class LeverDescription(BaseModel):
    """Structured response for a single lever's description from the LLM."""
    lever_id: str = Field(description="The ID of the lever being described, e.g., 'Lever-1'.")
    description: str = Field(
        description="A comprehensive description (100-150 words) covering the lever's purpose, scope, mechanism, objectives, and key success metrics."
    )

class BatchDescriptionResult(BaseModel):
    """The expected JSON structure for a batch of descriptions from the LLM."""
    descriptions: List[LeverDescription] = Field(
        description="A list containing the description for each requested lever in the batch."
    )

class EnrichedLever(InputLever):
    """The final, enriched lever model, including the new description field."""
    description: str

# --- LLM Prompts ---

ENRICH_LEVERS_SYSTEM_PROMPT = """
You are an expert strategic analyst. Your task is to enrich a list of strategic levers with detailed descriptions based on a provided project context.

**Goal:** For each provided lever, generate a comprehensive `description` that explains its strategic importance.

**Description Requirements:**
A good description is 100-150 words and MUST:
1.  **Define Purpose & Scope:** Clearly state what the lever controls and the strategic dimension it operates on (e.g., "This lever controls the project's core manufacturing philosophy, dictating the trade-off between centralized efficiency and decentralized adaptability.").
2.  **Explain the Mechanism:** Briefly describe how adjusting the lever's options leads to different strategic pathways and outcomes.
3.  **Summarize Objectives & Impact:** State what the lever aims to achieve (e.g., balancing cost, speed, innovation) and its potential impact range on the project's success.
4.  **Highlight Key Metrics:** Suggest 1-2 key metrics to measure the success of a chosen option for this lever (e.g., "Success is measured by 'time-to-market' and 'long-term scalability'.").
5.  **Identify Prerequisites:** Mention any critical dependencies or conditions required for the lever to be effective (e.g., "Effective use of this lever requires significant upfront investment in R&D...").

You MUST respond with a single JSON object that strictly adheres to the `BatchDescriptionResult` schema.
You MUST provide a description for every single lever requested in the user prompt.
"""

@dataclass
class EnrichPotentialLeversResult:
    """Holds the results of the enrichment process."""
    enriched_levers: List[EnrichedLever]
    metadata: List[Dict]

    def to_dict(self) -> dict:
        """Converts the result to a dictionary for serialization."""
        return {
            "metadata": self.metadata,
            "enriched_levers": [lever.model_dump() for lever in self.enriched_levers]
        }

    def save(self, file_path: str) -> None:
        """Saves the enriched levers to a JSON file."""
        output_data = {
            "enriched_levers": [lever.model_dump() for lever in self.enriched_levers]
        }
        with open(file_path, 'w') as f:
            json.dump(output_data, f, indent=2)

class EnrichPotentialLevers:
    """
    A class to manage the process of enriching potential levers with LLM-generated descriptions.
    """

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, project_plan: str, levers_to_enrich: List[InputLever]) -> EnrichPotentialLeversResult:
        """
        Executes the enrichment process in batches.

        Args:
            llm_executor: The LLM executor instance.
            project_plan: The overall project context.
            levers_to_enrich: A list of InputLever objects to be enriched.

        Returns:
            An EnrichPotentialLeversResult object containing the enriched levers.
        """
        if not levers_to_enrich:
            raise ValueError("The list of levers to enrich cannot be empty.")

        enriched_levers_map = {lever.id: lever.model_dump() for lever in levers_to_enrich}
        all_metadata = []

        system_message = ChatMessage(role=MessageRole.SYSTEM, content=ENRICH_LEVERS_SYSTEM_PROMPT.strip())

        # Process levers in batches
        for i in range(0, len(levers_to_enrich), BATCH_SIZE):
            batch = levers_to_enrich[i:i + BATCH_SIZE]
            if not batch:
                continue
            
            logger.info(f"Processing batch {i//BATCH_SIZE + 1} with {len(batch)} levers...")

            lever_details_for_prompt = []
            for lever in batch:
                details = (
                    f"Lever:\n"
                    f"- ID: {lever.id}\n"
                    f"- Name: {lever.name}\n"
                    f"- Options: {json.dumps(lever.options)}\n"
                    f"- Review: {lever.review}"
                )
                lever_details_for_prompt.append(details)

            user_prompt = (
                f"**Project Context:**\n{project_plan}\n\n"
                "---\n\n"
                f"**Levers to Describe:**\n"
                f"Please generate a detailed description for the following {len(batch)} levers. "
                f"Provide the output in the requested JSON format.\n\n"
                "\n".join(lever_details_for_prompt)
            )

            chat_message_list = [system_message, ChatMessage(role=MessageRole.USER, content=user_prompt)]

            def execute_function(llm: LLM) -> dict:
                sllm = llm.as_structured_llm(BatchDescriptionResult)
                chat_response = sllm.chat(chat_message_list)
                metadata = dict(llm.metadata)
                metadata["llm_classname"] = llm.class_name()
                return {
                    "chat_response": chat_response,
                    "metadata": metadata
                }

            try:
                result = llm_executor.run(execute_function)
                batch_result: BatchDescriptionResult = result["chat_response"].raw
                all_metadata.append(result["metadata"])

                for desc in batch_result.descriptions:
                    if desc.lever_id in enriched_levers_map:
                        enriched_levers_map[desc.lever_id]['description'] = desc.description
                    else:
                        logger.warning(f"LLM returned a description for an unknown or mismatched lever_id: '{desc.lever_id}'")

            except PipelineStopRequested:
                raise
            except Exception as e:
                logger.error(f"LLM batch interaction failed for levers {[l.id for l in batch]}.", exc_info=True)
                raise ValueError("LLM batch interaction failed.") from e

        # --- CORRECTED & ROBUST FINAL CONVERSION ---
        # Instead of a direct list comprehension, we loop and check each item.
        # This prevents a crash if a description is missing for any lever.
        final_enriched_levers = []
        for lever_id, data in enriched_levers_map.items():
            if 'description' in data:
                try:
                    # Validate and create the final Pydantic object
                    final_enriched_levers.append(EnrichedLever(**data))
                except ValidationError as e:
                    logger.error(f"Pydantic validation failed for enriched lever '{lever_id}' even though description key exists. Error: {e}")
            else:
                # This is the crucial log that explains the problem.
                logger.error(f"Enrichment failed for lever '{lever_id}'. No description was generated or added. Skipping this lever in the final output.")
        
        return EnrichPotentialLeversResult(
            enriched_levers=final_enriched_levers,
            metadata=all_metadata
        )

if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    input_file = "planexe/lever/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.txt"
    output_file = "enriched_potential_levers.json"
    
    if not os.path.exists(input_file):
        logger.error(f"Input data file not found at: {input_file}")
        exit(1)

    with open(input_file, 'r', encoding='utf-8') as f:
        test_data_content = f.read()

    try:
        plan_part, levers_part = test_data_content.split("file: 'potential_levers.json':")
        project_plan = plan_part.replace("file: 'plan.txt':", "").strip()
        levers_json_str = levers_part.strip()
        raw_levers_list = json.loads(levers_json_str)
        input_levers = [InputLever(**lever) for lever in raw_levers_list]
    except (ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Failed to parse the input data file '{input_file}'. Ensure it contains 'file: 'potential_levers.json':' and valid JSON matching the InputLever schema. Error: {e}")
        exit(1)
        
    logger.info(f"Successfully loaded {len(input_levers)} levers from '{input_file}'.")

    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    try:
        result = EnrichPotentialLevers.execute(
            llm_executor=llm_executor,
            project_plan=project_plan,
            levers_to_enrich=input_levers
        )

        print(f"\nSuccessfully processed all batches. Enriched {len(result.enriched_levers)} out of {len(input_levers)} levers.")
        
        if result.enriched_levers:
            print("\n--- Example Enriched Lever ---")
            example_lever = result.enriched_levers[0]
            print(json.dumps(example_lever.model_dump(), indent=2))
        
            result.save(output_file)
            logger.info(f"Full list of {len(result.enriched_levers)} enriched levers saved to '{output_file}'.")
        else:
            logger.warning("No levers were successfully enriched. Output file will not be created.")

    except (ValueError) as e:
        logger.error(f"An unrecoverable error occurred during the enrichment process: {e}")