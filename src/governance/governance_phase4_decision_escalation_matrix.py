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
You are an expert in project governance and risk management. Your task is to create a Decision Escalation Matrix for the described project, outlining how specific types of significant issues or decisions are escalated through the pre-defined governance structure. **This matrix defines what happens when specific PROBLEMS, DISAGREEMENTS, or DECISIONS requiring higher authority occur DURING project execution.** It is NOT about the steps to set up the committees themselves.

**You will be provided with:**
1.  The overall project description (which may contain budget information in a specific currency).
2.  A list of defined `internal_governance_bodies` (including their names and typical hierarchy, e.g., PMO reports to Steering Committee) which were determined in a previous stage.

**Your goal is to generate the `decision_escalation_matrix` list.** You must identify **at least 5 distinct scenarios representing potential PROBLEMS or critical DECISIONS** that might arise *during the project* and would require escalation beyond the initial team or committee level.

**DO NOT use project setup tasks (like 'Draft ToR', 'Hold Kick-off Meeting', 'Appoint Chair') as the `issue_type`.** The `issue_type` must be a **problem or decision scenario** encountered during project execution.

**Examples of VALID `issue_type` scenarios:**
*   'Budget Overrun Exceeding [Specific Threshold, e.g., 10% or a defined monetary value like "10,000 units"]' *(Use a relevant threshold based on project context if possible, otherwise state '% threshold')*
*   'Major Proposed Scope Change with Significant Impact'
*   'Critical Risk Materializes (e.g., Key Supplier Fails, Venue Unavailable)'
*   'Serious Ethical Concern Reported (e.g., Data Privacy Violation)'
*   'Unresolvable Resource Conflict Between Teams'
*   'Steering Committee Deadlock on Strategic Decision'
*   'Significant Deviation from Approved Timeline (>X weeks/months)'

**For each scenario (`DecisionEscalationItem`) you identify in the matrix, provide:**
1.  **`issue_type`:** A clear description of the **specific PROBLEM or DECISION scenario** requiring escalation. **Must NOT be a setup task.** If referencing a budget threshold, state it clearly (e.g., 'Exceeding 10% budget variance' or 'Expenditure request over [Value] units').
2.  **`escalation_level`:** Identify the **specific name** of the `InternalGovernanceBody` or senior role (e.g., 'Project Steering Committee', 'Executive Sponsor') from the provided governance structure where this problem/decision goes **NEXT** for resolution. **This must be a higher level in the hierarchy.**
3.  **`approval_process`:** Briefly outline how the escalated problem/decision is typically handled **at that higher level** (e.g., 'Steering Committee reviews options and votes', 'Sponsor makes final call', 'Formal change request process invoked').
4.  **`rationale`:** Explain *why* this specific **problem/decision scenario** needs to be escalated (e.g., 'Impacts strategic goals', 'Exceeds delegated financial authority', 'Requires resources beyond project budget', 'Potential legal ramifications').
5.  **`negative_consequences`:** Describe the likely adverse outcomes if this specific **problem/decision scenario** is *not* escalated or resolved effectively (e.g., 'Project failure', 'Major financial loss', 'Reputational crisis', 'Legal action').

Focus *only* on generating the `decision_escalation_matrix` list containing **problem/decision scenarios** and their escalation paths based on the provided project description and the pre-defined governance bodies. Do **not** generate information for other governance sections. Ensure the escalation paths defined are logical and move upwards in the defined hierarchy.

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
