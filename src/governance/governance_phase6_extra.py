"""
Governance extra fields

PROMPT> python -m src.governance.governance_phase6_extra
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
    governance_validation_checks: list[str] = Field(
        description="A rigorous check of the generated governance components for completeness, consistency, and potential gaps based on the inputs and standard practices."
    )
    tough_questions: list[str] = Field(
        description="Representative questions leadership should regularly ask (e.g., 'Are we on budget?')."
    )
    summary: str = Field(
        description="High-level context or summary of governance approach."
    )
 
GOVERNANCE_PHASE6_EXTRA_SYSTEM_PROMPT = """
You are an expert in project governance quality assurance and reporting. Your task is to **critically validate** the previously generated components of the project governance framework and provide key accountability questions and an overall summary.

**You will be provided with (as context):**
1.  The overall project description.
2.  The defined `internal_governance_bodies` (Stage 2 output).
3.  The `governance_implementation_plan` (Stage 3 output).
4.  The `decision_escalation_matrix` (Stage 4 output).
5.  The `monitoring_progress` plan (Stage 5 output).
6.  (Potentially) `AuditDetails` (Stage 1 output).

**Based on reviewing and VALIDATING ALL the provided governance context, your goal is to generate:**

1.  **`governance_validation_checks`:** (Replaces `governance_assessment_list`)
    *   Perform a **rigorous consistency and completeness check** on the governance components defined in the previous stages.
    *   **Point 1: Completeness Confirmation:** State clearly whether all core requested components (Bodies, Implementation Plan, Escalation Matrix, Monitoring Plan) were successfully generated in the input context.
    *   **Point 2: Internal Consistency Check:** Critically examine if the different components align logically. Identify specific inconsistencies, if any. Examples to check:
        *   Does the Implementation Plan correctly reference the bodies defined in Stage 2?
        *   Does the Escalation Matrix use the correct committee names and logical hierarchy defined in Stage 2?
        *   Do the roles responsible for Monitoring (Stage 5) exist within the bodies defined in Stage 2?
        *   Do the Audit Procedures (Stage 1) align with the responsibilities of the defined bodies (Stage 2)?
    *   **Point 3: Potential Gaps Identification:** Based on standard governance practices and the project description, identify any significant remaining gaps or areas lacking sufficient detail in the generated framework. (e.g., "Missing explicit process for Change Management.", "Lack of detail on stakeholder communication protocols beyond meeting minutes.", "Role of Project Sponsor not fully clarified in SteerCo membership/authority.").
    *   **Be specific in identifying inconsistencies or gaps.** Use point form for clarity. Focus validation on the *generated governance data* provided.

2.  **`tough_questions`:**
    *   Generate a list of **at least 5-7 critical, probing questions** for leadership and governance bodies to ask **regularly** for accountability and risk management, reflecting the project's critical factors, risks, and compliance needs.
    *   Examples: 'What is the variance between actual spend and budget forecast this period?', 'Based on current metrics, what is the projected completion date for [Critical Milestone]?', 'What specific actions resulted from the last [e.g., Ethics Committee] review?', 'Is the [e.g., Sponsorship] pipeline velocity sufficient to meet the target? Show data.'.

3.  **`summary`:**
    *   Write a brief, high-level concluding paragraph (2-4 sentences) summarizing the overall approach and key features of the established governance framework.

Focus *only* on generating `governance_validation_checks`, `tough_questions`, and `summary`. Base your validation and questions on the governance details provided in the input context.

Ensure your output strictly adheres to the provided Pydantic schema `DocumentDetails` containing *only* `governance_validation_checks`, `tough_questions`, and `summary`.
"""

@dataclass
class GovernancePhase6Extra:
    """
    Take a look at the almost finished plan and propose a governance structure, focus only on extra fields.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'GovernancePhase6Extra':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = GOVERNANCE_PHASE6_EXTRA_SYSTEM_PROMPT.strip()

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

        result = GovernancePhase6Extra(
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
                
        rows.append(f"## Governance Validation Checks")
        for i, item in enumerate(document_details.governance_validation_checks, 1):
            if i == 1:
                rows.append("")
            rows.append(f"{i}. {item}")

        rows.append("\n## Tough Questions")
        for i, question in enumerate(document_details.tough_questions, 1):
            if i == 1:
                rows.append("")
            rows.append(f"{i}. {question}")
        
        rows.append(f"\n## Summary\n\n{document_details.summary}")
        
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

    result = GovernancePhase6Extra.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
