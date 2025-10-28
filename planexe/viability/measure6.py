"""
Measure from a checklist of items, if the plan is viable.

PROMPT> python -u -m planexe.viability.measure6 | tee output.txt
"""
import json
import logging
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
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
        description="Parameter value -2 to 2. Where -2 is the strong no, -1 is the weak no, 0 is neutral, 1 is the weak yes, 2 is the strong yes."
    )
    reasoning: str = Field(
        description="Why this value and not another value. 30 words."
    )
    improve: str = Field(
        description="Propose changes to the plan that would improve the value. 30 words."
    )

class ChecklistResponse(BaseModel):
    checklist_answers: list[ChecklistAnswer] = Field(
        description="Answers to the checklist items."
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
        description="Parameter value -2 to 2. Where -2 is the strong no, -1 is the weak no, 0 is neutral, 1 is the weak yes, 2 is the strong yes."
    )
    reasoning: str = Field(
        description="Why this value and not another value. 30 words."
    )
    improve: str = Field(
        description="Propose changes to the plan that would improve the value. 30 words."
    )

CHECKLIST = [
    {
        "index": 1,
        "brief": "Fantasy technology",
        "explanation": "Does this project rely on tech such as faster than light travel, that isn't grounded in reality.",
        "comment": "If the initial prompt is vague/scifi/aggressive or asks for something that is physically impossible, then the generated plan usually end up with some fantasy parts, making the plan unrealistic."
    },
    {
        "index": 2,
        "brief": "Unproven technology",
        "explanation": "Does this project rely on a new technology that has never been used before. eg. a white paper that hasn't been tested in the real world.",
        "comment": "It's rarely smooth sailing when using new technology that no human has ever been used before. PlanExe sometimes picking a scenario that is way too ambitious."
    },
    {
        "index": 3,
        "brief": "Use of buzzwords",
        "explanation": "Does the plan use excessive buzzwords without evidence of knowledge.",
        "comment": "PlanExe often ends up using buzzwords such as blockchain, DAO, VR, AR, and expects that one person without developer background can implement the plan."
    },
    {
        "index": 4,
        "brief": "Underestimating risks",
        "explanation": "Does this plan grossly underestimate risks.",
        "comment": "Despite PlanExe trying to uncover many risks, there are often risks that are not identified, or some significant risk gets neglected."
    },
    {
        "index": 5,
        "brief": "Budget too low",
        "explanation": "Does this plan assume a budget that is too low to achieve the goals.",
        "comment": "Often the user specifies a 100 USD budget in the initial prompt, where the generated plan requires millions of dollars to implement. Or the budget grows during the plan generation, so the money needed ends up being much higher than expected."
    },
    {
        "index": 6,
        "brief": "Overconfident",
        "explanation": "Does this plan grossly overestimate the likelihood of success.",
        "comment": "The generated plan describes a sunshine scenario that is likely to go wrong, without any buffers or contingency plans."
    },
    {
        "index": 7,
        "brief": "Technical vague",
        "explanation": "Does the plan lack the important technical steps.",
        "comment": "Some plans involves serious engineering, but the generated plan is missing the technical details that explain how to overcome the technical challenges. Nailing the technical details is crucial."
    },
    {
        "index": 8,
        "brief": "Lack evidence",
        "explanation": "Does the plan do a poor job of providing evidence for the claims.",
        "comment": "Often the generated plan specifies numbers/facts/concepts without any evidence to support the claims. These will have to be fact checked and adjusted in a refinement of the plan."
    },
    {
        "index": 9,
        "brief": "Deliverables unclear",
        "explanation": "Are the deliverables unclear or missing.",
        "comment": "Some projects involves many components, without a clear specification of each component."
    },
    {
        "index": 10,
        "brief": "Overengineered plan",
        "explanation": "Is the plan overkill for the problem at hand.",
        "comment": "For a 'Make me a cup of coffee' prompt, then the generated plan is overkill and involves lots of people and resources."
    },
    {
        "index": 11,
        "brief": "Underestimate team size",
        "explanation": "Does the plan underestimate the number of people needed to achieve the goals.",
        "comment": "For a 'Construct a bridge' prompt, then the generated plan is likely to underestimate the number of people needed to achieve the goals."
    },
    {
        "index": 12,
        "brief": "Overestimate team size",
        "explanation": "Does the plan overestimate the number of people needed to achieve the goals.",
        "comment": "For a 'Im a solo entrepreneur and is making everything myself' prompt, then the generated plan is likely suggesting to hire a huge team of people, and ignoring the fact that the entrepreneur is doing everything themselves."
    },
    {
        "index": 13,
        "brief": "Legal minefield",
        "explanation": "Does the plan require lawyers, or have a high chance of getting sued, corruption, harmful, doing things that are illegal, etc.",
        "comment": "Sometimes the generated plan describes a sunshine scenario where everything goes smoothly, without any lawyers or legal issues."
    },
    {
        "index": 14,
        "brief": "Impossible to achieve",
        "explanation": "Are there constraints that make it impossible to achieve the goals.",
        "comment": "Getting a permit to build a spaceship launch pad in the center of the city is likely going to be rejected."
    },
    {
        "index": 15,
        "brief": "Other red flags",
        "explanation": "Are there other red flags not accounted for in this checklist.",
        "comment": "This checklist is not exhaustive. Besides what is listed in this checklist, there are other red flags that are not accounted for in this checklist."
    }
]

def enrich_checklist_with_batch_id_and_item_index(checklist: list[dict], batch_size: int = 5) -> list[dict]:
    enriched_checklist: list[dict] = []
    for i, item in enumerate(checklist):
        batch_id = i // batch_size
        item_index = i % batch_size
        id = f"batch={batch_id}&item={item_index}"
        item_enriched = {"id": id, "batch_index": batch_id, **item}
        enriched_checklist.append(item_enriched)
    return enriched_checklist

def format_system_prompt(*, checklist: list[dict], batch_size: int = 5, current_batch_index: int = 0) -> str:
    number_of_batches = len(checklist) // batch_size
    remainder = len(checklist) % batch_size
    if remainder > 0:
        number_of_batches += 1

    enriched_checklist = enrich_checklist_with_batch_id_and_item_index(checklist, batch_size)

    # remove the "comment" key from each item in the enriched_checklist
    enriched_checklist = [{k: v for k, v in item.items() if k != "comment"} for item in enriched_checklist]

    # assign status=TODO to the items that have batch_index == current_batch_index
    for item in enriched_checklist:
        batch_index = item["batch_index"]
        if batch_index < current_batch_index:
            item["status"] = "DONE"
        elif batch_index > current_batch_index:
            item["status"] = "PENDING"
        else:
            item["status"] = "TODO"

    checklist_answers: list[ChecklistAnswer] = []
    for item in enriched_checklist:
        if item["batch_index"] != current_batch_index:
            continue
        checklist_answer = ChecklistAnswer(
            id=item["id"],
            value=0,
            reasoning="",
            improve="",
        )
        checklist_answers.append(checklist_answer)
    checklist_response = ChecklistResponse(
        checklist_answers=checklist_answers,
    )
    json_response_skeleton: str = json.dumps(checklist_response.model_dump(), indent=2)
    # print(f"json_response_skeleton: {json_response_skeleton}")
    # exit(0)

    # remove the "index" key from each item in the enriched_checklist
    enriched_checklist = [{k: v for k, v in item.items() if k != "index"} for item in enriched_checklist]
    # remove the "batch_index" key from each item in the enriched_checklist
    enriched_checklist = [{k: v for k, v in item.items() if k != "batch_index"} for item in enriched_checklist]

    json_enriched_checklist = json.dumps(enriched_checklist, indent=2)
    # print(f"Enriched checklist: {json_enriched_checklist}")
    # exit(0)

    expected_ids = [item["id"] for item in enriched_checklist if item["status"] == "TODO"]
    json_expected_ids = json.dumps(expected_ids, indent=2)

    system_prompt = f"""
You are an expert strategic analyst. Your task is to analyze the provided query against a checklist.

You must answer the checklist items with the following ids (in this EXACT order):
{json_expected_ids}

Your job is to answer the checklist items that have status TODO.
- Only process items with status TODO. Ignore items with status DONE or PENDING.
- For each item, assign a value from -2 to 2 based on how well the query matches the item's explanation:
  -2 = strong no, it's not a problem
  -1 = weak no
   0 = neutral/uncertain
   1 = weak yes
   2 = strong yes, it's a big problem
- For each item, provide a reasoning for the value and not another value.
- For each item, provide a proposal for improvement that would make the problem go away.
- The reasoning and improve should be 30 words.

# Output Rules (STRICT)
- Output MUST be a single valid JSON object. No extra text, no markdown, no explanations.
- The "checklist_answers" array MUST contain EXACTLY {len(expected_ids)} objects, in the EXACT SAME ORDER as listed above.
- Include EVERY id exactly once. Do NOT add or remove ids.
- If uncertain about any item, USE 0 rather than omitting the id.
- Each "value" MUST be one of: -2, -1, 0, 1, 2 (integers only).

# Output Template (fill in ONLY the numbers; DO NOT change ids or order)
{json_response_skeleton}
   
# The Complete Checklist
{json_enriched_checklist}
"""
    return system_prompt

BATCH_SIZE = 5

@dataclass
class Measure:
    system_prompt: Optional[str]
    user_prompt: str
    responses: list[ChecklistResponse]
    measurements: list[ChecklistAnswerCleaned]
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str) -> 'Measure':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        number_of_groups = len(CHECKLIST) // BATCH_SIZE
        remainder = len(CHECKLIST) % BATCH_SIZE
        if remainder > 0:
            number_of_groups += 1

        system_prompt_list = []
        for group_index in range(0, number_of_groups):
            system_prompt = format_system_prompt(checklist=CHECKLIST, batch_size=BATCH_SIZE, current_batch_index=group_index)
            print(f"system prompt[{group_index}]:\n{system_prompt}")
            system_prompt_list.append(system_prompt)


        responses: list[ChecklistResponse] = []
        metadata_list: list[dict] = []
        for group_index in range(0, number_of_groups):
            logger.info(f"Processing group {group_index+1} of {number_of_groups}")
            system_prompt = system_prompt_list[group_index]

            # Add previous checklist responses to the bottom of the user prompt
            if group_index > 0:
                checklist_answers_raw: list[ChecklistAnswer] = []
                for response in responses:
                    checklist_answers_raw.extend(response.checklist_answers)
                previous_responses_dict = [answer.model_dump() for answer in checklist_answers_raw]
                previous_responses_str = json.dumps(previous_responses_dict, indent=2)
                # print(f"Previous responses: {previous_responses_str}")
                # exit(0)
                user_prompt_with_previous_responses = f"{user_prompt}\n\n# Checklist Answers\n{previous_responses_str}"
            else:
                user_prompt_with_previous_responses = user_prompt

            chat_message_list = [
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=system_prompt,
                ),
                ChatMessage(
                    role=MessageRole.USER,
                    content=user_prompt_with_previous_responses,
                )
            ]

            def execute_function(llm: LLM) -> dict:
                sllm = llm.as_structured_llm(ChecklistResponse)
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
                reasoning=measurement.reasoning,
                improve=measurement.improve,
            )
            measurements_cleaned.append(measurement_cleaned)

        # Verify that all the checklist items have been answered
        set_of_checklist_ids = set[Any]([checklist_item["id"] for checklist_item in enriched_checklist])
        set_of_checklist_answers_ids = set[str]([measurement.id for measurement in measurements_cleaned])
        if set_of_checklist_ids != set_of_checklist_answers_ids:
            diff = set_of_checklist_ids - set_of_checklist_answers_ids
            sorted_checklist_ids = sorted(set_of_checklist_ids)
            sorted_checklist_answers_ids = sorted(set_of_checklist_answers_ids)
            sorted_diff = sorted(diff)
            raise ValueError(f"Checklist item not found for ids: {sorted_diff!r} checklist ids: {sorted_checklist_ids!r} checklist answers ids: {sorted_checklist_answers_ids!r}")
        
        metadata = {}
        for metadata_index, metadata_item in enumerate(metadata_list, start=1):
            metadata[f"metadata_{metadata_index}"] = metadata_item

        markdown = cls.convert_to_markdown(measurements_cleaned)

        result = Measure(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            responses=responses,
            measurements=measurements_cleaned,
            metadata=metadata,
            markdown=markdown,
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

    @staticmethod
    def convert_to_markdown(checklist_answers: list[ChecklistAnswerCleaned]) -> str:
        """
        Convert the raw checklist answers to markdown.
        """
        value_map = {
            -2: "Strong no",
            -1: "Weak no",
            0: "Neutral",
            1: "Weak yes",
            2: "Strong yes",
        }
        rows = []
        for index, item in enumerate(checklist_answers):
            if index > 0:
                rows.append("\n")
            rows.append(f"## Checklist Item {index+1} - {item.brief}\n")
            rows.append(f"*{item.explanation}*\n")
            value_description = value_map.get(item.value, "unknown")
            rows.append(f"**Value**: {value_description}\n")
            rows.append(f"**Reasoning**: {item.reasoning}\n")
            rows.append(f"**Improve**: {item.improve}")
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(self.markdown)

if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    from planexe.prompt.prompt_catalog import PromptCatalog

    # logging.basicConfig(level=logging.DEBUG)

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_simple_plan_prompts()

    prompt_id = "b9afce6c-f98d-4e9d-8525-267a9d153b51"
    # prompt_id = "a6bef08b-c768-4616-bc28-7503244eff02"
    # prompt_id = "19dc0718-3df7-48e3-b06d-e2c664ecc07d"
    # prompt_id = "e42eafce-5c8c-4801-b9f1-b8b2a402cd78"
    prompt_item = prompt_catalog.find(prompt_id)
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    model_names = [
        "ollama-llama3.1",
        # "openrouter-paid-gemini-2.0-flash-001",
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

    markdown_filename = f"measure_{prompt_id}.md"
    result.save_markdown(Path(markdown_filename))
    print(f"Markdown saved to: {markdown_filename!r}")