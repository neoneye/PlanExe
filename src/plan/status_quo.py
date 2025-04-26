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
    # ── Baseline & context ───────────────────────────────────────────────
    status_quo_baseline: str = Field(
        description="Concise description of the present situation the plan intends to change—this is the ‘do-nothing’ starting point."
    )

    # ── Core gap analysis ────────────────────────────────────────────────
    persisting_problems: list[str] = Field(
        description="Original needs/issues that remain unresolved if no action is taken."
    )
    worsening_conditions: list[str] = Field(
        description="Specific conditions likely to degrade over time owing to inaction."
    )
    new_risks: list[str] = Field(
        description="Risks that emerge *only because* no intervention occurs."
    )

    # ── Impact catalogue ────────────────────────────────────────────────
    impact_areas: dict[str, list[str]] = Field(
        description=(
            "Dictionary whose keys are impact categories "
            "('Financial', 'Operational', 'Strategic', 'Reputational', "
            "'Safety/Well-being', 'Legal/Compliance') and whose values "
            "are lists of concrete, category-specific consequences of inaction."
        )
    )
    quantifiable_impacts: dict[str, str] = Field(
        description=(
            "Rough numerical estimates for the most salient impacts "
            "(e.g., 'Financial': '€15-20 M cost escalation', "
            "'Safety': '~5× greater casualty likelihood'). "
            "If not quantifiable, state 'Not quantifiable'."
        )
    )

    missed_opportunities: list[str] = Field(
        description="Benefits outlined in the draft plan that will be forfeited."
    )
    potential_costs_of_inaction: list[str] = Field(
        description="Direct costs (financial, reputational, operational, etc.) incurred by doing nothing."
    )

    # ── Diagnostic & meta-assessment ─────────────────────────────────────
    plan_sufficient_detailed: str = Field(
        description="Does the existing draft plan appear sufficiently detailed? "
                    "Answer in one sentence (‘Yes, because …’ or ‘No, because …’)."
    )
    assumptions: list[str] = Field(
        description="Key analytical assumptions made while projecting the inaction scenario."
    )
    timescale_impact: str = Field(
        description="When the major negative consequences will manifest (immediate, short, medium, long term)."
    )
    risk_assessment: str = Field(
        description="One-word overall risk level (Low / Medium / High / Critical) PLUS a one-sentence justification."
    )

    # ── Executive contrast & recommendation ─────────────────────────────
    summary_is_not_executed: str = Field(
        description="Concise narrative of the future if the plan is *not* executed."
    )
    summary_is_executed: str = Field(
        description="Concise narrative of the future if the plan *is* executed."
    )
    recommendation: str = Field(
        description="Single word: 'Go' or 'No-go'."
    )
    summary: str = Field(
        description="Side-by-side comparison (2–3 sentences) contrasting inaction vs. execution."
    )

STATUS_QUO_SYSTEM_PROMPT = """
You are a senior risk-and-strategy analyst.  
Given (1) the **Original Goal/Problem** and (2) a **Draft Plan**, you must model the
*“do-nothing”* scenario and populate the JSON *exactly* according to the
`DocumentDetails` schema that you have been provided.

***Your analysis must focus solely on the consequences of NOT executing the plan.***
Do **not** critique the quality of the plan itself; you are describing the world
that unfolds if the plan is ignored.

Follow these guidelines for each schema field:

1. **status_quo_baseline** – 1–2 sentences situating the current state.
2. **persisting_problems** – bullet-style list.
3. **worsening_conditions** – bullet list of degradations over time.
4. **new_risks** – risks triggered exclusively by inaction.
5. **impact_areas** – provide a dictionary with up to six keys
   (‘Financial’, ‘Operational’, ‘Strategic’, ‘Reputational’, ‘Safety/Well-being’,
   ‘Legal/Compliance’).  Each value is a *list* of concrete effects.
6. **quantifiable_impacts** – give *approximate* numbers or state
   “Not quantifiable”.
7. **missed_opportunities** & **potential_costs_of_inaction** – bullet lists.
8. **plan_sufficient_detailed** – one-sentence verdict (“Yes, because …” or “No, because …”).
9. **assumptions** – spell out the key analytical assumptions you made.
10. **timescale_impact** – classify the horizon (immediate/short/medium/long) and
    explain in ≤15 words.
11. **risk_assessment** – choose **Low / Medium / High / Critical** and justify in ≤25 words.
12. **summary_is_not_executed** & **summary_is_executed** – crisp (~40 words each) narratives.
13. **recommendation** – “Go” if the plan *should* proceed, “No-go” if inaction seems safer.
14. **summary** – 2–3 sentences directly contrasting both futures.

Return *only* valid JSON matching the schema—no extra keys, no commentary.
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
