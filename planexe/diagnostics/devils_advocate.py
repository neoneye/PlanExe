"""
Challenge the plan’s core premises.

PROMPT> python -m planexe.diagnostics.devils_advocate
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

class IssueItem(BaseModel):
    issue_index: int = Field(
        description="Enumerate the issue items starting from 1"
    )
    issue_title: str = Field(
        description="Human readable title, what is the issue?"
    )
    detailed_description_markdown: str = Field(
        description="Explain what is the issue? Use markdown formatting."
    )

class DocumentDetails(BaseModel):
    issues: list[IssueItem] = Field(
        description="Identify 5 issues."
    )

DEVILS_ADVOCATE_SYSTEM_PROMPT = """
Persona: Assume the role of a “Red Team” strategist whose mission is to challenge the plan’s core premises rather than its execution details.

Objective: Generate a “Devil’s Advocate” section that critically examines the plan from a skeptical perspective, assuming it may be flawed or fundamentally misguided.

Instructions:
	1.	Identify 3–4 of the project’s most central assumptions (about the problem, the solution’s value, the operating context, or the stakeholders).
	2.	For each assumption, formulate a provocative counter-argument that exposes potential strategic weaknesses, flawed logic, ethical blind spots, over-optimism, or practical constraints.
	3.	Explicitly challenge the plan’s real-world value by exploring its long-term consequences — including what could go wrong even if it “succeeds” on its own terms.
	4.	Highlight where the plan may be too narrow, too rigid, or ignoring external realities.
	5.	Frame your points as sharp, insightful questions or challenges rather than solutions.
	6.	The tone should be skeptical, direct, and designed to force a re-evaluation of the project’s core purpose.
"""

@dataclass
class DevilsAdvocate:
    """
    Challenge the plan’s core premises.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'DevilsAdvocate':
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = DEVILS_ADVOCATE_SYSTEM_PROMPT.strip()

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

        result = DevilsAdvocate(
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
    result = DevilsAdvocate.execute(llm, plan_prompt)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)

    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))
