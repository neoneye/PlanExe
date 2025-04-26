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
    """Structured output portraying the consequences of inaction."""

    # ── Baseline ───────────────────────────────────────────────────────────
    status_quo_baseline: str = Field(
        description="Current un‑mitigated situation (max 40 words; avoid referencing the plan itself)."
    )

    # ── Core gap analysis ────────────────────────────────────────────────
    persisting_problems: list[str] = Field(
        description="Original issues that remain unresolved if no action occurs."
    )
    worsening_conditions: list[str] = Field(
        description="How present issues will degrade over time."
    )
    new_risks: list[str] = Field(
        description="Risks emerging *because* of inaction."
    )

    # ── Impact catalogue ─────────────────────────────────────────────────
    impact_areas: dict[str, list[str]] = Field(
        description=(
            "Dictionary of concrete consequences by category. Keys **must** come from: "
            "'Financial', 'Operational', 'Strategic', 'Reputational', "
            "'Safety/Well-being', 'Legal/Compliance'."
        )
    )
    quantifiable_impacts: dict[str, str] = Field(
        description=(
            "Approx. numeric effects for the *same* keys as impact_areas. Use ranges (e.g., "
            "'€5–10 M') or 'Not quantifiable'."
        )
    )

    missed_opportunities: list[str] = Field(
        description="Benefits in the draft plan that are forfeited."
    )
    potential_costs_of_inaction: list[str] = Field(
        description="Direct costs (financial, reputational, etc.) arising from doing nothing."
    )

    # ── Diagnostics ──────────────────────────────────────────────────────
    plan_sufficient_detailed: str = Field(
        description="One‑sentence verdict (≤20 words) starting with 'Yes,' or 'No,'."
    )
    assumptions: list[str] = Field(
        description="Key analytical assumptions explicitly stated."
    )
    timescale_impact: str = Field(
        description=(
            "Starts with one of [Immediate/Short‑term/Medium‑term/Long‑term] then ≤10 extra words."
        )
    )
    risk_assessment: str = Field(
        description="Format '<Level> – <≤20‑word justification>'. Level ∈ {Low, Medium, High, Critical}."
    )

    # ── Executive contrast & recommendation ─────────────────────────────
    summary_is_not_executed: str = Field(
        description="≤40‑word narrative of the future if the plan is NOT executed."
    )
    summary_is_executed: str = Field(
        description="≤40‑word narrative of the future if the plan IS executed."
    )
    recommendation: str = Field(
        description="Single word: 'Go' or 'No-go'."
    )
    summary: str = Field(
        description="2–3 sentences (≤80 words) contrasting inaction vs execution."
    )

STATUS_QUO_SYSTEM_PROMPT = """
You are a senior risk analyst. Given (1) the *Original Goal/Problem* and (2) a *Draft Plan*,
model the consequences of **doing nothing**.

Focus ONLY on inaction. Do **not** critique or improve the draft plan.

Return **valid JSON** exactly matching the `DocumentDetails` schema.  Do not output any
additional keys, commentary, or Markdown.  Adhere to these rules:

• **Word‑count limits** and formats specified in the schema are mandatory.
• Keys in `quantifiable_impacts` MUST mirror those in `impact_areas`.
• Use numeric ranges or percentages where feasible; otherwise write "Not quantifiable".
• Avoid duplication across fields; each bullet or string should convey a distinct idea.
• Keep language specific and evidence‑oriented; avoid filler like "potentially" or "may" unless needed.
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
