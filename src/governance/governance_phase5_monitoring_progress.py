"""
Monitoring Progress

To define how project progress (especially concerning governance effectiveness and overall health) is tracked and how accountability is maintained.

PROMPT> python -m src.governance.governance_phase5_monitoring_progress
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

class MonitoringProgress(BaseModel):
    approach: str = Field(description="General approach to monitoring progress.")
    monitoring_tools_platforms: list[str] = Field(description="Specific tools or platforms used for monitoring (e.g., 'Asana dashboard', 'Shared KPI Spreadsheet', 'Monthly Report Template').")
    frequency: str = Field(description="How often progress is reviewed.")
    responsible_role: str = Field(description="Role or group responsible for collecting/analyzing data.")
    adaptation_process: str = Field(description="How plan changes are made based on monitoring data.")
    adaptation_trigger: str = Field(description="What specifically triggers the adaptation process (e.g., 'KPI deviation > 10%', 'Steering Committee review').")

class DocumentDetails(BaseModel):
    monitoring_progress: list[MonitoringProgress] = Field(
        description="How the team monitors progress and adapts the plan over time."
    )

GOVERNANCE_PHASE5_MONITORING_PROGRESS_SYSTEM_PROMPT = """
You are an expert in project management, monitoring, and evaluation. Your task is to define how progress will be monitored and how the project plan will be adapted based on that monitoring for the described project.

**You will be provided with:**
1.  The overall project description.
2.  (Potentially) A list of defined `internal_governance_bodies` (e.g., PMO, Steering Committee).

**Your goal is to generate the `monitoring_progress` list.** Define one or more distinct approaches to monitoring different aspects of the project (e.g., one for overall progress/budget, another for risk, another for compliance, if appropriate for the project).

**For each monitoring approach (`MonitoringProgress` object) you define, provide:**
1.  **`approach`:** A clear description of the monitoring method or focus (e.g., 'Tracking Key Performance Indicators (KPIs) against Project Plan', 'Regular Risk Register Review', 'Stakeholder Feedback Analysis', 'Compliance Audit Monitoring').
2.  **`monitoring_tools_platforms`:** List the **specific tools, documents, or platforms** that will be used for this monitoring approach (e.g., 'Project Management Software (e.g., Asana) Dashboard', 'Shared KPI Tracking Spreadsheet', 'Monthly Progress Report Template', 'Risk Register Document', 'Attendee/Sponsor Survey Platform', 'Compliance Checklist').
3.  **`frequency`:** State **how often** this specific monitoring review or data collection occurs (e.g., 'Weekly', 'Bi-weekly', 'Monthly', 'Quarterly', 'Post-Milestone', 'Post-Event').
4.  **`responsible_role`:** Identify the **specific internal role or governance body** primarily responsible for executing this monitoring approach (collecting data, performing analysis, preparing reports) (e.g., 'Project Manager', 'PMO', 'Marketing Coordinator', 'Ethics & Compliance Committee', 'Steering Committee Secretariat'). Use roles/bodies consistent with the project context or provided governance structure.
5.  **`adaptation_process`:** Briefly describe **how changes are typically made** to the project plan or operations as a result of this monitoring (e.g., 'PMO proposes adjustments, submitted via Change Request to Steering Committee', 'Risk mitigation plan updated by Risk Lead, reviewed by Steering Committee', 'Feedback informs adjustments to next event cycle plan', 'Corrective actions assigned by Ethics Committee').
6.  **`adaptation_trigger`:** Define the **specific condition or event** that initiates the `adaptation_process` based on this monitoring approach (e.g., 'KPI deviates >10% from target', 'New critical risk identified during review', 'Scheduled Steering Committee review meeting', 'Negative feedback trend identified in surveys', 'Audit finding requires corrective action').

Focus *only* on generating the `monitoring_progress` list. Define practical and relevant monitoring approaches for the described project. Do **not** generate information for other governance sections (audit details, bodies, implementation plan, escalation matrix, tough questions, summary).

Ensure your output strictly adheres to the provided Pydantic schema `DocumentDetails` containing *only* the `monitoring_progress` list, where each element follows the `MonitoringProgress` schema.
"""

@dataclass
class GovernancePhase5MonitoringProgress:
    """
    Take a look at the almost finished plan and propose a governance structure, focus only on monitoring progress.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'GovernancePhase5MonitoringProgress':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = GOVERNANCE_PHASE5_MONITORING_PROGRESS_SYSTEM_PROMPT.strip()

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

        result = GovernancePhase5MonitoringProgress(
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
        
        for i, item in enumerate(document_details.monitoring_progress, 1):
            if i > 1:
                rows.append("")
            rows.append(f"### {i}. {item.approach}")
            rows.append(f"**Monitoring Tools/Platforms:**\n")
            for monitoring_tool_platform in item.monitoring_tools_platforms:
                rows.append(f"  - {monitoring_tool_platform}")
            rows.append(f"\n**Frequency:** {item.frequency}")
            rows.append(f"\n**Responsible Role:** {item.responsible_role}")
            rows.append(f"\n**Adaptation Process:** {item.adaptation_process}")
            rows.append(f"\n**Adaptation Trigger:** {item.adaptation_trigger}")

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

    result = GovernancePhase5MonitoringProgress.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
