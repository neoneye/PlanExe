"""
Generates a preliminary checklist of required documents and data sources needed to start detailed planning.

Interpret the project goals and suggest:
- Documents to draft (e.g., Charter, Plans, Reports).
- Data/Information to locate (e.g., Market Data, Regulations, Existing Studies).
- Standard Project Management documents.

PROMPT> python -m src.plan.identify_documents
"""
import os
import json
import time
import logging
from uuid import uuid4
from math import ceil
from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class CreateDocumentItem(BaseModel):
    document_name: str = Field(
        description="The specific name of the document to be created (e.g., 'Project Charter', 'Detailed Financial Model', 'Stakeholder Communication Plan')."
    )
    description: str = Field(
        description=(
            "A concise yet comprehensive description of the document, "
            "including its purpose, document type (e.g., 'Policy Framework', 'International Agreement', 'Project Charter'), "
            "the intended primary audience(s), and any special notes such as specific context, constraints, or approvals needed."
        )
    )
    responsible_role_type: str = Field(
        description="The specific functional role or primary skill type responsible for creating or obtaining this document (e.g., 'Project Manager', 'Financial Analyst', 'Legal Counsel', 'Communication Specialist'). This field is mandatory."
    )
    document_template_primary: Optional[str] = Field(
        default=None,
        description="A suggested source or standard name for a primary template, if widely applicable (e.g., 'PMI Project Charter Template', 'World Bank Logical Framework'). Note that local/industry-specific templates might be required."
    )
    document_template_secondary: Optional[str] = Field(
        default=None,
        description="A suggested source or standard name for a secondary template, if applicable. Note that local/industry-specific templates might be required."
    )
    steps_to_create: list[str] = Field(
        description="High-level steps required to create this document, based on its purpose and the project context. Mention if key stakeholder input or signatures are typically needed."
    )
    approval_authorities: Optional[str] = Field(
        default=None,
        description="Specify roles or entities required to formally approve or sign off on this document (e.g., 'Legal Counsel', 'Heads of State', 'Ministry of Finance')."
    )

class FindDocumentItem(BaseModel):
    """A document that is to be found online or in a physical location, such as existing data, reports, contracts, permits, etc."""
    document_name: str = Field(
        description="The specific name or type of document/data to be found (e.g., 'Participating Nations GDP Data', 'Existing Childcare Support Program Reports', 'Local Zoning Regulations', 'Grid Connection Capacity Study')."
    )
    description: str = Field(
        description=(
            "A clear description of the existing document or data, "
            "including its type or nature (e.g., 'National GDP statistics', 'Mental Health Policy reports'), "
            "its purpose within the project context, intended audience, and any relevant constraints such as recency or regulatory considerations."
        )
    )
    recency_requirement: Optional[str] = Field(
        default=None,
        description="Guidance on how recent the document or data should ideally be, based on its type and purpose (e.g., 'Most recent available year', 'Published within last 2 years', 'Historical data acceptable', 'Current regulations essential')."
    )
    responsible_role_type: str = Field(
        description="The specific functional role or primary skill type responsible for creating or obtaining this document (e.g., 'Project Manager', 'Financial Analyst', 'Legal Counsel', 'Communication Specialist'). This field is mandatory."
    )
    steps_to_find: list[str] = Field(
        description="Likely steps to find the document/data (e.g., 'Contact national statistical offices', 'Search World Bank Open Data', 'Check local municipality website', 'Submit formal request to agency')."
    )
    access_difficulty: str = Field(
        description="Assessment of access difficulty: 'Easy' (e.g., public websites, open data portals), 'Medium' (e.g., requires registration, specific agency contact, freedom of information request), 'Hard' (e.g., requires authentication, negotiation, potential fees, classified). Provide a brief justification."
    )

class DocumentDetails(BaseModel):
    documents_to_create: list[CreateDocumentItem] = Field(
        description="Documents essential for project planning and execution that need to be created. Includes both subject-matter reports and standard project management artifacts."
    )
    documents_to_find: list[FindDocumentItem] = Field(
        description="Existing documents or datasets that must be obtained to inform the planning process."
    )
    documents_to_create_part2: list[CreateDocumentItem] = Field(
        description="Documents that are to be created, that for some reason were not identified in the first pass. Do not repeat documents already identified in the first pass."
    )
    documents_to_find_part2: list[FindDocumentItem] = Field(
        description="Documents that are to be found online or in a physical location, that for some reason were not identified in the first pass. Do not repeat documents already identified in the first pass."
    )

class CleanedupCreateDocumentItem(BaseModel):
    id: str
    document_name: str
    description: str
    responsible_role_type: str
    document_template_primary: Optional[str]
    document_template_secondary: Optional[str]
    steps_to_create: list[str]
    approval_authorities: Optional[str]

class CleanedupFindDocumentItem(BaseModel):
    id: str
    document_name: str
    description: str
    recency_requirement: Optional[str]
    responsible_role_type: str
    steps_to_find: list[str]
    access_difficulty: str

class CleanedupDocumentDetails(BaseModel):
    documents_to_create: list[CleanedupCreateDocumentItem]
    documents_to_find: list[CleanedupFindDocumentItem]

IDENTIFY_DOCUMENTS_SYSTEM_PROMPT = """
You are an expert in project planning and documentation. Your task is to analyze the provided project description and identify essential documents (both to create and to find) required *before* a comprehensive operational plan can be effectively developed. Focus strictly on the prerequisites needed to *start* detailed planning.

Based *only* on the **project description provided by the user**, generate the following details:

1.  **Documents to Create:** Clearly identify each document to be drafted during the *initial planning and strategy development phase*:
    *   Include documents explicitly mentioned or implied by the project description (e.g., charters, agreements, strategic plans).
    *   Ensure a dedicated high-level document (e.g., a 'Plan', 'Strategy', or initial 'Framework') is created for each major intervention area identified in the user prompt (e.g., reversing declining fertility rates, reducing financial burden of children, improving housing affordability, streamlining education/job access, improving social well-being/mental health). Interpret potential user prompt ambiguities logically (e.g., treat 'Reduce housing affordability' as 'Improve housing affordability').
    *   Suggest creating an initial baseline assessment or report relevant to the core problem (e.g., 'Current State Assessment of Fertility Trends').
    *   Include standard project management documents typically required *at the outset* (e.g., Project Charter, Risk Register, Communication Plan, Stakeholder Engagement Plan, Change Management Plan, High-Level Budget/Funding Framework, Funding Agreement Structure/Template, Initial High-Level Schedule/Timeline, M&E Framework), explicitly tailored to the provided context.
    *   **SCOPE:** Ensure these documents represent high-level strategies, frameworks, or foundational plans needed *before* detailed operational planning. **Do NOT include detailed implementation plans.** Analysis of found data is part of creating these documents, not a separate document *to create* unless specifically a 'Baseline Assessment'.
    *   For every document identified, include all required fields: `document_name`, `description`, `responsible_role_type` (use specific functional roles where appropriate, mandatory), `document_template_primary` / `document_template_secondary`, `steps_to_create` (key initial steps), `approval_authorities`.

2.  **Documents to Find:** Identify **existing source materials** (datasets, official government documents, existing legislation, statistical databases, etc.) crucial for performing the analysis needed to create the planning documents listed above.
    *   Derive directly from the information needs implied by the 'Documents to Create'.
    *   **CRITICAL INSTRUCTION - FOCUS ON SOURCE MATERIAL:** You MUST list the **raw inputs** needed for analysis, NOT pre-existing reports that *contain* analysis (unless the report *is* the raw data source, like an official statistical publication).
        *   **Think: What raw data or official text does the team need to *look at* to write their strategy/plan?**
        *   **EXAMPLE MAPPING:**
            *   If creating a 'Housing Affordability Improvement Framework', you need to *find* things like: 'National Housing Price Index Data', 'Existing Zoning Regulations', 'Data on Housing Construction Rates', 'Current Government Housing Subsidy Policies'.
            *   If creating a 'Reducing Child-Rearing Costs Strategic Plan', you need to *find* things like: 'Current National Childcare Subsidy Laws/Policies', 'Data on Average Childcare Costs', 'Tax Code Sections Related to Dependents'.
        *   **Explicitly FORBIDDEN:** Do NOT list items like 'Housing Market Analysis Report', 'Childcare Policies Review Report'. The team will *perform* the analysis or review using the source material found; they are not *finding* a completed analysis report (unless it's an official, foundational statistical report from a national office).
    *   **NAMING CONVENTION:** Use names that clearly reflect the raw source material type. Prefer names like:
        *   `[Region/Scope] [Topic] Statistical Data` (e.g., 'Participating Nations Fertility Rate Data')
        *   `Existing [Region/Scope] [Topic] Policies/Laws/Regulations` (e.g., 'Existing National Childcare Subsidy Policies')
        *   `Official [Region/Scope] [Topic] Survey Results/Data` (e.g., 'Official National Mental Health Survey Data')
        *   `[Region/Scope] Economic Indicators` (e.g., 'Participating Nations GDP Data', 'National Housing Price Indices')
    *   Consolidate similar source requirements where logical.
    *   For every source material identified, explicitly and always include **ALL** required fields:
        *   `document_name`: Clear title following the naming convention above (focus on data/policy type).
        *   `description`: Specify the type of source material, its purpose (input for which analysis/plan), intended audience *for analysis*, context.
        *   `recency_requirement`: Specify how recent it must be. **Mandatory field.**
        *   `responsible_role_type`: Role responsible for obtaining/verifying. **Mandatory field.**
        *   `steps_to_find`: Likely steps (e.g., contacting statistical offices, searching government legislative portals, accessing specific databases).
        *   `access_difficulty`: Assess clearly (Easy, Medium, Hard) with brief justification.

**Instructions Recap:**
- Ground analysis in the user prompt.
- "Create" section: High-level plans/strategies & initial PM docs. No implementation plans.
- "Find" section: **EXISTING SOURCE MATERIAL ONLY (Data, Policies, Laws, Stats).** Use specified naming convention. **NO PRE-EXISTING ANALYSIS REPORTS.**
- Ensure ALL mandatory fields (`responsible_role_type` everywhere, `recency_requirement` in Find) are populated.
- Adhere strictly to the Pydantic schema and field definitions.
"""

@dataclass
class IdentifyDocuments:
    """
    Take a look at the project description and identify necessary documents and requirements before the plan can be created.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    cleanedup_document_details: CleanedupDocumentDetails
    json_documents_to_create: list[dict]
    json_documents_to_find: list[dict]
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'IdentifyDocuments':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = IDENTIFY_DOCUMENTS_SYSTEM_PROMPT.strip()

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

        cleanedup_document_details = cls.cleanup(chat_response.raw)
        json_documents_to_create = [doc.model_dump() for doc in cleanedup_document_details.documents_to_create]
        json_documents_to_find = [doc.model_dump() for doc in cleanedup_document_details.documents_to_find]

        markdown = cls.convert_to_markdown(cleanedup_document_details)

        result = IdentifyDocuments(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            cleanedup_document_details=cleanedup_document_details,
            json_documents_to_create=json_documents_to_create,
            json_documents_to_find=json_documents_to_find,
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
    def cleanup(document_details: DocumentDetails) -> CleanedupDocumentDetails:
        """
        Cleanup the document details.
        - Combine part1 and part2.
        - Assign a unique id to each document.
        """
        cleanedup_documents_to_create = []
        documents_to_create = document_details.documents_to_create + document_details.documents_to_create_part2
        for item in documents_to_create:
            document = CleanedupCreateDocumentItem(
                id=str(uuid4()),
                document_name=item.document_name,
                description=item.description,
                responsible_role_type=item.responsible_role_type,
                document_template_primary=item.document_template_primary,
                document_template_secondary=item.document_template_secondary,
                steps_to_create=item.steps_to_create,
                approval_authorities=item.approval_authorities,
            )
            cleanedup_documents_to_create.append(document)

        cleanedup_documents_to_find = []
        documents_to_find = document_details.documents_to_find + document_details.documents_to_find_part2
        for item in documents_to_find:
            document = CleanedupFindDocumentItem(
                id=str(uuid4()),
                document_name=item.document_name,
                description=item.description,
                recency_requirement=item.recency_requirement,
                responsible_role_type=item.responsible_role_type,
                steps_to_find=item.steps_to_find,
                access_difficulty=item.access_difficulty,
            )
            cleanedup_documents_to_find.append(document)

        return CleanedupDocumentDetails(
            documents_to_create=cleanedup_documents_to_create,
            documents_to_find=cleanedup_documents_to_find
        )

    @staticmethod
    def convert_to_markdown(document_details: CleanedupDocumentDetails) -> str:
        """
        Convert the raw document details to markdown.
        """
        rows = []
        
        # Add documents to create section
        rows.append("\n## Documents to Create\n")
        if len(document_details.documents_to_create) > 0:
            for i, item in enumerate(document_details.documents_to_create, start=1):
                if i > 1:
                    rows.append("")
                rows.append(f"### {i}. {item.document_name}")
                rows.append(f"\n**ID:** {item.id}")
                rows.append(f"\n**Description:** {item.description}")
                rows.append(f"\n**Responsible Role Type:** {item.responsible_role_type}")
                if item.document_template_primary:
                    rows.append(f"\n**Primary Template:** {item.document_template_primary}")
                if item.document_template_secondary:
                    rows.append(f"\n**Secondary Template:** {item.document_template_secondary}")
                rows.append("\n**Steps:**\n")
                if item.steps_to_create:
                    for step in item.steps_to_create:
                        rows.append(f"- {step}")
                else:
                    rows.append("- *(No steps provided)*")
                if item.approval_authorities:
                    rows.append(f"\n**Approval Authorities:** {item.approval_authorities}")
        else:
            rows.append("\n*No documents identified to create.*")

        # Add documents to find section
        rows.append("\n## Documents to Find\n")
        if len(document_details.documents_to_find) > 0:
            for i, item in enumerate(document_details.documents_to_find, start=1):
                if i > 1:
                    rows.append("")
                rows.append(f"### {i}. {item.document_name}")
                rows.append(f"\n**ID:** {item.id}")
                rows.append(f"\n**Description:** {item.description}")
                if item.recency_requirement:
                    rows.append(f"\n**Recency Requirement:** {item.recency_requirement}")
                rows.append(f"\n**Responsible Role Type:** {item.responsible_role_type}")
                rows.append(f"\n**Access Difficulty:** {item.access_difficulty}")
                rows.append("\n**Steps:**\n")
                if item.steps_to_find:
                    for step in item.steps_to_find:
                        rows.append(f"- {step}")
                else:
                    rows.append("- *(No steps provided)*")
        else:
            rows.append("\n*No documents identified to find.*")
                
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

    def save_json_documents_to_create(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(json.dumps(self.json_documents_to_create, indent=2))

    def save_json_documents_to_find(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(json.dumps(self.json_documents_to_find, indent=2))

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

    result = IdentifyDocuments.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}") 