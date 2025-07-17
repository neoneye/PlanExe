"""
Step 2: Deduplicate Near-Identical Levers (LLM-based)

For removing duplicates, using vector embeddings are often used.
However this script uses LLMs to identify and remove near-duplicate levers.

The LLM is instructed to find groups of similar levers, keep the best one from
each group, and generate a "removal list" for the redundant ones.

PROMPT> python -m planexe.lever.deduplicate_levers \
    --input planexe/lever/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.json \
    --output deduplicated.json
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any
import argparse

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, ValidationError

from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Pydantic Models for Data Structuring ---

class InputLever(BaseModel):
    """Represents a single lever loaded from the initial brainstormed file."""
    lever_id: str
    name: str
    consequences: str
    options: List[str]
    review: str

class RemoveItem(BaseModel):
    """Represents a single lever that should be removed due to duplication."""
    lever_id: str = Field(
        description="The unique ID of the lever that should be removed."
    )
    reason_for_removal: str = Field(
        description="A concise explanation for the removal. Crucially, this MUST state which lever is being kept in its place. Example: 'This is a redundant, more generic version of lever [ID of kept lever], which better captures the specific manufacturing choices.'"
    )

class DeduplicationResult(BaseModel):
    """The structured response from the LLM, containing the list of levers to remove."""
    items_to_remove: List[RemoveItem] = Field(
        description="A list of all levers identified as duplicates and recommended for removal."
    )

# --- LLM Prompt ---

DEDUPLICATE_SYSTEM_PROMPT = """
You are a meticulous and ruthless strategic analyst. Your task is to review a list of strategic levers and rationalize it by removing near-duplicates.

**Your Goal:**
Identify groups of levers that address the same core concept. For each group, you must keep **EXACTLY ONE** lever (the one that is most specific, well-defined, or comprehensive) and mark all others in that group for removal.

**Criteria for a "Duplicate":**
- **Semantic Overlap:** The levers describe the same fundamental choice, even with different words. For example, "Material Feedstock Optimization" and "Material Sourcing and Sourcing" are duplicates.
- **Subset Relationship:** One lever is a more generic version of another. For example, "Technology Integration" is a generic version of "Emerging Technologies Integration Strategy". You should remove the more generic one.
- **Redundant Concepts:** Multiple levers focus on the same aspect, like 'modularity'. Pick the best single lever that represents the "modularity" choice and remove the others.

**Output Requirements:**
- You MUST respond with a single JSON object that strictly adheres to the `DeduplicationResult` schema.
- The `items_to_remove` list should ONLY contain the levers to be discarded. Do not include the levers you decide to keep.
- For each `RemoveItem`, the `reason_for_removal` is critical. It MUST clearly state which lever is being kept.
"""

@dataclass
class DeduplicateLevers:
    """Holds the results of the LLM-based deduplication process."""
    raw_levers: List[InputLever]
    deduplication_result: DeduplicationResult
    deduplicated_levers: List[InputLever]
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, raw_levers_list: List[dict]) -> 'DeduplicateLevers':
        """
        Executes the deduplication process using an LLM.

        Args:
            llm_executor: The configured LLMExecutor instance.
            raw_levers_list: A list of dictionaries, each representing a lever.

        Returns:
            An instance of DeduplicateLevers containing the results.
        """
        try:
            levers = [InputLever(**lever) for lever in raw_levers_list]
        except ValidationError as e:
            logger.error(f"Input data does not match the expected Lever schema. Error: {e}")
            raise ValueError("Invalid input lever data.") from e

        if not levers:
            logger.warning("The list of levers to deduplicate is empty.")
            return cls(raw_levers=[], deduplication_result=DeduplicationResult(items_to_remove=[]), deduplicated_levers=[], metadata={})

        logger.info(f"Starting deduplication for {len(levers)} levers using LLM.")

        # Format the levers into a text block for the prompt
        formatted_levers = []
        for i, lever in enumerate(levers):
            formatted_levers.append(
                f"--- Lever {i+1} ---\n"
                f"ID: {lever.lever_id}\n"
                f"Name: {lever.name}\n"
                f"Consequences: {lever.consequences}"
            )
        levers_text_block = "\n\n".join(formatted_levers)

        user_prompt = (
            "Here is the full list of strategic levers. Please analyze them for duplicates "
            "according to the rules and provide the JSON list of items to remove.\n\n"
            f"{levers_text_block}"
        )

        system_prompt = DEDUPLICATE_SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt)
        ]

        # Define the function to be executed by the LLMExecutor
        def execute_function(llm: LLM) -> dict:
            sllm = llm.as_structured_llm(DeduplicationResult)
            chat_response = sllm.chat(chat_message_list)
            metadata = dict(llm.metadata)
            metadata["llm_classname"] = llm.class_name()
            return {"chat_response": chat_response, "metadata": metadata}

        try:
            result = llm_executor.run(execute_function)
            deduplication_result: DeduplicationResult = result["chat_response"].raw
            metadata = result["metadata"]
        except PipelineStopRequested:
            raise
        except Exception as e:
            logger.error("LLM interaction for deduplication failed.", exc_info=True)
            raise ValueError("LLM interaction failed.") from e

        # Process the result to create the final list
        ids_to_remove = {item.lever_id for item in deduplication_result.items_to_remove}
        logger.info(f"LLM recommended removing {len(ids_to_remove)} levers.")
        for item in deduplication_result.items_to_remove:
            logger.info(f" - Removing '{item.lever_id}': {item.reason_for_removal}")

        deduplicated_levers = [lever for lever in levers if lever.lever_id not in ids_to_remove]
        logger.info(f"Final lever count after deduplication: {len(deduplicated_levers)}.")

        return cls(
            raw_levers=levers,
            deduplication_result=deduplication_result,
            deduplicated_levers=deduplicated_levers,
            metadata=metadata
        )

    def save_clean(self, file_path: Path) -> None:
        """Saves the final, deduplicated list of levers to a JSON file."""
        output_data = [lever.model_dump() for lever in self.deduplicated_levers]
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)
            logger.info(f"Successfully saved {len(output_data)} deduplicated levers to '{file_path}'.")
        except IOError as e:
            logger.error(f"Failed to write output to '{file_path}': {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deduplicate a list of strategic levers using an LLM.")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the input JSON file containing a list of levers."
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to the output JSON file for the deduplicated levers."
    )
    args = parser.parse_args()

    # --- Load Input ---
    if not args.input.is_file():
        logger.error(f"Input file not found: {args.input}")
        raise ValueError(f"Input file not found: {args.input}")

    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            raw_levers_data = json.load(f)
        logger.info(f"Successfully loaded {len(raw_levers_data)} levers from '{args.input}'.")
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading input file '{args.input}': {e}")
        raise ValueError(f"Error reading input file '{args.input}': {e}")

    # --- Setup LLMExecutor ---
    # This part should be adapted to your project's LLM configuration
    from planexe.llm_util.llm_executor import LLMModelFromName
    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    # --- Run Deduplication ---
    try:
        result = DeduplicateLevers.execute(
            llm_executor=llm_executor,
            raw_levers_list=raw_levers_data
        )

        # --- Save Output ---
        result.save_clean(args.output)

    except (ValueError, PipelineStopRequested) as e:
        logger.error(f"Deduplication process failed: {e}")
