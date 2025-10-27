"""
Measure from a checklist of items, if the plan is viable.

PROMPT> python -m planexe.viability.measure2
"""
import json
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import uuid
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logger = logging.getLogger(__name__)

class ChecklistAnswer(BaseModel):
    checklist_index: int = Field(
        description="Index of this checklist item."
    )
    value: int = Field(
        description="Parameter value -2 to 2. Where -2 is the strong negative, -1 is the weak negative, 0 is neutral, 1 is the weak positive, 2 is the strong positive."
    )

class DocumentDetails(BaseModel):
    checklist_answers: list[ChecklistAnswer] = Field(
        description="Answers to the checklist."
    )

class ChecklistAnswerCleaned(BaseModel):
    checklist_index: int = Field(
        description="Index of this checklist item."
    )
    checklist_item_id: str = Field(
        description="Id of this checklist item."
    )
    checklist_item_explanation: str = Field(
        description="Explain this measurement. 30 words."
    )
    value: int = Field(
        description="Parameter value -2 to 2. Where -2 is the strong negative, -1 is the weak negative, 0 is neutral, 1 is the weak positive, 2 is the strong positive."
    )

CHECKLIST = [
    {
        "index": 1,
        "id": "fantasy technology",
        "explanation": "does this project rely on tech such as faster than light travel, that isn't grounded in reality",
    },
    {
        "index": 2,
        "id": "unproven technology",
        "explanation": "does this project rely on a new technology that has never been used before. eg. a white paper that hasn't been tested in the real world",
    },
    {
        "index": 3,
        "id": "use of buzzwords",
        "explanation": "does the plan use excessive buzzwords without evidence of knowledge",
    },
    {
        "index": 4,
        "id": "underestimating risks",
        "explanation": "does this plan grossly underestimate risks",
    },
    {
        "index": 5,
        "id": "budget too low",
        "explanation": "does this plan assume a budget that is too low to achieve the goals",
    },
    {
        "index": 6,
        "id": "overconfident",
        "explanation": "does this plan grossly overestimate the likelihood of success",
    },
    {
        "index": 7,
        "id": "technical vague",
        "explanation": "does the plan lack the important technical steps",
    },
    {
        "index": 8,
        "id": "lack evidence",
        "explanation": "does the plan do a poor job of providing evidence for the claims",
    },
    {
        "index": 9,
        "id": "deliverables unclear",
        "explanation": "are the deliverables unclear or missing",
    },
    {
        "index": 10,
        "id": "ready for execution",
        "explanation": "is the plan ready for beginning execution",
    }
]

def format_system_prompt(checklist: list[dict], batch_size: int = 5) -> str:
    json_checklist = json.dumps(checklist, indent=2)
    number_of_batches = len(checklist) // batch_size
    remainder = len(checklist) % batch_size
    if remainder > 0:
        number_of_batches += 1

    system_prompt = f"""
You are an expert strategic analyst.

Go through the checklist, you are going to do {number_of_batches} batches, taking {batch_size} items at a time.
You must preserve the index from the checklist in the output.

checklist:
{json_checklist}


"""
    return system_prompt

BATCH_SIZE = 5
SYSTEM_PROMPT = format_system_prompt(CHECKLIST, BATCH_SIZE)

@dataclass
class Measure:
    system_prompt: Optional[str]
    user_prompt: str
    responses: list[DocumentDetails]
    measurements: list[ChecklistAnswerCleaned]
    metadata: dict

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str) -> 'Measure':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        system_prompt = SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt,
            )
        ]

        user_prompt_list = [
            user_prompt,
            f"next batch, checklist indexes from {BATCH_SIZE + 1} to {BATCH_SIZE * 2} (inclusive)",
            # "next batch",
        ]

        responses: list[DocumentDetails] = []
        metadata_list: list[dict] = []
        for user_prompt_index, user_prompt_item in enumerate(user_prompt_list, start=1):
            logger.info(f"Processing user_prompt_index: {user_prompt_index} of {len(user_prompt_list)}")
            chat_message_list.append(
                ChatMessage(
                    role=MessageRole.USER,
                    content=user_prompt_item,
                )
            )

            def execute_function(llm: LLM) -> dict:
                sllm = llm.as_structured_llm(DocumentDetails)
                chat_response = sllm.chat(chat_message_list)
                metadata = dict(llm.metadata)
                metadata["llm_classname"] = llm.class_name()
                return {
                    "chat_response": chat_response,
                    "metadata": metadata
                }

            try:
                result = llm_executor.run(execute_function)
            except PipelineStopRequested:
                # Re-raise PipelineStopRequested without wrapping it
                raise
            except Exception as e:
                logger.debug(f"LLM chat interaction failed: {e}")
                logger.error("LLM chat interaction failed.", exc_info=True)
                raise ValueError("LLM chat interaction failed.") from e
            
            chat_message_list.append(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=result["chat_response"].raw.model_dump(),
                )
            )

            responses.append(result["chat_response"].raw)
            metadata_list.append(result["metadata"])

        # from the raw_responses, extract the measurements into a flatten list
        checklist_answers_raw: list[ChecklistAnswer] = []
        for response in responses:
            checklist_answers_raw.extend(response.checklist_answers)

        # convert CHECKLIST from list to dict, using the index as the key
        checklist_dict = {item["index"]: item for item in CHECKLIST}
        if len(checklist_dict) != len(CHECKLIST):
            raise ValueError("Checklist dict length does not match checklist list length.")

        # Clean the raw measurements
        measurements_cleaned: list[ChecklistAnswerCleaned] = []
        for i, measurement in enumerate(checklist_answers_raw, start=1):
            checklist_index = measurement.checklist_index
            checklist_item = checklist_dict.get(checklist_index)
            if checklist_item is None:
                raise ValueError(f"Checklist item not found for index: {checklist_index}")
            checklist_item_id = checklist_item["id"]
            checklist_item_explanation = checklist_item["explanation"]
            measurement_cleaned = ChecklistAnswerCleaned(
                checklist_index=measurement.checklist_index,
                checklist_item_id=checklist_item_id,
                checklist_item_explanation=checklist_item_explanation,
                value=measurement.value,
            )
            measurements_cleaned.append(measurement_cleaned)

        metadata = {}
        for metadata_index, metadata_item in enumerate(metadata_list, start=1):
            metadata[f"metadata_{metadata_index}"] = metadata_item

        result = Measure(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            responses=responses,
            measurements=measurements_cleaned,
            metadata=metadata,
        )
        return result    

    def to_dict(self, include_responses=True, include_cleaned_measurments=True, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = {}
        if include_responses:
            d["responses"] = [response.model_dump() for response in self.responses]
        if include_cleaned_measurments:
            d['measurements'] = [measurement.model_dump() for measurement in self.measurements]
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        Path(file_path).write_text(json.dumps(self.to_dict(), indent=2))

    def measurement_item_list(self) -> list[dict]:
        """
        Return a list of dictionaries, each representing a measurement.
        """
        return [measurement.model_dump() for measurement in self.measurements]
    
    def save_clean(self, file_path: str) -> None:
        measurements_dict = self.measurement_item_list()
        Path(file_path).write_text(json.dumps(measurements_dict, indent=2))
    
if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    from planexe.prompt.prompt_catalog import PromptCatalog

    # logging.basicConfig(level=logging.DEBUG)

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_simple_plan_prompts()

    # prompt_id = "b9afce6c-f98d-4e9d-8525-267a9d153b51"
    # prompt_id = "a6bef08b-c768-4616-bc28-7503244eff02"
    # prompt_id = "19dc0718-3df7-48e3-b06d-e2c664ecc07d"
    prompt_id = "e42eafce-5c8c-4801-b9f1-b8b2a402cd78"
    prompt_item = prompt_catalog.find(prompt_id)
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    model_names = [
        # "ollama-llama3.1",
        "openrouter-paid-gemini-2.0-flash-001",
        # "openrouter-paid-qwen3-30b-a3b"
    ]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    print(f"Query: {query}")
    result = Measure.execute(llm_executor, query)

    print("\nResult:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    test_data_filename = f"measure_{prompt_id}.json"
    result.save_clean(Path(test_data_filename))
    print(f"Test data saved to: {test_data_filename!r}")
