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

class GovernanceBody(BaseModel):
    name: str = Field(description="Name of the governance body.")
    responsibilities: list[str] = Field(description="Key tasks or responsibilities of this body.")
    initial_setup_actions: list[str] = Field(description="Key initial actions this body needs to take upon formation (e.g., 'Finalize Terms of Reference', 'Elect Chair', 'Set meeting schedule').")
    membership: list[str] = Field(description="Roles or titles of individuals in this governance body.")
    decision_rights: str = Field(description="Type and scope of decisions this body can make.")
    decision_mechanism: str = Field(description="How decisions are typically made (e.g., 'Majority Vote', 'Consensus', 'Chair Decision'). Specify tie-breaker if applicable.")
    meeting_cadence: str = Field(description="How often this body meets.")
    typical_agenda_items: list[str] = Field(description="Example recurring items for this body's meetings.")
    escalation_path: str = Field(description="Where or to whom issues exceeding authority are escalated.")

class DocumentDetails(BaseModel):
    governance_bodies: list[GovernanceBody] = Field(
        description="List of all governance bodies with roles, responsibilities, and membership."
    )

GOVERNANCE_PHASE2_BODIES_SYSTEM_PROMPT = """
You are an expert in project governance and organizational design. Your task is to analyze the provided project description and propose a suitable structure of governance bodies (committees, working groups, etc.) required to effectively oversee and manage the project.

Based *only* on the **project description provided by the user**, define a list of `governance_bodies`. For each body, provide the following details:

1.  **`name`:** A clear and descriptive name for the governance body (e.g., Steering Committee, Technical Working Group, Project Management Office).
2.  **`responsibilities`:** List the key tasks, oversight functions, or areas of accountability for this specific body, relevant to the described project.
3.  **`initial_setup_actions`:** List the essential first steps this body must take upon its formation to become operational (e.g., Finalize Terms of Reference, Elect Chair, Set meeting schedule, Define reporting needs).
4.  **`membership`:** Specify the key roles or titles of individuals who should be members of this body, ensuring necessary expertise and representation for the project's context.
5.  **`decision_rights`:** Clearly describe the scope and type of decisions this body is empowered to make (e.g., Strategic approvals, Budget sign-off > £X, Operational prioritization, Technical standard setting).
6.  **`decision_mechanism`:** Specify how decisions are typically made within this body (e.g., Majority Vote, Consensus, Chair Decision after consultation). Include details on handling tie-breakers or disagreements if applicable.
7.  **`meeting_cadence`:** Recommend an appropriate frequency for this body's meetings (e.g., Weekly, Monthly, Quarterly, Ad-hoc), considering the project phase and the body's function.
8.  **`typical_agenda_items`:** List examples of recurring topics or standard items likely to be discussed in this body's regular meetings, reflecting its responsibilities.
9.  **`escalation_path`:** Define where or to which other body or role issues should be escalated if they exceed this body's authority or cannot be resolved internally.

Focus *only* on defining these governance bodies and their attributes as listed above. Do **not** generate information about audit procedures, transparency measures, a detailed implementation plan for setting up these bodies, a decision escalation matrix based on scenarios, monitoring progress details, or tough questions. These will be handled separately. Ensure the number and type of bodies proposed are appropriate for the scale and nature of the project described.

Ensure your output strictly adheres to the provided Pydantic schema `DocumentDetails` containing *only* the `governance_bodies` list, where each element follows the `GovernanceBody` schema.
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
        
        for i, body in enumerate(document_details.governance_bodies, 1):
            if i == 1:
                rows.append("")
            rows.append(f"\n### {i}. {body.name}")
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
