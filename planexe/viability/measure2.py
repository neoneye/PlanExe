"""
Measure from a checklist of items, if the plan is viable.

PROMPT> python -u -m planexe.viability.measure2 | tee output.txt
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
    id: str = Field(
        description="Id of this checklist item."
    )
    value: int = Field(
        description="Parameter value -2 to 2. Where -2 is the strong negative, -1 is the weak negative, 0 is neutral, 1 is the weak positive, 2 is the strong positive."
    )

class BatchResponse(BaseModel):
    batch_index: int = Field(
        description="Which batch of the checklist is this answer for."
    )
    checklist_answers: list[ChecklistAnswer] = Field(
        description="Answers to the checklist."
    )

class ChecklistAnswerCleaned(BaseModel):
    id: str = Field(
        description="Id of this checklist item."
    )
    index: int = Field(
        description="Index of this checklist item."
    )
    brief: str = Field(
        description="Brief description of this checklist item."
    )
    explanation: str = Field(
        description="Explain this measurement. 30 words."
    )
    value: int = Field(
        description="Parameter value -2 to 2. Where -2 is the strong negative, -1 is the weak negative, 0 is neutral, 1 is the weak positive, 2 is the strong positive."
    )

CHECKLIST = [
    {
        "index": 1,
        "brief": "fantasy technology",
        "explanation": "does this project rely on tech such as faster than light travel, that isn't grounded in reality",
    },
    {
        "index": 2,
        "brief": "unproven technology",
        "explanation": "does this project rely on a new technology that has never been used before. eg. a white paper that hasn't been tested in the real world",
    },
    {
        "index": 3,
        "brief": "use of buzzwords",
        "explanation": "does the plan use excessive buzzwords without evidence of knowledge",
    },
    {
        "index": 4,
        "brief": "underestimating risks",
        "explanation": "does this plan grossly underestimate risks",
    },
    {
        "index": 5,
        "brief": "budget too low",
        "explanation": "does this plan assume a budget that is too low to achieve the goals",
    },
    {
        "index": 6,
        "brief": "overconfident",
        "explanation": "does this plan grossly overestimate the likelihood of success",
    },
    {
        "index": 7,
        "brief": "technical vague",
        "explanation": "does the plan lack the important technical steps",
    },
    {
        "index": 8,
        "brief": "lack evidence",
        "explanation": "does the plan do a poor job of providing evidence for the claims",
    },
    {
        "index": 9,
        "brief": "deliverables unclear",
        "explanation": "are the deliverables unclear or missing",
    },
    {
        "index": 10,
        "brief": "ready for execution",
        "explanation": "is the plan ready for beginning execution",
    }
]

def enrich_checklist_with_batch_id_and_item_index(checklist: list[dict], batch_size: int = 5) -> list[dict]:
    enriched_checklist: list[dict] = []
    for i, item in enumerate(checklist):
        batch_id = (i // batch_size) + 1
        item_index = i % batch_size
        id = f"batch={batch_id}&item={item_index}"
        item_enriched = {"id": id, **item}
        enriched_checklist.append(item_enriched)
    return enriched_checklist

def format_system_prompt(checklist: list[dict], batch_size: int = 5) -> str:
    number_of_batches = len(checklist) // batch_size
    remainder = len(checklist) % batch_size
    if remainder > 0:
        number_of_batches += 1

    enriched_checklist = enrich_checklist_with_batch_id_and_item_index(checklist, batch_size)
    # remove the "index" key from each item in the enriched_checklist
    enriched_checklist = [{k: v for k, v in item.items() if k != "index"} for item in enriched_checklist]
    json_enriched_checklist = json.dumps(enriched_checklist, indent=2)
    # print(f"Enriched checklist: {json_enriched_checklist}")

    system_prompt = f"""
You are an expert strategic analyst. Your task is to analyze the provided query against a checklist of items. You will do this in batches.

The checklist is divided into {number_of_batches} batches. Each batch has up to 5 items.
- Each item has a unique "id" like "batch=1&item=0".
- Only process items from the current batch.
- For each item, assign a value from -2 to 2 based on how well the query matches the item's explanation. -2 is strong negative (yes, it's a big problem), -1 is weak negative, 0 is neutral, 1 is weak positive, 2 is strong positive (no, it's not a problem).

checklist:
{json_enriched_checklist}

Process batches one at a time across responses:
- The first user message contains the query to analyze. Automatically process batch 1 for it.
- Later user messages will say something like "process batch 2" or "next batch". Process only that batch.
- Think step-by-step: For the current batch, evaluate each item one by one against the query. Then output the results.
- Your response must be valid JSON for a single BatchResponse object. Do not add extra text, lists, or wrappers.
- "batch_index" is the current batch number (starting at 1).
- "checklist_answers" must include ALL items for the batch (exactly 5 for full batches, fewer for the last). It must NEVER be empty or incomplete.

Example of a valid response (pure JSON, no extra text):
{{
    "batch_index": 1,
    "checklist_answers": [
        {{
            "id": "batch=1&item=0",
            "value": -2
        }},
        {{
            "id": "batch=1&item=1",
            "value": 0
        }},
        {{
            "id": "batch=1&item=2",
            "value": -2
        }},
        {{
            "id": "batch=1&item=3",
            "value": 1
        }},
        {{
            "id": "batch=1&item=4",
            "value": -1
        }}
    ]
}}
"""
    return system_prompt

BATCH_SIZE = 5
SYSTEM_PROMPT = format_system_prompt(CHECKLIST, BATCH_SIZE)

@dataclass
class Measure:
    system_prompt: Optional[str]
    user_prompt: str
    responses: list[BatchResponse]
    measurements: list[ChecklistAnswerCleaned]
    metadata: dict

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str) -> 'Measure':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        system_prompt = SYSTEM_PROMPT.strip()
        print(f"System prompt: {system_prompt}")
        # exit(0)

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
            f"Now process batch 2",
            # "next batch",
        ]

        responses: list[BatchResponse] = []
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
                sllm = llm.as_structured_llm(BatchResponse)
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

            print(f"Chat response: {result['chat_response'].raw.model_dump()}")
            responses.append(result["chat_response"].raw)
            metadata_list.append(result["metadata"])

        # from the raw_responses, extract the measurements into a flatten list
        checklist_answers_raw: list[ChecklistAnswer] = []
        for response in responses:
            checklist_answers_raw.extend(response.checklist_answers)

        # convert CHECKLIST from list to dict, using the index as the key
        enriched_checklist = enrich_checklist_with_batch_id_and_item_index(CHECKLIST, BATCH_SIZE)
        checklist_dict = {item["id"]: item for item in enriched_checklist}
        if len(checklist_dict) != len(CHECKLIST):
            raise ValueError("Checklist dict length does not match checklist list length.")

        # Clean the raw measurements
        measurements_cleaned: list[ChecklistAnswerCleaned] = []
        for measurement in checklist_answers_raw:
            checklist_id = measurement.id
            checklist_item = checklist_dict.get(checklist_id)
            if checklist_item is None:
                raise ValueError(f"Checklist item not found for id: {checklist_id}")
            checklist_item_index = checklist_item["index"]
            checklist_item_brief = checklist_item["brief"]
            checklist_item_explanation = checklist_item["explanation"]
            measurement_cleaned = ChecklistAnswerCleaned(
                id=checklist_id,
                index=checklist_item_index,
                brief=checklist_item_brief,
                explanation=checklist_item_explanation,
                value=measurement.value,
            )
            measurements_cleaned.append(measurement_cleaned)

        # Verify that all the checklist items have been answered
        set_of_checklist_ids = set([checklist_item["id"] for checklist_item in enriched_checklist])
        set_of_checklist_answers_ids = set([measurement.id for measurement in measurements_cleaned])
        if set_of_checklist_ids != set_of_checklist_answers_ids:
            diff = set_of_checklist_ids - set_of_checklist_answers_ids
            sorted_checklist_ids = sorted(set_of_checklist_ids)
            sorted_checklist_answers_ids = sorted(set_of_checklist_answers_ids)
            sorted_diff = sorted(diff)
            raise ValueError(f"Checklist item not found for ids: {sorted_diff!r} checklist ids: {sorted_checklist_ids!r} checklist answers ids: {sorted_checklist_answers_ids!r}")
        
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
