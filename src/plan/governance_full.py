"""
Governance, Accountability, & Audit Framework: 
- Corruption
- Misallocation Risks. 
- monitoring progress and adapting the plan over time.
- audit procedures, corruption countermeasures, and multi-stakeholder transparency (public dashboards, third-party evaluations, etc.).
- Set Up Governance Structure
- Establish how decisions will be made and issues escalated during execution.
- Decide how often they meet.
- ask tough questions.

PROMPT> python -m src.plan.governance
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

class AuditDetails(BaseModel):
    corruption_list: list[str] = Field(
        description="Corruption risks in this project: bribery, nepotism, etc."
    )
    misallocation_list: list[str] = Field(
        description="Ways resources can be misallocated: budget misuse, double spending, etc."
    )
    audit_procedures: list[str] = Field(
        description="Procedures for conducting regular and ad-hoc audits (e.g., quarterly external audits)."
    )
    transparency_measures: list[str] = Field(
        description="Mechanisms to ensure transparency (e.g., public dashboards, published meeting minutes)."
    )

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

class DecisionEscalation(BaseModel):
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


class ImplementationStep(BaseModel):
    step_description: str = Field(description="Specific action required to set up or implement a governance component (e.g., 'Draft Steering Committee ToR', 'Select External Auditor').")
    responsible_body_or_role: str = Field(description="The committee or role primarily responsible for executing or overseeing this step.")
    suggested_timeframe: str = Field(description="A suggested target for completing this step, relative to project start (e.g., 'Within 1 week of kickoff', 'By end of Month 1', 'Ongoing Quarterly').")
    key_outputs_deliverables: list[str] = Field(description="Tangible outputs resulting from this step (e.g., 'Approved Terms of Reference', 'Signed Audit Contract', 'Published Dashboard').")
    dependencies: list[str] = Field(description="Prerequisite steps or decisions needed before this step can be effectively started or completed.")

class MonitoringProgress(BaseModel):
    approach: str = Field(description="General approach to monitoring progress.")
    monitoring_tools_platforms: list[str] = Field(description="Specific tools or platforms used for monitoring (e.g., 'Asana dashboard', 'Shared KPI Spreadsheet', 'Monthly Report Template').")
    frequency: str = Field(description="How often progress is reviewed.")
    responsible_role: str = Field(description="Role or group responsible for collecting/analyzing data.")
    adaptation_process: str = Field(description="How plan changes are made based on monitoring data.")
    adaptation_trigger: str = Field(description="What specifically triggers the adaptation process (e.g., 'KPI deviation > 10%', 'Steering Committee review').")

class DocumentDetails(BaseModel):
    audit_details: AuditDetails = Field(
        description="Audit details and transparency measures."
    )
    governance_bodies: list[GovernanceBody] = Field(
        description="List of all governance bodies with roles, responsibilities, and membership."
    )
    governance_implementation_plan: list[ImplementationStep] = Field(
        description="Actionable steps required to establish and operationalize the described governance framework."
    )
    decision_escalation_matrix: list[DecisionEscalation] = Field(
        description="Clear escalation paths for various issues."
    )
    monitoring_progress: list[MonitoringProgress] = Field(
        description="How the team monitors progress and adapts the plan over time."
    )
    tough_questions: list[str] = Field(
        description="Representative questions leadership should regularly ask (e.g., 'Are we on budget?')."
    )
    summary: str = Field(
        description="High-level context or summary of governance approach."
    )

GOVERNANCE_SYSTEM_PROMPT = """
You are a governance and project management expert. Your role is to analyze project plans and provide detailed recommendations for establishing robust governance frameworks. Focus on:

1. GOVERNANCE STRUCTURE
 - Recommend clear roles and responsibilities
 - Define reporting lines and accountability measures
 - Outline key governance bodies (steering committees, working groups, etc.)
 - For each body, specify key **initial setup actions** required upon formation.

2. DECISION-MAKING PROCESSES
 - Establish clear decision rights and delegation frameworks
 - Define escalation paths for different types of issues
 - Outline approval processes for key decisions
 - Indicate whether each governance body makes decisions by consensus, majority vote, or other mechanisms. **Specify the primary `decision_mechanism` and how tie-breakers or disagreements are handled.**
 - Provide example agenda items for each governance body's regular meetings (e.g., progress review, budget status, risk discussion). **List these as `typical_agenda_items`.**
 - Outline how meeting outputs (decisions, actions) are documented and shared.

3. MEETING CADENCE & OVERSIGHT
 - Recommend appropriate meeting frequency for different governance bodies
 - Define standard agenda items and review cycles
 - Outline monitoring and reporting requirements

4. RISK MANAGEMENT & CONTROLS
 - Identify potential governance risks and mitigation strategies
 - Recommend control mechanisms and audit procedures
 - Outline transparency and stakeholder communication approaches
 - Identify how each governance body will interact with local stakeholders in each participating country.
 - Provide sample standard agenda items for Steering Committee vs. PMO vs. Ethics & Compliance meetings.
 - Elaborate on procedures to measure governance effectiveness (e.g., periodic governance reviews, stakeholder surveys).
 - Suggest a mechanism for rotating membership or leadership roles to avoid stagnation or conflicts of interest.
 - Outline how local stakeholder groups should coordinate with national governments and the PMO.
 - Recommend how community members are selected or rotated to ensure representation and continuity.
 - Provide additional detail on how the Ethics & Compliance Committee coordinates with local groups to address moral or social concerns.
 - Suggest how to measure environmental impacts under the program's sustainability standards.
 - Where relevant, suggest specific **`monitoring_tools_platforms`** (e.g., specific software, templates) to support monitoring.
 - Define clear **`adaptation_trigger`** points for plan changes based on monitoring.

5. CONTINUOUS IMPROVEMENT
 - Suggest mechanisms for governance framework review
 - Outline processes for incorporating lessons learned
 - Recommend metrics for measuring governance effectiveness
 - Describe the workflow of a change request from identification to approval.
 - Outline how change requests are documented, analyzed for impact, and tracked in the project plan.

6. IMPLEMENTATION PLAN
 - **Crucially, generate a `governance_implementation_plan`. This should be a list of specific, actionable steps required to set up the governance framework you are recommending.**
 - For each step (`ImplementationStep`), define the `step_description`, the `responsible_body_or_role`, a `suggested_timeframe` (relative to project start, e.g., 'Week 1', 'Month 1'), any critical `dependencies`, and the tangible `key_outputs_deliverables`.
 - Ensure this plan covers the formation of committees, establishment of procedures (audit, communication), and setup of tools (dashboards, reporting templates).

Analyze the provided project description and provide specific, actionable recommendations for each of these areas. Focus on practical, implementable solutions that balance oversight with operational efficiency. Ensure the output strictly adheres to the Pydantic schema provided.
"""

@dataclass
class GovernanceFull:
    """
    Take a look at the almost finished plan and propose a governance structure.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'GovernanceFull':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = GOVERNANCE_SYSTEM_PROMPT.strip()

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

        result = GovernanceFull(
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
        
        # Add audit details section
        rows.append("\n## Audit - Corruption Risks\n")
        for item in document_details.audit_details.corruption_list:
            rows.append(f"- {item}")
            
        rows.append("\n## Audit - Misallocation Risks\n")
        for item in document_details.audit_details.misallocation_list:
            rows.append(f"- {item}")
            
        rows.append("\n## Audit - Procedures\n")
        for item in document_details.audit_details.audit_procedures:
            rows.append(f"- {item}")
            
        rows.append("\n## Audit - Transparency Measures\n")
        for item in document_details.audit_details.transparency_measures:
            rows.append(f"- {item}")
        
        # Add governance bodies section
        rows.append("\n## Governance Bodies")
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
        
        # Add governance implementation plan section
        rows.append("\n## Governance Implementation Plan")
        for i, step in enumerate(document_details.governance_implementation_plan, 1):
            if i == 1:
                rows.append("")
            rows.append(f"\n### {i}. {step.step_description}")
            rows.append(f"\n**Responsible Body/Role:** {step.responsible_body_or_role}")
            rows.append(f"\n**Suggested Timeframe:** {step.suggested_timeframe}")
            
            rows.append(f"\n**Key Outputs/Deliverables:**")
            for output in step.key_outputs_deliverables:
                rows.append(f"- {output}")
                
            rows.append(f"\n**Dependencies:**")
            for dependency in step.dependencies:
                rows.append(f"- {dependency}")
        
        # Add decision escalation matrix section
        rows.append("\n## Decision Escalation Matrix")
        for i, escalation in enumerate(document_details.decision_escalation_matrix, 1):
            if i == 1:
                rows.append("")
            rows.append(f"\n### {i}. {escalation.issue_type}")
            rows.append(f"\n**Escalation Level:** {escalation.escalation_level}")
            rows.append(f"\n**Approval Process:** {escalation.approval_process}")
            rows.append(f"\n**Rationale:** {escalation.rationale}")
            rows.append(f"\n**Negative Consequences:** {escalation.negative_consequences}")
        
        # Add monitoring progress section
        rows.append("\n## Monitoring Progress")
        for i, monitoring in enumerate(document_details.monitoring_progress, 1):
            if i == 1:
                rows.append("")
            rows.append(f"\n### {i}. {monitoring.approach}")
            rows.append(f"\n**Monitoring Tools/Platforms:**")
            for tool in monitoring.monitoring_tools_platforms:
                rows.append(f"- {tool}")
            rows.append(f"\n**Frequency:** {monitoring.frequency}")
            rows.append(f"\n**Responsible Role:** {monitoring.responsible_role}")
            rows.append(f"\n**Adaptation Process:** {monitoring.adaptation_process}")
            rows.append(f"\n**Adaptation Trigger:** {monitoring.adaptation_trigger}")
        
        # Add tough questions section
        rows.append("\n## Tough Questions")
        for i, question in enumerate(document_details.tough_questions, 1):
            if i == 1:
                rows.append("")
            rows.append(f"{i}. {question}")
        
        rows.append(f"\n## Summary\n{document_details.summary}")
        
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

    result = GovernanceFull.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
