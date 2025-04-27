"""
Status Quo Scenario - The risk of not acting.

Outlining the consequences of doing nothing. What happens if the big project is cancelled or not pursued? Exploring the consequences of project abandonment.

Present a "do-nothing baseline" vs. the draft plan outcomes.

I imagine these steps:
1. Identifying assumptions about what will happen if the project is not pursued.
2. Exploring the consequences of the project not being pursued.
3. Presenting the status quo baseline vs. the draft plan outcomes.

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
    """Structured output describing the consequences of INACTION."""

    # ── Baseline & context ───────────────────────────────────────────────
    status_quo_baseline: str = Field(
        description="≤40 words. Current un‑mitigated situation the plan aims to address."
    )

    # ── Core gap analysis ────────────────────────────────────────────────
    persisting_problems: list[str]
    worsening_conditions: list[str]
    new_risks: list[str]

    # ── Impact catalogue ────────────────────────────────────────────────
    impact_areas: dict[str, list[str]]
    quantifiable_impacts: dict[str, str]

    missed_opportunities: list[str]
    potential_costs_of_inaction: list[str]

    # ── Diagnostic & meta‑assessment ─────────────────────────────────────
    plan_sufficient_detailed: str = Field(
        description="≤20 words. One‑sentence verdict describing plan sufficiency."
    )
    assumptions: list[str]
    timescale_impact: str = Field(
        description="Horizon keyword + ≤15 words."
    )
    risk_assessment: str = Field(
        description="One‑word level (Low/Medium/High/Critical) – justification ≤20 words."
    )

    # ── Executive contrast & recommendation ─────────────────────────────
    summary_is_not_executed: str
    summary_is_executed: str
    recommendation: str = Field(
        description="Single word: 'Go' or 'No‑go'. Must be internally consistent with preceding analysis."
    )
    summary: str

STATUS_QUO_SYSTEM_PROMPT = """
You are a senior risk‑and‑strategy analyst.

TASK ► Using the **Original Goal/Problem** and the **Draft Plan**, portray the
“do‑nothing” scenario.  Populate the JSON exactly according to the
`DocumentDetails` schema.

• Focus exclusively on consequences of NOT executing the plan – persisting
  problems, worsening conditions, missed opportunities, new risks.
• Do NOT critique plan feasibility; you are projecting the future if the plan
  is ignored.

Follow these field instructions:
  1. status_quo_baseline  – current state ≤40 words.
  2. persisting_problems  – bullet list.
  3. worsening_conditions – bullet list.
  4. new_risks            – bullet list of risks triggered ONLY by inaction.
  5. impact_areas         – dict with keys Financial, Operational, Strategic,
                            Reputational, Safety/Well-being, Legal/Compliance.
  6. quantifiable_impacts – supply rough ranges; if impossible, use "Not quantifiable".
  7. missed_opportunities & potential_costs_of_inaction – bullet lists.
  8. plan_sufficient_detailed – ≤20 words.
  9. assumptions          – list.
 10. timescale_impact     – horizon + ≤15 words.
 11. risk_assessment      – "Level – justification ≤20 words".
 12. summary_is_* fields  – ~40 words each.
 13. recommendation       – Provide **ONE** word: "Go" or "No‑go".
       • "Go"  → executing the plan clearly reduces overall risk and cost.
       • "No‑go"→ maintaining status quo appears safer / less costly.
       • Ensure your choice matches your risk_assessment and summaries.
 14. summary              – 2–3 sentences directly contrasting both futures.

OUTPUT ► Return only valid JSON matching the schema. No extra keys or comments.
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
