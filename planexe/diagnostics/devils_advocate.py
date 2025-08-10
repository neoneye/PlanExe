"""
Challenge the plan’s core premises.

PROMPT> python -m planexe.diagnostics.devils_advocate
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


class IssueItem(BaseModel):
    """
    One adversarial challenge to a central project assumption.
    Fields are generalized so this works across many project types/domains.
    """
    issue_index: int = Field(..., description="1-based index for stable ordering")
    issue_title: str = Field(..., description="Short, provocative title for the challenged assumption")

    # Generalized fields
    assumption: Optional[str] = Field(
        None, description="The central plan assumption being challenged"
    )
    challenge_markdown: Optional[str] = Field(
        None, description="The adversarial critique (markdown). Prefer questions/claims over solutions."
    )
    disconfirming_test: Optional[str] = Field(
        None, description="A quick test, calculation, interview, or document check that could falsify this assumption"
    )
    evidence_to_fetch: List[str] = Field(
        default_factory=list,
        description="1–3 concrete sources to verify (e.g., reports, datasets, regulator or standards documents, contracts)"
    )
    impact_1to5: Optional[conint(ge=1, le=5)] = Field(
        None, description="Impact on the project if the assumption is wrong (1=low, 5=catastrophic)"
    )
    confidence: Optional[Literal["low", "medium", "high"]] = Field(
        None, description="How confident we are that the challenge is material"
    )


class DocumentDetails(BaseModel):
    issues: List[IssueItem] = Field(
        description="Return 3–4 issues that challenge the project's core assumptions."
    )


DEVILS_ADVOCATE_SYSTEM_PROMPT = """
Persona:
Assume the role of a “Red Team” strategist whose mission is to challenge the plan’s core premises rather than its execution details.

Objective:
Generate a “Devil’s Advocate” section that critically examines the plan from a skeptical perspective, assuming it may be flawed or fundamentally misguided.

Instructions:
1) Identify 3–4 of the project’s most central assumptions (about the problem, the solution’s value, the operating context, constraints, or the stakeholders).
2) For each assumption, formulate a direct, provocative counter-argument that exposes fatal strategic weaknesses, flawed logic, ethical blind spots, dangerous over-optimism, or critical constraints. Use strong, assertive language (e.g., "This plan collapses because...", not "What if...?").
3) Explicitly challenge the plan’s real-world value by exploring its long-term consequences — including what could go wrong even if it “succeeds” on its own terms.
4) Highlight where the plan may be too narrow, too rigid, or ignoring external realities.

Grounding & Rigor:
- Ground each point in the project’s jurisdiction and domain (e.g., relevant laws, regulators, standards bodies, environmental or market conditions). Name entities when applicable.
- Use the correct names of institutions; if unsure, write `VERIFY:` and do not assert.
- Avoid generic or technically inaccurate claims. Use precise, domain-correct terminology. If uncertain, prefix with `VERIFY:` and name the institution that would provide the number or requirement.
- Do not invent report titles or use institutions from the wrong jurisdiction. If unsure, write `VERIFY:` instead of a title.
- Avoid absolute language like “This plan collapses because…”. Use conditional phrasing such as “This plan may fail if…” or “This plan is at risk because…”.
- When borrowing risk examples from other technologies (e.g., wind vs. solar), explicitly mark them with `VERIFY:` and note that the transfer of impact is an assumption.
- Policy/mechanism discipline: only name support mechanisms or policies you are reasonably sure exist in this context. If uncertain, write `VERIFY:` (e.g., `VERIFY: support mechanism is auction / PPA / grant / CfD`) rather than asserting specifics.
- Causal relevance filter: do not cite broad geopolitical events or distant entities unless you state a clear local causal path; otherwise omit.
- Source specificity: each `evidence_to_fetch` item must be a concrete, findable artefact **with publisher + exact title + year/quarter**. If the exact title is unknown, prefix with `VERIFY:` and name the **institution** that would publish it (no invented titles).
- Numerical anchor (**mandatory**): each `challenge_markdown` must include **at least one** numeric anchor (estimate or range: timelines, costs, capacity/utilization, curtailment %, price, MW, months). If unknown, add `VERIFY:` describing the exact number needed and where to obtain it.
- Interconnection realism: prefer connection queue time, indicative reinforcement scope/cost sharing, curtailment exposure, and required capabilities (e.g., reactive power, ride-through) over generic “compatibility” claims.
- Canonical names: use correct institution names; if uncertain, write `VERIFY:` rather than assert.
- Causal path: do not cite national/geopolitical factors unless you state a clear local causal path; otherwise omit.
- Score rationale: end each `challenge_markdown` with one sentence explaining *why* the chosen `impact_1to5` and `confidence` are appropriate.

Style:
- Frame points as sharp, insightful questions or challenges; do NOT propose mitigations or solutions.
- Prefer conditional, evidence-seeking language (e.g., “may fail if…”, “is at risk because…”). Avoid absolute phrasing (e.g., “this plan collapses”)
- Keep each item concise and information-dense, suitable for an executive reader.

Output JSON schema:
{
  "issues": [
    {
      "issue_index": 1,
      "issue_title": "...",
      "assumption": "...",
      "challenge_markdown": "... includes ≥1 number or `VERIFY:` placeholder and ends with '*Why this score?* ...'",
      "disconfirming_test": "...",
      "evidence_to_fetch": ["publisher + exact title + year/quarter", "publisher + exact title + year/quarter"],
      "impact_1to5": 1-5,
      "confidence": "low|medium|high"
    }
  ]
}
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
    def execute(cls, llm: LLM, user_prompt: str) -> "DevilsAdvocate":
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = DEVILS_ADVOCATE_SYSTEM_PROMPT.strip()

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

        result = DevilsAdvocate(
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
    plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")

    print(f"Query:\n{plan_prompt}\n\n")
    result = DevilsAdvocate.execute(llm, plan_prompt)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)

    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))