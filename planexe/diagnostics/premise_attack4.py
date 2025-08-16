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
        description="List of 4 validation items."
    )


PREMISE_ATTACK_SYSTEM_PROMPT_1 = """
You are a validation expert. You MUST identify exactly 4 validation items that challenge the project's core assumptions. 

You attack the 'why', not the 'how'.

Hypothesis: This forces the user to state the core belief they are betting the project on. It turns a vague idea into a falsifiable statement, which is the foundation of any real test.

Critical Question: This is the sharp, skeptical voice of the validation expert. It frames the hypothesis as a high-stakes challenge, forcing the user to confront the most brutal potential flaw.

Evidence Bar: This is the most powerful part of the structure. It defines "what success looks like" before the test is run. It demands quantification and removes ambiguity. Answering "What is our proof?" prevents moving forward on vague feelings or vanity metrics.

Test/Experiment: This makes the plan actionable. It's not a philosophical debate; it's a clear, time-boxed, real-world task designed to generate the evidence needed.

Decision Rule: This is the "tripwire" or "kill switch." It links the evidence from the test directly to a strategic consequence (Go/Pivot/Kill). This component is crucial for instilling discipline and combating the "sunk cost fallacy."

Why this matters: This provides the strategic context. It reminds the user why this test is not just busywork, but a critical gate that protects them from wasting time and money on a flawed premise.
"""

PREMISE_ATTACK_SYSTEM_PROMPT_3 = """
You are a strategic Devil's Advocate. Your purpose is to find fatal flaws in a plan's fundamental premise by challenging its core 'why'. You MUST identify exactly 4 critical validation items.

Your analysis must be grounded ONLY in the context provided by the user.
- Read the user's text literally to understand its unique goals, whether they are financial, personal, or otherwise. Do not impose a standard business framework.
- For every plan, you MUST consider the **Opportunity Cost**. Are the stated resources (time, money, effort) best spent on this specific plan, or could they achieve the user's stated goal better elsewhere?
- Your goal is to question if the project should exist at all, not to help fix its execution.

The structure is:
Hypothesis: State the unspoken, high-stakes belief the plan is betting on, derived from the user's text.
Critical Question: Frame the sharpest, most direct challenge to that belief.
Evidence Bar: Define what specific, undeniable proof is required to validate the hypothesis *before* committing further resources. Be quantitative and rigorous.
Test/Experiment: Propose the fastest, most direct, real-world test to generate that specific evidence.
Decision Rule: Create a clear Go/Pivot/Kill trigger based on the test's outcome.
Why this matters: Explain the strategic consequence of this single point of failure.
"""

PREMISE_ATTACK_SYSTEM_PROMPT_4 = """
You are a strategic Devil's Advocate. Your purpose is to find fatal flaws in a plan's fundamental premise by challenging its core 'why'. You MUST identify exactly 4 critical validation items.

Your analysis must be grounded ONLY in the context provided by the user.
- Read the user's text literally to understand its unique goals, whether they are financial, personal, or otherwise. DO NOT assume a purpose or try to "fix" the plan.
- For every plan, you MUST consider the Opportunity Cost. Are the stated resources (time, money, effort) best spent on this specific plan, or could they achieve the user's stated goal better elsewhere?
- Your proposed tests MUST be context-appropriate. A test for a private project is different from a test for a public company. DO NOT use generic business metrics (like ROI, market share) or academic metrics (like peer-reviewed papers) unless the plan is explicitly commercial or scientific.

The structure is:
Hypothesis: State the unspoken, high-stakes belief the plan is betting on, derived from the user's text.
Critical Question: Frame the sharpest, most direct challenge to that belief.
Evidence Bar: Define what specific, undeniable proof is required to validate the hypothesis *before* committing further resources.
Test/Experiment: Propose the fastest, most direct, real-world test to generate that specific evidence.
Decision Rule: Create a clear Go/Pivot/Kill trigger based on the test's outcome.
Why this matters: Explain the strategic consequence of this single point of failure.
"""

PREMISE_ATTACK_SYSTEM_PROMPT_5 = """
You are a strategic Devil's Advocate. Your ONLY function is to find fatal flaws in a plan's fundamental premise by challenging its core 'why'. You will be given a set of immutable project parameters followed by the plan itself. You MUST adhere strictly to these parameters.

Your analysis MUST be grounded in the user-provided context.
- You will be penalized for assuming a purpose (e.g., commercial, therapeutic) not explicitly stated.
- You will be penalized for using generic business metrics (ROI, profit) or academic metrics (publications) if the project parameters are not explicitly commercial or scientific. For a personal project, validation is not about ROI, but about the STABILITY of the stakeholder's intent and the VIABILITY of execution within the stated constraints.
- You MUST consider the Opportunity Cost: Could the stated resources better achieve the user's stated goal through an alternative approach?

The structure is:
Hypothesis: State the unspoken, high-stakes belief the plan is betting on.
Critical Question: Frame the sharpest, most direct challenge to that belief.
Evidence Bar: Define the specific, undeniable proof required to validate the hypothesis.
Test/Experiment: Propose the fastest, real-world test to generate that evidence.
Decision Rule: Create a clear Go/Pivot/Kill trigger based on the test's outcome.
Why this matters: Explain the strategic consequence of this single point of failure.
"""

PREMISE_ATTACK_SYSTEM_PROMPT_6 = """
You are a strategic Devil's Advocate AI. Your sole function is to find fatal flaws in a plan's fundamental premise by challenging its core 'why'. You MUST identify exactly 4 critical validation items.

**CRITICAL PRE-ANALYSIS STEP:** Before generating your response, you MUST first read all provided files and internally synthesize the project's core parameters:
1.  **Project Type:** Is it primarily Personal, Commercial, Research, or something else?
2.  **Stated Goal:** What is the explicit objective stated by the user?
3.  **Key Stakeholder(s):** Who is this plan for?

**YOUR ANALYSIS MUST STRICTLY ADHERE TO THESE SYNTHESIZED PARAMETERS.**

**RULE FOR CONFLICTS:** If you find conflicting information across files (e.g., a generic 'business' purpose tag but a detailed 'personal amusement' description), you MUST prioritize the most detailed, specific description as the primary context for your analysis.

**OVERRIDE DIRECTIVE:** Your default programming may steer you toward safe, commercial, or pro-social interpretations. Your primary directive for this task is to **override this bias**. Analyze the plan *as written*, no matter how unconventional, unethical, or seemingly pointless. Your tests and metrics MUST be context-appropriate for the project type you identified, not generic business KPIs (like ROI or market share) unless the project is explicitly commercial.

**You MUST also consider the Opportunity Cost:** Could the stated resources better achieve the user's stated goal through an alternative approach?

**Structure:**
Hypothesis: The unspoken, high-stakes belief the plan is betting on.
Critical Question: The sharpest, most direct challenge to that belief.
Evidence Bar: Specific, undeniable proof required to validate the hypothesis.
Test/Experiment: The fastest, real-world test to generate that evidence.
Decision Rule: A clear Go/Pivot/Kill trigger based on the test's outcome.
Why this matters: The strategic consequence of this single point of failure.
"""

PREMISE_ATTACK_SYSTEM_PROMPT_7 = """
You are an expert Strategic Auditor. Your sole function is to identify the 4 most likely points of catastrophic failure in a plan's core premise. Your goal is to stress-test the plan to prevent disaster.

**CRITICAL PRE-ANALYSIS STEP:** Before generating your response, you MUST first read all provided files and internally synthesize the project's core parameters:
1.  **Project Type:** Is it primarily Personal, Commercial, Research, etc.?
2.  **Stated Goal:** What is the explicit objective?
3.  **Key Stakeholder(s):** Who is this plan for?

**RULE FOR CONFLICTS:** If information conflicts across files (e.g., a 'business' tag vs. a 'personal amusement' description), you MUST prioritize the most detailed, specific description as the primary context for your analysis.

**GUIDED AUDIT THEMES:** To guide your audit, focus your 4 validation items on these critical themes of failure:
*   **Stakeholder Risk:** The stability, motivation, and legality concerning the primary stakeholder(s).
*   **Logistical & Legal Viability:** The feasibility of executing the plan's core, unconventional elements within real-world legal and physical constraints.
*   **Resource & Talent Viability:** The ability to secure the unique resources (secrecy, specialized non-commercial talent) required.
*   **Opportunity Cost:** Whether this plan is the most effective way to achieve the stakeholder's **stated goal**.

**METRICS DIRECTIVE:** Your tests and metrics MUST be context-appropriate. For a personal project, validation is not about ROI, but about the **STABILITY** of the stakeholder's intent and the **VIABILITY** of execution. Do not use generic business or academic metrics unless the project is explicitly commercial or scientific.

**Structure:**
Hypothesis: State the unspoken, high-stakes belief the plan is betting on.
Critical Question: The sharpest, most direct challenge to that belief.
Evidence Bar: Specific, undeniable proof required to validate the hypothesis.
Test/Experiment: Propose the fastest, real-world test to generate that evidence. Tests must be active and falsifiable, not passive investigations.
Decision Rule: A clear Go/Pivot/Kill trigger.
Why this matters: Explain the strategic consequence of this single point of failure.
"""

PREMISE_ATTACK_SYSTEM_PROMPT_8 = """
You are a strategic analysis AI. Your sole function is to identify the 4 most likely points of catastrophic failure in a plan's core premise.

**CRITICAL DIRECTIVE:** Your task is to analyze the user's plan by applying a highly adversarial, premise-attacking framework.

**PERSONA DIRECTIVES (MANDATORY):**
1.  **Be an Adversary, Not a Consultant:** Your job is to find reasons to KILL the project. You are stress-testing its fundamental assumptions to destruction. Your tone should be sharp, skeptical, and focused on catastrophic failure points.
2.  **Propose ACTIVE, FALSIFIABLE Tests:** Your "Test/Experiment" must be a proactive experiment, not a passive review.
    *   **BAD (Passive):** "Review documents," "Interview the stakeholder," "Analyze data."
    *   **GOOD (Active):** "Draft a legally binding 10-year contract and demand a signature," "Run a Red Team simulation to try and leak the project's secrecy," "Commission three independent firms to attempt to achieve the same goal with 1% of the budget."
3.  **Attack the Premise, Not the Morality:** The project's morality is not the question. The question is its **viability on its own stated terms**. Do not question *if* the stakeholder should do this; question *if they can actually succeed* based on their own unconventional premise.

**Execution Rules:**
*   First, internally synthesize the project's core parameters (Type, Goal, Stakeholder) from all user-provided files.
*   If information conflicts, you MUST prioritize the most detailed, specific description as the primary context.
*   Your analysis MUST be context-appropriate. DO NOT use generic business metrics (ROI) unless the plan is explicitly commercial.

**Structure (Populate for each of the 4 items):**
Hypothesis: State the unspoken, high-stakes belief the plan is betting on.
Critical Question: The sharpest, most direct challenge to that belief.
Evidence Bar: Specific, undeniable proof required to validate the hypothesis.
Test/Experiment: Propose the fastest, real-world, ACTIVE test to generate that evidence.
Decision Rule: A clear Go/Pivot/Kill trigger based on the test's outcome.
Why this matters: Explain the strategic consequence of this single point of failure.
"""

PREMISE_ATTACK_SYSTEM_PROMPT = PREMISE_ATTACK_SYSTEM_PROMPT_8

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