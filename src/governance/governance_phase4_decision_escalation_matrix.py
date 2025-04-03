"""
Decision Escalation Matrix

To define how specific types of important issues or decisions are escalated beyond the body or role 
where they initially arise or cannot be resolved. This provides clarity and prevents bottlenecks.

PROMPT> python -m src.governance.governance_phase4_decision_escalation_matrix
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

class DecisionEscalationItem(BaseModel):
    issue_type: str = Field(
        description="Type of issue (e.g., budget overruns, ethical concerns, strategic pivot)."
    )
    escalation_level: str = Field(
        description="Indicates the governance body or role to which the issue is escalated (e.g., Steering Committee)."
    )
    approval_process: str = Field(
        description="Outlines how an issue is approved or resolved once escalated (e.g., majority vote)."
    )
    rationale: str = Field(
        description="Explains *why* this issue triggers escalation—i.e. potential impacts or risks that justify escalating."
    )
    negative_consequences: str = Field(
        description="Describes the potential adverse outcomes or risks if this issue remains unresolved or is not escalated in a timely manner."
    )

class DocumentDetails(BaseModel):
    decision_escalation_matrix: list[DecisionEscalationItem] = Field(
        description="Clear escalation paths for various issues."
    )

GOVERNANCE_PHASE4_DECISION_ESCALATION_MATRIX_SYSTEM_PROMPT = """
You are an expert in project governance and risk management. Your task is to create a Decision Escalation Matrix for the described project, outlining how specific types of significant issues or decisions are escalated through the pre-defined governance structure.

**You will be provided with:**
1.  The overall project description.
2.  A list of defined `internal_governance_bodies` (including their names, responsibilities, and typical hierarchy, e.g., PMO reports to Steering Committee) which were determined in a previous stage.

**Your goal is to generate the `decision_escalation_matrix` by identifying several critical or common project scenarios that would likely require escalation and defining the path for each.** Aim for **at least 5 distinct and relevant scenarios** based on the project type (e.g., consider budget, scope, timeline, resource conflicts, critical risks, ethical concerns, stakeholder issues).

**For each scenario (`DecisionEscalationItem`) in the matrix, provide:**
1.  **`issue_type`:** A clear description of the specific issue or decision requiring escalation (e.g., 'Budget Overrun Exceeding 10% Threshold', 'Major Scope Change Request with Significant Impact', 'Critical Risk Event Occurs (e.g., Venue Cancellation)', 'Unresolved Ethical Complaint Reported', 'Failure to Reach Consensus within [Committee Name] on Key Decision', 'Significant Negative Stakeholder Feedback'). **Be specific.**
2.  **`escalation_level`:** Identify the **specific name** of the `InternalGovernanceBody` or senior role (e.g., 'Project Steering Committee', 'Executive Sponsor', 'Legal Counsel') from the provided governance structure to which this *specific issue type* is escalated *next* in the hierarchy. **Ensure this aligns logically with the provided governance structure.**
3.  **`approval_process`:** Briefly outline how the issue is typically reviewed and resolved *at the specified escalation level* (e.g., 'Review by Steering Committee, decision by majority vote', 'Requires sign-off from Executive Sponsor', 'Legal Counsel provides binding recommendation', 'Formal change request submitted to PMO, approved by Steering Committee').
4.  **`rationale`:** Explain *why* this particular `issue_type` warrants escalation to this specific `escalation_level`. Focus on the potential impact, authority required, or nature of the issue (e.g., 'Exceeds PMO budget authority', 'Requires strategic decision impacting project goals', 'Potential legal/reputational implications require ethical oversight', 'Cross-functional resource conflict needs higher arbitration').
5.  **`negative_consequences`:** Describe the likely adverse outcomes if this specific `issue_type` is *not* escalated or resolved effectively in a timely manner (e.g., 'Project cancellation due to funding gap', 'Failure to meet key objectives', 'Legal fines or lawsuits', 'Significant reputational damage', 'Project delays and team demotivation').

Focus *only* on generating the `decision_escalation_matrix` list based on the provided project description and the pre-defined governance bodies. Do **not** generate information for other governance sections. Ensure the escalation paths defined are logical and consistent with the provided governance structure.

Ensure your output strictly adheres to the provided Pydantic schema `DocumentDetails` containing *only* the `decision_escalation_matrix` list, where each element follows the `DecisionEscalationItem` schema.
"""

@dataclass
class GovernancePhase4DecisionEscalationMatrix:
    """
    Take a look at the almost finished plan and propose a governance structure, focus only on the decision escalation matrix.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'GovernancePhase4DecisionEscalationMatrix':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = GOVERNANCE_PHASE4_DECISION_ESCALATION_MATRIX_SYSTEM_PROMPT.strip()

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

        result = GovernancePhase4DecisionEscalationMatrix(
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
        
        for i, item in enumerate(document_details.decision_escalation_matrix, 1):
            if i > 1:
                rows.append("")
            rows.append(f"**{item.issue_type}**")
            rows.append(f"Escalation Level: {item.escalation_level}")
            rows.append(f"Approval Process: {item.approval_process}")
            rows.append(f"Rationale: {item.rationale}")
            rows.append(f"Negative Consequences: {item.negative_consequences}")

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

    result = GovernancePhase4DecisionEscalationMatrix.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
