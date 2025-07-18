"""
Step 2: Deduplicate Near-Identical Levers (LLM-based)

For removing duplicates, using vector embeddings are often used.
However this script uses LLMs to identify and remove near-duplicate levers.

The LLM is instructed to find groups of similar levers, keep the best one from
each group, and generate a "removal list" for the redundant ones.

PROMPT> python -m planexe.lever.deduplicate_levers_legacy1 \
    --input planexe/lever/test_data/identify_potential_levers_19dc0718-3df7-48e3-b06d-e2c664ecc07d.json \
    --output deduplicated.json
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Dict, Any, Set
import argparse

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, ValidationError

from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Pydantic Models for Data Structuring ---

class RemovalInstruction(BaseModel):
    """Represents a single lever that should be removed due to duplication."""
    lever_id_to_remove: str = Field(
        description="The unique ID of the lever that should be removed."
    )
    reason_for_removal: str = Field(
        description="A concise explanation for the removal. This MUST state which lever is being kept in its place by referencing its ID explicitly. Format: 'Redundant with kept lever [ID of kept lever] because...'"
    )

class DeduplicationAnalysis(BaseModel):
    """The structured response from the LLM, containing the list of levers to remove."""
    removals: List[RemovalInstruction] = Field(
        description="A list of all levers identified as duplicates and recommended for removal."
    )

class InputLever(BaseModel):
    """Represents a single lever loaded from the initial brainstormed file."""
    lever_id: str
    name: str
    consequences: str
    options: List[str]
    review: str


DEDUPLICATE_SYSTEM_PROMPT = """
You are a meticulous and ruthless strategic analyst. Your task is to rationalize a list of strategic levers by removing near-duplicates. Your process must be logical and non-destructive.

**Your Three-Step Process:**
1.  **Group Similar Levers:** Mentally group levers that address the same core strategic concept (e.g., everything about 'modularity', everything about 'materials').
2.  **Nominate One Winner Per Group:** For each group, you MUST choose EXACTLY ONE lever to keep. The winner should be the most specific, comprehensive, or well-defined lever in its group. ALL other levers in the group must be marked for removal.
3.  **Generate Removal List:** Create a JSON list of levers to remove. A lever can ONLY be on this list if another lever from its group is being kept.

**CRITICAL RULES:**
-   **DO NOT REMOVE BOTH LEVERS IN A PAIR.** If you identify Lever A and Lever B as duplicates, you must choose one to keep and one to remove. You cannot remove both.
-   The `reason_for_removal` MUST explicitly name the ID of the lever you are KEEPING. This is mandatory.

**Output Schema:**
You MUST respond with a single JSON object that strictly adheres to the `DeduplicationAnalysis` schema.

---
**GOOD EXAMPLE:**
-   **Group:** [Lever-A: "Material Strategy"], [Lever-B: "Feedstock Sourcing"]
-   **Decision:** Lever-A is more comprehensive. Keep Lever-A, remove Lever-B.
-   **JSON Output:**
    ```json
    {
      "removals": [
        {
          "lever_id_to_remove": "Lever-B",
          "reason_for_removal": "Redundant with kept lever [Lever-A] which provides a better strategic overview of materials."
        }
      ]
    }
    ```

**BAD EXAMPLE (What you must avoid):**
-   **Incorrect Logic:** "Lever-A is a duplicate of Lever-B, so I'll remove A. Lever-B is a duplicate of Lever-A, so I'll remove B."
-   **Incorrect JSON Output:**
    ```json
    {
      "removals": [
        { "lever_id_to_remove": "Lever-A", "reason_for_removal": "Duplicate of Lever-B." },
        { "lever_id_to_remove": "Lever-B", "reason_for_removal": "Duplicate of Lever-A." }
      ]
    }
    ```
This is a logical contradiction and is forbidden. You must choose a winner.
"""

@dataclass
class DeduplicateLevers:
    """Holds the results of the LLM-based deduplication process."""
    raw_levers: List[InputLever]
    analysis_result: DeduplicationAnalysis
    deduplicated_levers: List[InputLever]
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, raw_levers_list: List[dict]) -> 'DeduplicateLevers':
        """
        Executes the deduplication process.

        Args:
            llm_executor: The configured LLMExecutor instance.
            raw_levers_list: A list of dictionaries, each representing a lever.

        Returns:
            An instance of DeduplicateLevers containing the results.
        """
        try:
            levers = [InputLever(**lever) for lever in raw_levers_list]
        except ValidationError as e:
            raise ValueError(f"Invalid input lever data: {e}")

        if not levers:
            return cls(raw_levers=[], analysis_result=DeduplicationAnalysis(removals=[]), deduplicated_levers=[], metadata={})

        logger.info(f"Starting deduplication for {len(levers)} levers.")

        formatted_levers = [f"ID: {l.lever_id}\nName: {l.name}" for l in levers]
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

        def execute_function(llm: LLM) -> dict:
            sllm = llm.as_structured_llm(DeduplicationAnalysis)
            chat_response = sllm.chat(chat_message_list)
            metadata = dict(llm.metadata)
            return {"chat_response": chat_response, "metadata": metadata}

        try:
            result = llm_executor.run(execute_function)
            analysis_result: DeduplicationAnalysis = result["chat_response"].raw
            metadata = result["metadata"]
        except PipelineStopRequested:
            raise
        except Exception as e:
            logger.error("LLM interaction for deduplication failed.", exc_info=True)
            raise ValueError("LLM interaction failed.") from e

        # --- CHANGE 3: Add post-processing safeguard ---
        ids_to_remove = {item.lever_id_to_remove for item in analysis_result.removals}
        
        # Extract all IDs that the LLM mentioned it was *keeping*.
        ids_to_keep: Set[str] = set()
        for item in analysis_result.removals:
            # Use regex to find GUIDs mentioned in the reason string
            found_ids = re.findall(r'\[([a-fA-F0-9\-]+)\]', item.reason_for_removal)
            ids_to_keep.update(found_ids)

        # Sanity Check: Identify contradictions where a lever is marked for both removal and keeping.
        contradictions = ids_to_remove.intersection(ids_to_keep)
        if contradictions:
            logger.warning(f"Contradiction detected! The LLM tried to both REMOVE and KEEP the following levers: {contradictions}")
            logger.warning("Prioritizing KEEPING these levers. They will not be removed.")
            # Resolve the contradiction by removing the conflicted IDs from the removal set.
            ids_to_remove.difference_update(contradictions)
            
        logger.info(f"LLM recommended removing {len(analysis_result.removals)} levers. After resolving contradictions, {len(ids_to_remove)} will be removed.")
        for item in analysis_result.removals:
             logger.info(f" - LLM Reason: Remove '{item.lever_id_to_remove}' because: {item.reason_for_removal}")


        deduplicated_levers = [lever for lever in levers if lever.lever_id not in ids_to_remove]
        logger.info(f"Final lever count after deduplication: {len(deduplicated_levers)}.")

        return cls(
            raw_levers=levers,
            analysis_result=analysis_result,
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
