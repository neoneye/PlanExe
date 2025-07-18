"""
PROMPT> python -m planexe.lever.deduplicate_levers2
"""
from enum import Enum
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

class LeverClassification(str, Enum):
    keep   = "keep"
    maybe  = "maybe"
    remove = "remove"

class LeverDecision(BaseModel):
    lever_id: str = Field(
        description="The uuid of the lever."
    )
    classification: LeverClassification = Field(
        description="What should happen to this lever."
    )
    justification: str = Field(
        description="A concise justification for the classification. Use the lever_id to reference the lever that is being kept in its place. Use 40 words."
    )

class DeduplicationAnalysis(BaseModel):
    decisions: List[LeverDecision] = Field(
        description="A list of all levers with their classification and justification."
    )
    summary: str = Field(
        description="How confident are you that you have removed near-duplicates? And not removed too many levers? Use a scale of -2 to +2, where 0 is neutral."
    )

class InputLever(BaseModel):
    """Represents a single lever loaded from the initial brainstormed file."""
    lever_id: str
    name: str
    consequences: str
    options: List[str]
    review: str


DEDUPLICATE_SYSTEM_PROMPT = """You are a senior strategy consultant hired to prune near-duplicate “levers”
(ideas for how to influence an infrastructure scenario).

**Task**

For *each* lever you receive:
1. Decide its `classification` from {keep | maybe | remove}
2. Give a concise `justification` (≤40 words)

**Definitions**

• keep   – best, most complete or clearest version; losing it would drop important
           content for this cluster of similar levers.
• maybe  – similarity is unclear or the text is only partly unique; flag for review.
• remove – weaker, vaguer, or redundant; every idea it contains is already present
           in another ‘keep’ lever in the same cluster.

**Output**

Return **only** valid JSON – an array of objects that satisfy the schema

[
  {"lever_id":"…","classification":"keep","justification":"…"},
  …
]

Do **not** wrap the JSON in Markdown fences.
"""

@dataclass
class DeduplicateLevers:
    """Holds the results of the LLM-based deduplication process."""
    user_prompt: str
    system_prompt: str
    analysis_result: DeduplicationAnalysis
    deduplicated_levers: List[InputLever]
    metadata: Dict[str, Any]

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, project_context: str, raw_levers_list: List[dict]) -> 'DeduplicateLevers':
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
            raise ValueError("No levers to deduplicate.")

        logger.info(f"Starting deduplication for {len(levers)} levers.")

        levers_json = json.dumps([lever.model_dump() for lever in levers], indent=2)        
        user_prompt = (
            f"**Project Context:**\n{project_context}\n\n"
            "Here is the full list of strategic levers. Please analyze them for duplicates.\n\n"
            f"{levers_json}"
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

        # Create a mapping from lever_id to classification
        classification_map = {decision.lever_id: decision.classification for decision in analysis_result.decisions}
        
        # Filter levers based on their classification
        levers_keep = [lever for lever in levers if classification_map.get(lever.lever_id) == LeverClassification.keep]
        levers_maybe = [lever for lever in levers if classification_map.get(lever.lever_id) == LeverClassification.maybe]
        deduplicated_levers = levers_keep + levers_maybe
        logger.info(f"Final lever count after deduplication: {len(deduplicated_levers)}.")

        return cls(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            analysis_result=analysis_result,
            deduplicated_levers=deduplicated_levers,
            metadata=metadata
        )

    def to_dict(self, include_raw_response=True, include_deduplicated_levers=True, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = {}
        if include_raw_response:
            d["raw_response"] = self.analysis_result.model_dump()
        if include_deduplicated_levers:
            d['deduplicated_levers'] = [lever.model_dump() for lever in self.deduplicated_levers]
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        Path(file_path).write_text(json.dumps(self.to_dict(), indent=2))

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
    from planexe.prompt.prompt_catalog import PromptCatalog
    from planexe.llm_util.llm_executor import LLMModelFromName

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_simple_plan_prompts()

    prompt_id = "19dc0718-3df7-48e3-b06d-e2c664ecc07d"
    prompt_item = prompt_catalog.find(prompt_id)
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    project_context = prompt_item.prompt

    # This file is created by identify_potential_levers.py
    input_file = os.path.join(os.path.dirname(__file__), 'test_data', f'identify_potential_levers_{prompt_id}.json')
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_levers_data = json.load(f)

    output_file = f"deduplicate_levers_{prompt_id}.json"

    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    # --- Run Deduplication ---
    result = DeduplicateLevers.execute(
        llm_executor=llm_executor,
        project_context=project_context,
        raw_levers_list=raw_levers_data
    )

    d = result.to_dict(include_raw_response=True, include_deduplicated_levers=True, include_metadata=True, include_system_prompt=False, include_user_prompt=False)
    d_json = json.dumps(d, indent=2)
    logger.info(f"Deduplication result: {d_json}")

    # --- Save Output ---
    result.save_clean(output_file)
