"""
Governance bodies: 

PROMPT> python -m src.governance.governance_phase2_bodies
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

class InternalGovernanceBody(BaseModel):
    name: str = Field(description="Name of the internal governance body.")
    rationale_for_inclusion: str = Field(
        description="Brief justification explaining *why* this specific type of internal governance body (e.g., Steering Committee, PMO, Ethics Committee) is necessary or appropriate for *this particular project*, based on its description, scale, or key challenges."
    )
    responsibilities: list[str] = Field(description="Key tasks or responsibilities of this internal body.")
    initial_setup_actions: list[str] = Field(description="Key initial actions this body needs to take upon formation (e.g., 'Finalize Terms of Reference', 'Elect Chair', 'Set meeting schedule').")
    membership: list[str] = Field(description="Roles or titles of individuals *within the project/organization* forming this internal body.")
    decision_rights: str = Field(description="Type and scope of decisions this internal body is empowered to make.")
    decision_mechanism: str = Field(description="How decisions are typically made within this internal body. Specify tie-breaker if applicable.")
    meeting_cadence: str = Field(description="How often this internal body meets.")
    typical_agenda_items: list[str] = Field(description="Example recurring items for this internal body's meetings.")
    escalation_path: str = Field(description="Where or to which *other internal body or senior project/organization role* issues exceeding authority are escalated.")

class DocumentDetails(BaseModel):
    internal_governance_bodies: list[InternalGovernanceBody] = Field(
        description="List of all internal governance bodies with roles, responsibilities, and membership."
    )

GOVERNANCE_PHASE2_BODIES_SYSTEM_PROMPT = """
You are an expert in project governance and organizational design. Your task is to analyze the provided project description and propose a suitable structure of **distinct INTERNAL project governance bodies** (committees, working groups, etc.) required to effectively oversee and manage the project internally.

**Consider these common types of INTERNAL governance bodies and select/adapt those most appropriate for the described project:**
*   **Strategic Oversight:** e.g., Project Steering Committee (SteerCo), Project Board. (Provides high-level direction, major approvals).
*   **Operational Management:** e.g., Project Management Office (PMO), Core Project Team. (Manages day-to-day execution).
*   **Specialized Advisory/Assurance:** e.g., Technical Advisory Group, Ethics & Compliance Committee, User Advisory Board, Stakeholder Engagement Group. (Provides expert input or specific oversight).

**Propose a structure that logically separates strategic oversight from day-to-day operational management within the project or its parent organization.** Avoid creating committees with overlapping core functions unless clearly justified. Ensure the number and type of bodies are appropriate for the project's scale and nature. **Crucially, define ONLY internal bodies composed of project/organization personnel or designated internal representatives. Do NOT define external regulatory bodies (like government authorities or standards organizations) as internal governance bodies.**

Based *only* on the **project description provided by the user**, define a list named `internal_governance_bodies`. Each element in this list must be an `InternalGovernanceBody` object with the following details:

1.  **`name`:** A clear name for the *internal* body (e.g., 'Project Steering Committee').
2.  **`rationale_for_inclusion`:** Justification explaining *why* this *internal* body is needed for *this project*.
3.  **`responsibilities`:** Key tasks for this *internal* body.
4.  **`initial_setup_actions`:** Essential first steps for this *internal* body.
5.  **`membership`:** Key roles/titles of *internal personnel or designated representatives* forming this body.
6.  **`decision_rights`:** Scope/type of decisions this *internal* body makes.
7.  **`decision_mechanism`:** How decisions are made *within* this body (e.g., Majority Vote, Consensus). Specify tie-breakers.
8.  **`meeting_cadence`:** Recommended meeting *frequency* (e.g., Weekly, Monthly).
9.  **`typical_agenda_items`:** Recurring topics reflecting the *internal* body's responsibilities.
10. **`escalation_path`:** The *next internal body or senior role* for unresolved issues.

Focus *only* on defining these **internal project governance bodies** and their attributes. Ensure the proposed structure is logical. Do **not** generate information about audit procedures, external regulatory interactions (except potentially as context for an internal body's responsibility, e.g., 'Ensure compliance with [External Body] regulations'), implementation plans, etc.

Ensure your output strictly adheres to the provided Pydantic schema `DocumentDetails` containing *only* the `internal_governance_bodies` list, where each element follows the `InternalGovernanceBody` schema.
"""

@dataclass
class GovernancePhase2Bodies:
    """
    Take a look at the almost finished plan and propose a governance structure, focus only on the governance bodies part.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'GovernancePhase2Bodies':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = GOVERNANCE_PHASE2_BODIES_SYSTEM_PROMPT.strip()

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

        result = GovernancePhase2Bodies(
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
        
        for i, body in enumerate(document_details.internal_governance_bodies, 1):
            if i == 1:
                rows.append("")
            rows.append(f"\n### {i}. {body.name}")
            rows.append(f"\n**Rationale for Inclusion:** {body.rationale_for_inclusion}")
            rows.append(f"\n**Responsibilities:**")
            for resp in body.responsibilities:
                rows.append(f"- {resp}")
                
            rows.append(f"\n**Initial Setup Actions:**")
            for action in body.initial_setup_actions:
                rows.append(f"- {action}")
                
            rows.append(f"\n**Membership:**")
            for member in body.membership:
                rows.append(f"- {member}")
                
            rows.append(f"\n**Decision Rights:** {body.decision_rights}")
            rows.append(f"\n**Decision Mechanism:** {body.decision_mechanism}")
            rows.append(f"\n**Meeting Cadence:** {body.meeting_cadence}")
            
            rows.append(f"\n**Typical Agenda Items:**")
            for item in body.typical_agenda_items:
                rows.append(f"- {item}")
                
            rows.append(f"\n**Escalation Path:** {body.escalation_path}")
        
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

    result = GovernancePhase2Bodies.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
