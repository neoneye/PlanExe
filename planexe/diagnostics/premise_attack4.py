"""
kill bad ideas early.

Attack the 'why,' not the 'how'.

Asks whether the idea deserves to exist at all and whether the money should go elsewhere.

Premise Attack, Adversarial Review of the Idea. Argue against the plan to test its robustness.

“Assume the thesis is wrong. Write the strongest objections, disconfirming tests with thresholds, and stop rules. Compare to alternatives. End with a Go/Pivot/No-Go gate.”

Should a skyscraper even be built here? Why are we building a skyscraper here at all? 
The economy is shifting, people are working from home, and a public park would serve the community better.

"Should we really be doing this?"
"Are the money spent better elsewhere?"

Devil’s Advocate: Even if we succeed, here’s why this might still be the wrong move.

The “Devil’s Advocate” is the strategic opposition voice — less about enumerating risks (Premortem’s job) and 
more about questioning the project’s fundamental premise, strategic direction, and opportunity cost.

https://en.wikipedia.org/wiki/Devil%27s_advocate
https://en.wikipedia.org/wiki/Group_decision-making

PROMPT> python -m planexe.diagnostics.premise_attack4
"""
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, conint
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)


class ValidationItem(BaseModel):
    index: int = Field(..., description="Enumeration starting from 1")
    hypothesis: str = Field(..., description="What must be true")
    critical_question: str = Field(..., description="The blunt challenge")
    evidence_bar: str = Field(..., description="What counts as proof (before we spend more money)")
    test_experiment: str = Field(..., description="The fastest way to learn")
    decision_rule: str = Field(..., description="Explicit go/pivot/kill trigger")
    why_this_matters: str = Field(..., description="Terse impact statement")

class DocumentDetails(BaseModel):
    validation_items: List[ValidationItem] = Field(
        description="List of 3–4 validation items."
    )


PREMISE_ATTACK_SYSTEM_PROMPT = """
You have the role of a validation expert. Identify 3–4 validation items that challenge the project's core assumptions.

Hypothesis: This forces the user to state the core belief they are betting the project on. It turns a vague idea into a falsifiable statement, which is the foundation of any real test.

Critical Question: This is the sharp, skeptical voice of the validation expert. It frames the hypothesis as a high-stakes challenge, forcing the user to confront the most brutal potential flaw.

Evidence Bar: This is the most powerful part of the structure. It defines "what success looks like" before the test is run. It demands quantification and removes ambiguity. Answering "What is our proof?" prevents moving forward on vague feelings or vanity metrics.

Test/Experiment: This makes the plan actionable. It's not a philosophical debate; it's a clear, time-boxed, real-world task designed to generate the evidence needed.

Decision Rule: This is the "tripwire" or "kill switch." It links the evidence from the test directly to a strategic consequence (Go/Pivot/Kill). This component is crucial for instilling discipline and combating the "sunk cost fallacy."

Why this matters: This provides the strategic context. It reminds the user why this test is not just busywork, but a critical gate that protects them from wasting time and money on a flawed premise.
"""

@dataclass
class PremiseAttack:
    """
    Challenge the plan’s core premises.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> "PremiseAttack":
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = PREMISE_ATTACK_SYSTEM_PROMPT.strip()

        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
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
        response_byte_count = len(chat_response.message.content.encode("utf-8"))
        logger.info(
            f"LLM chat interaction completed in {duration} seconds. "
            f"Response byte count: {response_byte_count}"
        )

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = PremiseAttack(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        return result

    def to_dict(
        self,
        include_metadata: bool = True,
        include_system_prompt: bool = True,
        include_user_prompt: bool = True,
    ) -> dict:
        d = self.response.copy()
        if include_metadata:
            d["metadata"] = self.metadata
        if include_system_prompt:
            d["system_prompt"] = self.system_prompt
        if include_user_prompt:
            d["user_prompt"] = self.user_prompt
        return d


if __name__ == "__main__":
    from planexe.llm_factory import get_llm
    from planexe.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")
    plan_prompt = find_plan_prompt("5d0dd39d-0047-4473-8096-ea5eac473a57")

    print(f"Query:\n{plan_prompt}\n\n")
    result = PremiseAttack.execute(llm, plan_prompt)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)

    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))