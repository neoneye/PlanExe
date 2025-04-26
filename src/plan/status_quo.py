"""
Status Quo Scenario - The risk of not acting.

Outlining the consequences of doing nothing.

Present a "do-nothing baseline" vs. the draft plan outcomes.

PROMPT> python -m src.plan.status_quo
"""
import os
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class DocumentDetails(BaseModel):
    """Structured output describing the consequences of doing nothing."""

    # ── Baseline & context ───────────────────────────────────────────────
    status_quo_baseline: str = Field(
        description=(
            "Concise, 1–2‑sentence description of the current, unmitigated situation.  "
            "Must *not* repeat details of the draft plan itself."
        )
    )

    # ── Core gap analysis ────────────────────────────────────────────────
    persisting_problems: list[str] = Field(..., description="Unresolved original issues if no action is taken.")
    worsening_conditions: list[str] = Field(..., description="Conditions that will degrade over time without intervention.")
    new_risks: list[str] = Field(..., description="Risks arising *specifically* from inaction.")

    # ── Impact catalogue ────────────────────────────────────────────────
    impact_areas: dict[str, list[str]] = Field(
        ...,
        description=(
            "Dictionary whose keys are the six recognised impact categories —  \n"
            "  Financial, Operational, Strategic, Reputational, Safety/Well-being, Legal/Compliance —  \n"
            "and whose values are lists of concrete consequences of inaction."),
    )
    quantifiable_impacts: dict[str, str] = Field(
        ...,
        description=(
            "Approximate numerics for the same keys used in *impact_areas*.  \n"
            "Keys *must match exactly*; value 'Not quantifiable' is acceptable when numbers cannot be estimated."),
    )

    # ── Lost upside & direct costs ───────────────────────────────────────
    missed_opportunities: list[str] = Field(..., description="Benefits forfeited by doing nothing.")
    potential_costs_of_inaction: list[str] = Field(..., description="Direct costs incurred through inaction.")

    # ── Diagnostic verdicts ──────────────────────────────────────────────
    plan_sufficient_detailed: str = Field(
        ..., description="One‑sentence verdict: ‘Yes, because …’ or ‘No, because …’."
    )
    assumptions: list[str] = Field(..., description="Key analytical assumptions.")
    timescale_impact: str = Field(
        ..., description="<=15 words indicating when major negative effects emerge (immediate / short / medium / long)."
    )
    risk_assessment: str = Field(
        ..., description="Overall risk rating (Low/Medium/High/Critical) + justification in <=25 words."
    )

    # ── Executive contrast & decision ───────────────────────────────────
    summary_is_not_executed: str = Field(..., description="~40‑word narrative of the future if plan is *not* executed.")
    summary_is_executed: str = Field(..., description="~40‑word narrative of the future if plan *is* executed.")
    recommendation: str = Field(..., description="Single word: 'Go' or 'No-go'.")
    summary: str = Field(..., description="2–3 sentence contrast of inaction vs. execution.")

STATUS_QUO_SYSTEM_PROMPT = """
You are a senior risk‑and‑strategy analyst.  
Given (1) the **Original Goal/Problem** and (2) a **Draft Plan**, you must model
and describe the *“do‑nothing”* scenario.  Output **only** JSON that complies
exactly with the `DocumentDetails` schema.

**Scope:** Describe consequences, risks, costs, and lost upside if the plan is
ignored. **Do not** critique the plan’s feasibility; assume it *could* work if
implemented.

Populate each field as follows:

1. **status_quo_baseline** – 1–2 sentences on current unmitigated state.
2. **persisting_problems / worsening_conditions / new_risks** – bullet lists.
3. **impact_areas** – dict with *exactly* these six keys:  
   Financial · Operational · Strategic · Reputational · Safety/Well-being · Legal/Compliance.  
   Each value: 2–4 concrete consequences.
4. **quantifiable_impacts** – same six keys, each with a rough numeric impact
   (ranges or percentage change).  Use "Not quantifiable" when necessary.
5. **missed_opportunities** & **potential_costs_of_inaction** – bullet lists.
6. **plan_sufficient_detailed** – one sentence verdict.
7. **assumptions** – list main assumptions driving the analysis.
8. **timescale_impact** – ≤15 words; specify horizon(s).
9. **risk_assessment** – Low / Medium / High / Critical + ≤25‑word rationale.
10. **summary_is_not_executed** & **summary_is_executed** – crisp ~40‑word
    narratives each.
11. **recommendation** – "Go" if plan should proceed; otherwise "No-go".
12. **summary** – 2–3 sentences directly contrasting both futures.

**Validation rules**
• Keys in `quantifiable_impacts` must *exactly match* those in `impact_areas`.  
• Maintain JSON compliance; no extra keys, no commentary.  
• Respect word‑count limits.
"""

@dataclass
class StatusQuo:
    """
    Take a look at the draft plan and present the status quo scenario.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'StatusQuo':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = STATUS_QUO_SYSTEM_PROMPT.strip()

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

        markdown = cls.convert_to_markdown(chat_response.raw)

        result = StatusQuo(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
            markdown=markdown
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

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

    @staticmethod
    def convert_to_markdown(document_details: DocumentDetails) -> str:
        """
        Convert the raw document details to markdown.
        """
        rows = []
        
        rows.append(f"\n## Summary\n{document_details.summary}")
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")

    plan_prompt = find_plan_prompt("de626417-4871-4acc-899d-2c41fd148807")
    query = (
        f"{plan_prompt}\n\n"
        "Today's date:\n2025-Feb-27\n\n"
        "Project start ASAP"
    )
    print(f"Query: {query}")

    physical_locations = StatusQuo.execute(llm, query)
    json_response = physical_locations.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{physical_locations.markdown}")
