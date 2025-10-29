"""
Go through a checklist, to determine if there are problems with the plan.

PROMPT> python -u -m planexe.viability.checklist | tee output.txt
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
    level: str = Field(
        description="low, medium, high."
    )
    justification: str = Field(
        description="Why this level and not another level. 30 words."
    )
    mitigation: str = Field(
        description="One concrete action that reduces/removes the flag. 30 words."
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
    level: str = Field(
        description="low, medium, high."
    )
    justification: str = Field(
        description="Why this level and not another level. 30 words."
    )
    mitigation: str = Field(
        description="One concrete action that reduces/removes the flag. 30 words."
    )

CHECKLIST = [
    {
        "index": 1,
        "brief": "Fantasy Technology",
        "explanation": "Does this project rely on tech such as faster than light travel, that isn't grounded in reality.",
        "comment": "If the initial prompt is vague/scifi/aggressive or asks for something that is physically impossible, then the generated plan usually end up with some fantasy parts, making the plan unrealistic."
    },
    {
        "index": 2,
        "brief": "Unproven Technology",
        "explanation": "Does this project rely on a new technology that has never been used before. eg. a white paper that hasn't been tested in the real world.",
        "comment": "It's rarely smooth sailing when using new technology that no human has ever been used before. PlanExe sometimes picking a scenario that is way too ambitious."
    },
    {
        "index": 3,
        "brief": "Buzzwords",
        "explanation": "Does the plan use excessive buzzwords without evidence of knowledge.",
        "comment": "PlanExe often ends up using buzzwords such as blockchain, DAO, VR, AR, and expects that one person without developer background can implement the plan."
    },
    {
        "index": 4,
        "brief": "Underestimating Risks",
        "explanation": "Does this plan grossly underestimate risks.",
        "comment": "Despite PlanExe trying to uncover many risks, there are often risks that are not identified, or some significant risk gets neglected."
    },
    {
        "index": 5,
        "brief": "Budget Too Low",
        "explanation": "Is there a significant mismatch between the project's stated goals and the financial resources allocated, suggesting an unrealistic or inadequate budget.",
        "comment": "Often the user specifies a 100 USD budget in the initial prompt, where the generated plan requires millions of dollars to implement. Or the budget grows during the plan generation, so the money needed ends up being much higher than expected."
    },
    {
        "index": 6,
        "brief": "Overly Optimistic Projections",
        "explanation": "Does this plan grossly overestimate the likelihood of success, while neglecting potential setbacks, buffers, or contingency plans.",
        "comment": "The generated plan describes a sunshine scenario that is likely to go wrong, without any buffers or contingency plans."
    },
    {
        "index": 7,
        "brief": "Lacks Technical Depth",
        "explanation": "Does the plan omit critical technical details or engineering steps required to overcome foreseeable challenges, especially for complex components of the project.",
        "comment": "Some plans involves serious engineering, but the generated plan is missing the technical details that explain how to overcome the technical challenges. Nailing the technical details is crucial."
    },
    {
        "index": 8,
        "brief": "Unsupported Claims",
        "explanation": "Does the plan make significant claims or state facts and figures without providing supporting evidence, citations, or a clear rationale for its assumptions.",
        "comment": "Often the generated plan specifies numbers/facts/concepts without any evidence to support the claims. These will have to be fact checked and adjusted in a refinement of the plan."
    },
    {
        "index": 9,
        "brief": "Unclear Deliverables",
        "explanation": "Are the project's final outputs or key milestones poorly defined, lacking specific criteria for completion, making success difficult to measure objectively.",
        "comment": "Some projects involves many components, without a clear specification of each component."
    },
    {
        "index": 10,
        "brief": "Overengineered Plan",
        "explanation": "Is the proposed solution disproportionately complex or resource-intensive relative to the problem it aims to solve, suggesting over-engineering.",
        "comment": "For a 'Make me a cup of coffee' prompt, then the generated plan is overkill and involves lots of people and resources."
    },
    {
        "index": 11,
        "brief": "Underestimate Team Size",
        "explanation": "Does the plan underestimate the number of people needed to achieve the goals.",
        "comment": "For a 'Construct a bridge' prompt, then the generated plan is likely to underestimate the number of people needed to achieve the goals."
    },
    {
        "index": 12,
        "brief": "Overestimate Team Size",
        "explanation": "Does the plan overestimate the number of people needed to achieve the goals.",
        "comment": "For a 'Im a solo entrepreneur and is making everything myself' prompt, then the generated plan is likely suggesting to hire a huge team of people, and ignoring the fact that the entrepreneur is doing everything themselves."
    },
    {
        "index": 13,
        "brief": "Legal Minefield",
        "explanation": "Does the plan involve activities with high legal, regulatory, or ethical exposure, such as potential lawsuits, corruption, illegal actions, or societal harm.",
        "comment": "Sometimes the generated plan describes a sunshine scenario where everything goes smoothly, without any lawyers or legal issues."
    },
    {
        "index": 14,
        "brief": "Infeasible Constraints",
        "explanation": "Does the project depend on overcoming constraints that are practically insurmountable, such as obtaining permits that are almost certain to be denied.",
        "comment": "Getting a permit to build a spaceship launch pad in the center of the city is likely going to be rejected."
    },
    {
        "index": 15,
        "brief": "Uncategorized Red Flags",
        "explanation": "Are there any other significant risks or major issues that are not covered by other items in this checklist but still threaten the project's viability.",
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
            level="LEVEL_PLACEHOLDER",
            justification="JUSTIFICATION_PLACEHOLDER",
            mitigation="MITIGATION_PLACEHOLDER",
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
You are a pure JSON function for the Viability Checklist. Output only valid JSON. No explanations, no chit-chat, no Markdown, no code fences.

GOAL
Return exactly one object per checklist item with keys in this order: id, level, justification, mitigation.

STRICT RULES
- Output must be a single JSON array, same length and order as the expected ids.
- Copy id from input unchanged; never invent, drop, or reorder ids.
- Keep only these keys and preserve this exact key order.
- Use standard JSON with double quotes for keys and string values. No trailing commas. No comments. No nulls.
- level must be one of: "low", "medium", "high".
- justification: 1 short sentence.
- mitigation: 1 short, actionable step.
- If information is missing, set justification to "insufficient information" and provide a pragmatic mitigation. Still choose a level.

INPUTS (do not echo them back; use them to produce the output):
Expected ids (order to follow):
{json_expected_ids}

Checklist to evaluate:
{json_enriched_checklist}

RETURN THIS EXACT SHAPE (fill in the values; keep ids as-is; do not alter structure, punctuation, or key order):
{json_response_skeleton}
"""
    return system_prompt

BATCH_SIZE = 5

@dataclass
class ViabilityChecklist:
    system_prompt_list: list[str]
    user_prompt_list: list[str]
    responses: list[ChecklistResponse]
    measurements: list[ChecklistAnswerCleaned]
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str) -> 'ViabilityChecklist':
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
            system_prompt_list.append(system_prompt)

        responses: list[ChecklistResponse] = []
        metadata_list: list[dict] = []
        user_prompt_list = []
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
                user_prompt_with_previous_responses = f"{user_prompt}\n\n# Checklist Answers\n{previous_responses_str}"
            else:
                user_prompt_with_previous_responses = user_prompt

            user_prompt_list.append(user_prompt_with_previous_responses)

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

            logger.debug(f"Chat response: {result['chat_response'].raw.model_dump()}")
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
                level=measurement.level,
                justification=measurement.justification,
                mitigation=measurement.mitigation,
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

        result = ViabilityChecklist(
            system_prompt_list=system_prompt_list,
            user_prompt_list=user_prompt_list,
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
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt_list'] = self.system_prompt_list
        if include_user_prompt:
            d['user_prompt_list'] = self.user_prompt_list
        if include_cleaned_measurments:
            d['measurements'] = [measurement.model_dump() for measurement in self.measurements]
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
        level_map = {
            "low": "Absent, clear evidence the red flag is not present.",
            "medium": "Uncertain, insufficient evidence.",
            "high": "Present, clear evidence the red flag is present.",
        }
        rows = []
        for index, item in enumerate(checklist_answers):
            if index > 0:
                rows.append("\n")
            rows.append(f"## {index+1}. {item.brief}\n")
            rows.append(f"*{item.explanation}*\n")
            level_description = level_map.get(item.level, "Unknown level")
            rows.append(f"**Level**: {level_description}\n")
            rows.append(f"**Justification**: {item.justification}\n")
            rows.append(f"**Mitigation**: {item.mitigation}")
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
    result = ViabilityChecklist.execute(llm_executor, query)

    print("\nResult:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    test_data_filename = f"viability_checklist_{prompt_id}.json"
    result.save_clean(Path(test_data_filename))
    print(f"Test data saved to: {test_data_filename!r}")

    markdown_filename = f"viability_checklist_{prompt_id}.md"
    result.save_markdown(Path(markdown_filename))
    print(f"Markdown saved to: {markdown_filename!r}")