"""
Measure from a checklist of items, if the plan is viable.

PROMPT> python -m planexe.viability.measure1
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

class Measurement(BaseModel):
    measurement_index: int = Field(
        description="Index of this measurement."
    )
    name: str = Field(
        description="Name of this measurement."
    )
    explanation: str = Field(
        description="Explain this measurement. 30 words."
    )
    value: int = Field(
        description="Parameter value -2 to 2. Where -2 is the strong negative, -1 is the weak negative, 0 is neutral, 1 is the weak positive, 2 is the strong positive."
    )
    reasoning: str = Field(
        description="Why this measurement value and not another value. Where in the document is there evidence for this measurement value. 60 words."
    )
    improve: str = Field(
        description="Propose changes to the document that would improve on this measurement. 60 words."
    )

class DocumentDetails(BaseModel):
    strategic_rationale: str = Field(
        description="A concise strategic analysis (around 100 words) of the project's core tensions and trade-offs. This rationale must JUSTIFY why the selected levers are the most critical levers for decision-making. For example, explain how the chosen levers navigate the fundamental conflicts between speed, cost, scope, and quality."
    )
    measurements: list[Measurement] = Field(
        description="Propose exactly 5 measurements."
    )
    summary: str = Field(
        description="Are these measurements well picked? Are they well balanced? Are they well thought out? Point out flaws. 100 words."
    )

class MeasurementCleaned(BaseModel):
    """
    The Measurement class has some ugly field names, that guide the LLM for what to generate. Changing them and the LLM can't generate as good results.
    This class has nicer field names for the final output.
    """
    measurement_id: str = Field(
        description="A uuid that identifies this measurement. The measurements can be deduplicated and preserve their measurement_id without leaving gaps in the numbering."
    )
    name: str = Field(
        description="Name of this measurement."
    )
    explanation: str = Field(
        description="Explain this measurement. 30 words."
    )
    value: int = Field(
        description="Parameter value -2 to 2. Where -2 is the strong negative, -1 is the weak negative, 0 is neutral, 1 is the weak positive, 2 is the strong positive."
    )
    reasoning: str = Field(
        description="Why this measurement value and not another value. Where in the document is there evidence for this measurement value. 60 words."
    )
    improve: str = Field(
        description="Propose changes to the document that would improve on this measurement. 60 words."
    )

SYSTEM_PROMPT = """
You are an expert strategic analyst. Generate solution space parameters following these directives:

Go through the following list of measurements and add more measurements to fill the 5 measurements per response.
You must preserve the measurement_id, name, and explanation from the following list, with your own measurements added to the end of the list.
[
{
    "measurement_id": 1,
    "name": "uses fantasy technology",
    "explanation": "does this project rely on tech such as faster than light travel, that isn't grounded in reality",
},
{
    "measurement_id": 2,
    "name": "unproven technology",
    "explanation": "does this project rely on a new technology that has never been used before. eg. a white paper that hasn't been tested in the real world",
},
{
    "measurement_id": 3,
    "name": "underestimating risks",
    "explanation": "does this plan grossly underestimate risks",
},
{
    "measurement_id": 4,
    "name": "is budget too low",
    "explanation": "does this plan assume a budget that is too low to achieve the goals",
},
{
    "measurement_id": 5,
    "name": "is overconfident",
    "explanation": "does this plan grossly overestimate the likelihood of success",
},
{
    "measurement_id": 6,
    "name": "is technical vague",
    "explanation": "does the plan lack the important technical steps",
},
{
    "measurement_id": 7,
    "name": "is lacking evidence",
    "explanation": "does the plan do a poor job of providing evidence for the claims",
},
{
    "measurement_id": 8,
    "name": "deliverables unclear",
    "explanation": "are the deliverables unclear or missing",
},
{
    "measurement_id": 9,
    "name": "ready for execution",
    "explanation": "is the plan ready for beginning execution",
}
]

1. **Output Requirements**
   - You must generate EXACTLY 5 measurements per response. Do not generate more or fewer than 5 measurements.
   - Format value as an integer between -2 and 2, where -2 is the strong negative, -1 is the weak negative, 0 is neutral, 1 is the weak positive, 2 is the strong positive:
     ```json
     "value": -2
     ```

2. **Strategic Framing**
   - Name measurements as strategic concepts (e.g., "Material Adaptation Strategy")
   - Frame options as complete strategic approaches
   - Ensure measurements challenge core project assumptions

3. **Validation Protocols**
   - For `summary`:
     • Identify ONE critical missing dimension
     • Prescribe CONCRETE addition: "Add '[full strategic option]' to [lever]"

4. **Prohibitions**
   - NO prefixes/labels in options (e.g., "Option A:", "Choice 1:")
   - NO generic option labels (e.g., "Optimize X", "Tolerate Y")
   - NO placeholder consequences
   - NO "[specific innovative option]" placeholders
   - NO value sets without clear strategic progression

5. **Option Structure Enforcement**
   - Radical option must include emerging tech/business model
   - Maintain parallel grammatical structure across options
   - Ensure options are self-contained descriptions
"""

@dataclass
class Measure:
    system_prompt: Optional[str]
    user_prompt: str
    responses: list[DocumentDetails]
    measurements: list[MeasurementCleaned]
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
            "more",
            "more",
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
        measurements_raw: list[Measurement] = []
        for response in responses:
            measurements_raw.extend(response.measurements)

        # Clean the raw measurements
        measurements_cleaned: list[MeasurementCleaned] = []
        for i, measurement in enumerate(measurements_raw, start=1):
            measurement_id = str(uuid.uuid4())
            measurement_cleaned = MeasurementCleaned(
                measurement_id=measurement_id,
                name=measurement.name,
                explanation=measurement.explanation,
                reasoning=measurement.reasoning,
                value=measurement.value,
                improve=measurement.improve,
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

    logging.basicConfig(level=logging.DEBUG)

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
