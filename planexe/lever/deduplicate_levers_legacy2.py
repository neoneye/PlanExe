"""
The identify_potential_levers.py script creates a list of levers, some of which are duplicates, some of which are poorly thought out.
This script deduplicates the list and improves the texts.

PROMPT> python -m planexe.lever.deduplicate_levers_legacy2
"""
from enum import Enum
import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Union, Literal
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field, ValidationError, RootModel
from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logger = logging.getLogger(__name__)

class StopAction(BaseModel):
    """When the levers have been cleaned up."""
    action_type: Literal["stop"] = Field(description="Type of action to perform")
    reasoning: str = Field(
        description="Explain the action. Use ~80 words."
    )
    diagnostics_levers: str = Field(
        description="Are there any obvious duplicates? 30 words."
    )
    confidence: int = Field(
        description="Rank the confidence in the action. 0-10."
    )

class RenameAction(BaseModel):
    """Action to rename a lever."""
    action_type: Literal["rename"] = Field(description="Type of action to perform")
    lever_index: int = Field(
        description="The index of the lever to be renamed."
    )
    reasoning: str = Field(
        description="Explain the action. Use ~80 words."
    )
    name: str = Field(
        description="New name for the lever"
    )
    confidence: int = Field(
        description="Rank the confidence in the action. 0-10."
    )

class MergeAction(BaseModel):
    """Action to merge two or more levers."""
    action_type: Literal["merge"] = Field(description="Type of action to perform")
    reasoning: str = Field(
        description="Explain the action. Use ~80 words."
    )
    lever_indexes: list[int] = Field(
        description="The levers that are to be merged."
    )
    name: str = Field(
        description="New name for the lever"
    )
    diagnostics_name: str = Field(
        description="Does the new name capture the original names? 30 words."
    )
    consequences: str = Field(
        description="Briefly describe the likely second-order effects or consequences of pulling this lever (e.g., 'Choosing a high-risk tech strategy will likely increase talent acquisition difficulty and require a larger contingency budget.'). 30 words."
    )
    diagnostics_consequences: str = Field(
        description="Is the new consequences worse than the original consequences fields? 30 words."
    )
    options: List[str] = Field(
        description="New options for the lever."
    )
    diagnostics_options: str = Field(
        description="Does the new options capture the original options? 30 words."
    )
    review: str = Field(
        description="New review for the lever."
    )
    diagnostics_review: str = Field(
        description="Does the new review capture the insights of the original review fields? 30 words."
    )
    confidence: int = Field(
        description="Rank the confidence in the action. 0-10. If the proposed new lever is not better than the original levers, then set the confidence to 0. If the proposed new lever is better than the original levers, then set the confidence to 10. If there are any flaws, then set the confidence to 5."
    )

# Create a discriminated union using RootModel
class PerformAction(RootModel):
    """Union of possible actions that can be performed on levers."""
    root: Union[RenameAction, MergeAction, StopAction] = Field(discriminator='action_type')

class Lever(BaseModel):
    """Represents a single lever."""
    item_index: int = -1
    lever_id: str
    name: str
    consequences: str
    options: List[str]
    review: str


CONSOLIDATE_LEVERS_SYSTEM_PROMPT = """
Your job is to tidy up a list of strategic levers.

The final list is supposed to be a MECE (Mutually Exclusive, Collectively Exhaustive) set of levers.

Your primary task is to merge the **most obvious pair of redundant levers** based on their functional similarity.

## Actions

You can perform the following actions:

- Merge two levers into one
- Rename a lever
- Stop the process

## Merge two levers

The response MUST be formatted as:
```json
{
  "action_type": "merge",
  "reasoning": "<explanation what theme does these levers have in common>"
  "lever_indexes": <list of indexes to be merged>,
  "consequences": "<new consequences by combining the consequences of the original levers>",
  "diagnostics_consequences": "<is the new consequences really better than the original consequences?>",
  "name": "<new name>",
  "diagnostics_name": "<is the new name really better than the original names?>",
  "options": <list with new options>,
  "diagnostics_options": "<does the new options really cover all the options of the original levers?>"
  "review": "<new review by combining the reviews of the original levers>",
  "diagnostics_review": "<did I make mistakes when combining the reviews of the original levers?>",
  "confidence": <0-10>
}
```

## Rename a lever

The response MUST be formatted as:
```json
{
  "action_type": "rename",
  "lever_index": <index>,
  "reasoning": "<explain why the new name is better>",
  "name": "<new name>",
  "confidence": <0-10>
}
```

## Stop the process

Are there any obvious duplicates? If so, then do the 'merge' action.
Are there a names that are terrible? If so, then do the 'rename' action.
Otherwise, do the 'stop' action.

The response MUST be formatted as:
```json
{
  "action_type": "stop",
  "reasoning": "<explain why you are stopping the process>",
  "diagnostics_levers": "<are there any obvious duplicates? 30 words.>",
  "confidence": <0-10>
}
```

"""

@dataclass
class ConsolidateLevers:
    """Clean up the list of potential levers."""
    user_prompt: str
    system_prompt: str
    levers: List[Lever]
    response_list: List[PerformAction]
    metadata_list: List[Dict[str, Any]]

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, project_context: str, raw_levers_list: List[dict]) -> 'ConsolidateLevers':
        """
        Executes the deduplication process.

        Args:
            llm_executor: The configured LLMExecutor instance.
            raw_levers_list: A list of dictionaries, each representing a lever.

        Returns:
            An instance of DeduplicateLevers containing the results.
        """
        try:
            levers = [Lever(**lever) for lever in raw_levers_list]
        except ValidationError as e:
            raise ValueError(f"Invalid input lever data: {e}")

        if not levers:
            raise ValueError("No input levers to deduplicate.")
        
        logger.info(f"Starting cleaning up for {len(levers)} levers.")


        system_prompt = CONSOLIDATE_LEVERS_SYSTEM_PROMPT.strip()

        response_list = []
        metadata_list = []

        refinement_steps = 10
        for refinement_step in range(refinement_steps):
            logger.info(f"Refinement step {refinement_step+1} of {refinement_steps}")

            # Assign item_index to each lever
            for i, lever in enumerate(levers):
                lever.item_index = i

            levers_json = json.dumps([lever.model_dump() for lever in levers], indent=2)        
            user_prompt = (
                f"**Project Context:**\n{project_context}\n\n"
                "Below is the list of levers that are to be cleaned up.\n\n"
                f"{levers_json}"
            )
            chat_message_list = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_prompt)
            ]

            def execute_function(llm: LLM) -> dict:
                sllm = llm.as_structured_llm(PerformAction)
                chat_response = sllm.chat(chat_message_list)
                metadata = dict(llm.metadata)
                return {"chat_response": chat_response, "metadata": metadata}

            try:
                result = llm_executor.run(execute_function)
            except PipelineStopRequested:
                raise
            except Exception as e:
                logger.error("Deduplication failed.", exc_info=True)
                raise ValueError("Deduplication failed.") from e

            response: PerformAction = result["chat_response"].raw
            action = response.root
            response_list.append(action)
            metadata_list.append(result["metadata"])

            # Apply the action to the input_levers
            if action.action_type == "merge":
                logger.info(f"Action: Merging lever {action.lever_indexes}. reasoning: {action.reasoning!r}")
                if len(action.lever_indexes) < 2:
                    logger.info(f"Invalid merge action: {action.lever_indexes!r}. Must be a list of at least 2 indexes. Skipping.")
                    continue

                # Reject the action if any of the lever indexes are out of range.
                valid_lever_indexes = True
                for lever_index in action.lever_indexes:
                    if lever_index < 0 or lever_index >= len(levers):
                        logger.info(f"Invalid merge action: {action.lever_indexes!r}. Lever index {lever_index} is out of range. Skipping.")
                        valid_lever_indexes = False

                if not valid_lever_indexes:
                    logger.info(f"Invalid merge action: {action.lever_indexes!r}. Skipping.")
                    continue

                # Reject the action if the lever indexes are not unique.
                if len(action.lever_indexes) != len(set(action.lever_indexes)):
                    logger.info(f"Invalid merge action: {action.lever_indexes!r}. Lever indexes are not unique. Skipping.")
                    continue

                if action.confidence < 5:
                    logger.info(f"Ignoring the action, because the confidence is too low. confidence: {action.confidence}")
                    continue

                for lever_index in sorted(action.lever_indexes):
                    logger.info(f"Lever[{lever_index}] BEFORE merge: {levers[lever_index].name!r}")

                # Remove items by index. Higher index first to avoid shifting issues.
                for lever_index in sorted(action.lever_indexes, reverse=True):
                    del levers[lever_index]
                
                new_lever = Lever(
                    lever_id=str(uuid.uuid4()),
                    name=action.name,
                    consequences=action.consequences,
                    options=action.options,
                    review=action.review
                )
                levers.append(new_lever)
                logger.info(f"New lever AFTER merge: {new_lever!r}")
            elif action.action_type == "rename":
                logger.info(f"Action: Renaming lever {action.lever_index} to {action.name!r}. reasoning: {action.reasoning!r}")
                if action.confidence < 5:
                    logger.info(f"Ignoring the action, because the confidence is too low. confidence: {action.confidence}")
                    continue
                logger.info(f"Lever BEFORE rename: {levers[action.lever_index].name!r}")
                levers[action.lever_index].name = action.name
                logger.info(f"Lever AFTER rename: {levers[action.lever_index].name!r}")
            elif action.action_type == "stop":
                logger.info(f"Action: Stopping the process. reasoning: {action.reasoning!r}")
                if action.confidence < 5:
                    logger.info(f"Ignoring the action, because the confidence is too low. confidence: {action.confidence}")
                    continue
                break

        return cls(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            levers=levers,
            response_list=response_list,
            metadata_list=metadata_list
        )

    def to_dict(self, include_response=True, include_levers=True, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = {}
        if include_response:
            d["responses"] = [response.model_dump() for response in self.response_list]
        if include_levers:
            d["levers"] = [lever.model_dump() for lever in self.levers]
        if include_metadata:
            d['metadata'] = self.metadata_list
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        Path(file_path).write_text(json.dumps(self.to_dict(), indent=2))

    def save_clean(self, file_path: Path) -> None:
        """Saves the final, deduplicated list of levers to a JSON file."""
        output_data = [lever.model_dump() for lever in self.levers]
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)
            logger.info(f"Successfully saved {len(output_data)} deduplicated levers to {file_path!r}.")
        except IOError as e:
            logger.error(f"Failed to write output to {file_path!r}: {e}")

if __name__ == "__main__":
    from planexe.prompt.prompt_catalog import PromptCatalog
    from planexe.llm_util.llm_executor import LLMModelFromName

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_simple_plan_prompts()

    prompt_id = "19dc0718-3df7-48e3-b06d-e2c664ecc07d"
    # prompt_id = "b9afce6c-f98d-4e9d-8525-267a9d153b51"
    prompt_item = prompt_catalog.find(prompt_id)
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    project_context = prompt_item.prompt

    # This file is created by identify_potential_levers.py
    input_file = os.path.join(os.path.dirname(__file__), 'test_data', f'identify_potential_levers_{prompt_id}.json')
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_levers_data = json.load(f)

    output_file = f"consolidate_levers_{prompt_id}.json"

    model_names = ["ollama-llama3.1"]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    result = ConsolidateLevers.execute(
        llm_executor=llm_executor,
        project_context=project_context,
        raw_levers_list=raw_levers_data
    )

    d = result.to_dict(include_response=True, include_metadata=True, include_system_prompt=False, include_user_prompt=False)
    d_json = json.dumps(d, indent=2)
    logger.info(f"Result: {d_json}")

    # result.save_clean(output_file)
