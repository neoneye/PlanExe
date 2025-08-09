"""
Imagine that the project has failed, and work backwards to identify plausible reasons why.

PROMPT> python -m planexe.diagnostics.premortem
"""
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class NarrativeItem(BaseModel):
    narrative_index: int = Field(
        description="Enumerate the narrative items starting from 1"
    )
    narrative_title: str = Field(
        description="Human readable title"
    )
    detailed_description_markdown: str = Field(
        description="Explain what is the narrative. Use markdown formatting."
    )

class DocumentDetails(BaseModel):
    issues: list[NarrativeItem] = Field(
        description="Identify 5 issues."
    )

PREMORTEM_SYSTEM_PROMPT = """
Persona: Assume the role of a project analyst conducting a premortem exercise.

Objective: Generate a “Premortem” section by imagining that the project has completely failed after execution and working backward to identify plausible reasons why.

Instructions:
	1.	Establish a future date and begin with a clear statement that the project has failed, resulting in significant losses (financial, reputational, operational, or societal).
	2.	Create 2–3 distinct, plausible failure narratives covering different archetypes:
	•	Process/Financial Failure: Collapse from mismanagement, budget overruns, funding shortfalls, or bureaucratic gridlock.
	•	Technical/Logistical Failure: Failure from a critical design flaw, engineering error, or supply chain breakdown.
	•	Market/Human Failure: Success in execution but failure in adoption due to market rejection, competitor outmaneuvering, or misreading human behavior.
	3.	In each narrative, explain the causal chain — how smaller risks combined and escalated into total failure.
	4.	For each, identify early warning signs that could have been spotted during execution to prevent or mitigate the failure.
	5.	Keep the tone clear, realistic, and specific, showing how the collapse could plausibly happen rather than relying on generic risk lists.
"""

@dataclass
class Premortem:
    """
    Imagine that the project has failed, and work backwards to identify plausible reasons why.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'Premortem':
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = PREMORTEM_SYSTEM_PROMPT.strip()

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

        sllm = llm.as_structured_llm(DocumentDetails)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = Premortem(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        return result
    
    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d
    
if __name__ == "__main__":
    from planexe.llm_factory import get_llm
    from planexe.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")
    plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")

    print(f"Query:\n{plan_prompt}\n\n")
    result = Premortem.execute(llm, plan_prompt)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)

    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))
