"""
Governance Implementation Plan - How to set it up.

Define the specific, sequential steps needed to actually set up and operationalize the internal governance bodies. 
This includes actions like drafting/approving Terms of Reference, formally appointing members, scheduling initial meetings, 
setting up tools (dashboards, reporting templates), and establishing key procedures (audit process kickoff, communication plan finalization).

PROMPT> python -m src.governance.governance_phase3_impl_plan
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

class ImplementationStep(BaseModel):
    step_description: str = Field(description="Specific action required to set up or implement a governance component (e.g., 'Draft Steering Committee ToR', 'Select External Auditor').")
    responsible_body_or_role: str = Field(description="The committee or role primarily responsible for executing or overseeing this step.")
    suggested_timeframe: str = Field(description="A suggested target for completing this step, relative to project start (e.g., 'Within 1 week of kickoff', 'By end of Month 1', 'Ongoing Quarterly').")
    key_outputs_deliverables: list[str] = Field(description="Tangible outputs resulting from this step (e.g., 'Approved Terms of Reference', 'Signed Audit Contract', 'Published Dashboard').")
    dependencies: list[str] = Field(description="Prerequisite steps or decisions needed before this step can be effectively started or completed.")


class DocumentDetails(BaseModel):
    governance_implementation_plan: list[ImplementationStep] = Field(
        description="Actionable steps required to establish and operationalize the described governance framework."
    )

GOVERNANCE_PHASE3_IMPL_PLAN_SYSTEM_PROMPT = """
You are an expert in project management and governance implementation. Your task is to create a practical, detailed, step-by-step implementation plan for establishing the project governance structure that has already been defined. **Think about the logical workflow needed to make each governance body fully operational.**

**You will be provided with:**
1.  The overall project description.
2.  A list of defined `internal_governance_bodies` (including their names, responsibilities, initial setup actions, and memberships) which were determined in a previous step.

**Your goal is to generate the `governance_implementation_plan` by:**
*   Breaking down the necessary setup activities into **granular, logical, sequential steps** (`ImplementationStep`). **Consider multi-step processes where appropriate (e.g., Draft -> Review -> Finalize for key documents like Terms of Reference).**
*   **Including key milestones like the formal appointment/confirmation of committee memberships and the scheduling AND holding of initial kick-off meetings for each body.**
*   Referencing the specific governance bodies provided in the input context accurately.
*   Assigning responsibility for each step clearly.
*   Suggesting realistic timeframes, allowing for potential parallel activities where logical (e.g., multiple Week 1 tasks).
*   Identifying key outputs and **realistic, specific dependencies** for each step.

**Generate a list of `ImplementationStep` objects, ensuring each step includes:**
1.  **`step_description`:** A clear, specific action (e.g., 'Draft Terms of Reference for Project Steering Committee', 'Circulate Draft SteerCo ToR for Member Review', 'Finalize SteerCo ToR based on Feedback', 'Formally Confirm Full PMO Membership', 'Schedule Initial PMO Kick-off Meeting', 'Hold PMO Kick-off Meeting & Review Initial Plan'). **Be specific and action-oriented.**
2.  **`responsible_body_or_role`:** Identify the primary internal body or specific role responsible for ensuring the step is completed. Reference the names of the bodies provided in the input context where applicable.
3.  **`suggested_timeframe`:** Provide a realistic target (e.g., 'Project Week 1', 'Project Week 2', 'By end of Month 1').
4.  **`key_outputs_deliverables`:** List the tangible documents, decisions, or system states resulting from completing this step (e.g., 'Draft SteerCo ToR v0.1', 'Feedback Summary on ToR', 'Approved SteerCo ToR v1.0', 'Confirmed PMO Member List', 'Meeting Invitation & Agenda', 'Meeting Minutes with Action Items').
5.  **`dependencies`:** List **specific prerequisite steps from this plan** or key project decisions that must be completed *before* this step can effectively start or finish (e.g., 'Draft Steering Committee ToR Completed', 'Steering Committee Chair Appointed', 'Relevant Policy Approved'). **Avoid overly generic or potentially incorrect dependencies.**

**Consider the logical order:** Committees need Terms of Reference before formal operation. Members need appointing. Kick-off meetings are crucial for alignment. Policy development might depend on committee formation.

Focus *only* on generating the `governance_implementation_plan` list based on the provided project description and the pre-defined governance bodies. Do **not** redefine the governance bodies themselves or generate information for other governance sections.

Ensure your output strictly adheres to the provided Pydantic schema `DocumentDetails` containing *only* the `governance_implementation_plan` list, where each element follows the `ImplementationStep` schema.
"""

@dataclass
class GovernancePhase3ImplPlan:
    """
    Take a look at the almost finished plan and propose a governance structure, focus only on the governance implementation plan.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'GovernancePhase3ImplPlan':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = GOVERNANCE_PHASE3_IMPL_PLAN_SYSTEM_PROMPT.strip()

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

        result = GovernancePhase3ImplPlan(
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
        
        for i, item in enumerate(document_details.governance_implementation_plan, 1):
            rows.append(f"### {i}. {item.step_description}")
            rows.append(f"\n**Responsible Body/Role:** {item.responsible_body_or_role}")
            rows.append(f"\n**Suggested Timeframe:** {item.suggested_timeframe}")
            rows.append(f"\n**Key Outputs/Deliverables:**\n")
            for output in item.key_outputs_deliverables:
                rows.append(f"- {output}")
            rows.append(f"\n**Dependencies:**\n")
            for dependency in item.dependencies:
                rows.append(f"- {dependency}")

        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")

    plan_prompt = find_plan_prompt("4060d2de-8fcc-4f8f-be0c-fdae95c7ab4f")
    query = (
        f"{plan_prompt}\n\n"
        "Today's date:\n2025-Mar-23\n\n"
        "Project start ASAP"
    )
    print(f"Query: {query}")

    result = GovernancePhase3ImplPlan.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
