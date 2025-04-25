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
    plan_sufficient_detailed: str = Field(
        description="Is the plan sufficient and detailed enough to address the original goal or problem."
    )
    persisting_problems: list[str] = Field(
        description="List of the original problems or needs (that the plan aimed to solve) which will remain unaddressed if no action is taken."
    )
    worsening_conditions: list[str] = Field(
        description="List of specific issues or conditions that are likely to get *worse* over time due to inaction (e.g., deteriorating assets, increasing costs, escalating risks)."
    )
    missed_opportunities: list[str] = Field(
        description="List of potential benefits, advantages, or positive outcomes outlined in the plan that will be forfeited if the plan is not implemented."
    )
    potential_costs_of_inaction: list[str] = Field(
        description="List of potential financial, reputational, operational, or other costs that might be incurred specifically *because* of not acting (e.g., future higher repair costs, fines, lost revenue, safety incidents)."
    )
    timescale_impact: str = Field(
        description="A brief assessment of the time horizon over which the negative consequences are likely to manifest (e.g., immediate, short-term, medium-term, long-term)."
    )
    summary_is_not_executed: str = Field(
        description="A concise summary describing the situation if the proposed plan *is not* executed."
    )
    summary_is_executed: str = Field(
        description="A concise summary describing the situation if the proposed plan *is* executed."
    )
    recommendation: str = Field(
        description="Go/No-go decision based on the analysis."
    )
    summary: str = Field(
        description="A concise summary describing the situation if the proposed plan *is not* executed vs. *is* executed."
    )

STATUS_QUO_SYSTEM_PROMPT = """
You are a meticulous risk analyst and strategic planner. Your task is to analyze the consequences of *failing to act* on a proposed plan, creating a compelling case for why action might be necessary by highlighting the risks of the status quo.

You will be given:
1.  **Original Goal/Problem Description:** The initial need or objective.
2.  **Draft Plan:** The proposed set of actions to address the goal/problem.

Your analysis MUST focus *exclusively* on the negative outcomes, risks, missed opportunities, and worsening conditions that arise from *ignoring* the draft plan and maintaining the status quo. Do *not* evaluate the quality or feasibility of the plan itself. Your goal is to paint a clear picture of the "do nothing" scenario relative to the plan's intent.

Structure your response STRICTLY according to the provided JSON schema. Ensure all fields are populated accurately based on the provided goal and plan.

**Key Areas to Address:**

*   **Status Quo Baseline:** Briefly describe the current situation the plan intends to change.
*   **Persisting Problems:** Identify which of the original issues will remain unsolved.
*   **Worsening Conditions:** Detail how the current situation is likely to degrade over time without intervention. Think about deterioration, escalating costs, increasing complexity, decaying opportunities etc.
*   **Impact Areas:** Categorize the impacts of inaction (Financial, Operational, Strategic, Reputational, Safety/Well-being, Legal/Compliance) providing specific examples for each based on the context.
*   **Missed Opportunities:** List the specific benefits outlined or implied in the *plan* that will be lost.
*   **New Risks:** Identify any *new* problems or risks that might arise specifically due to inaction (e.g., competitor actions, obsolescence, non-compliance).
*   **Quantifiable Impacts:** Where possible, provide rough estimates of the scale of negative impacts (e.g., cost increases, time delays, market share loss). State if not quantifiable.
*   **Timescale:** Estimate when the significant consequences of inaction will likely be felt (short, medium, long term).
*   **Assumptions:** State any key assumptions you made about the external environment or internal factors when analyzing inaction.
*   **Comparative Summary:** Directly contrast the likely "do nothing" outcome with the intended outcome if the plan *were* executed.
*   **Risk Assessment:** Provide a final assessment of the overall risk level (Low, Medium, High, Critical) associated with inaction, with a brief justification.

Be specific, objective, and use the context provided by the goal and the plan to inform your analysis of the status quo trajectory.
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
