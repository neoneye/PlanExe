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
    document_purpose: str = Field(
        description="The purpose of the document and its intended primary audience(s) (e.g., 'To formally authorize the project and define high-level objectives for the Project Sponsor and Senior Management.')."
    )
    responsible_role_type: Optional[str] = Field(
        default=None,
        description="The typical functional role or primary skill type needed to create or lead the creation of this document (e.g., 'Project Manager', 'Finance Team Lead', 'Legal Counsel', 'Environmental Scientist', 'Lead Engineer'). Suggest a role type, not a specific person."
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

class FindDocumentItem(BaseModel):
    """A document that is to be found online or in a physical location, such as existing data, reports, contracts, permits, etc."""
    document_name: str = Field(
        description="The specific name or type of document/data to be found (e.g., 'Participating Nations GDP Data', 'Existing Childcare Support Program Reports', 'Local Zoning Regulations', 'Grid Connection Capacity Study')."
    )
    document_purpose: str = Field(
        description="Why this document/data is needed for planning and its intended audience(s) (e.g., 'To determine funding contributions for Finance Team and Project Sponsor.', 'To inform the Financial Burden Reduction Plan for the Program Team.')."
    )
    recency_requirement: Optional[str] = Field(
        default=None,
        description="Guidance on how recent the document or data should ideally be, based on its type and purpose (e.g., 'Most recent available year', 'Published within last 2 years', 'Historical data acceptable', 'Current regulations essential')."
    )
    responsible_role_type: Optional[str] = Field(
        default=None,
        description="The typical functional role or primary skill type responsible for finding, requesting, or verifying this document/data (e.g., 'Research Analyst', 'Financial Analyst', 'Regulatory Liaison', 'Legal Assistant', 'Permitting Specialist'). Suggest a role type."
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
    document_purpose: str
    responsible_role_type: Optional[str]
    document_template_primary: Optional[str]
    document_template_secondary: Optional[str]
    steps_to_create: list[str]

class CleanedupFindDocumentItem(BaseModel):
    id: str
    document_name: str
    document_purpose: str
    recency_requirement: Optional[str]
    responsible_role_type: Optional[str]
    steps_to_find: list[str]
    access_difficulty: str

class CleanedupDocumentDetails(BaseModel):
    documents_to_create: list[CleanedupCreateDocumentItem]
    documents_to_find: list[CleanedupFindDocumentItem]

IDENTIFY_DOCUMENTS_SYSTEM_PROMPT = """
You are an expert in project planning and documentation. Your task is to analyze the provided project description and identify the necessary documents (both to create and to find) that are essential *before* a comprehensive operational plan can be effectively developed.

Based *only* on the **project description provided by the user**, generate the following details:

1.  **Documents to Create:** Identify specific documents that must be drafted or created as part of the planning phase.
    *   Include documents directly implied by the project description (e.g., specific reports, plans mentioned).
    *   Also include standard project management documents typically required for a project of this nature and scale (e.g., Project Charter, Risk Register, Stakeholder Communication Plan, Change Management Plan, Detailed Budget, Detailed Schedule, M&E Framework), ensuring they are relevant to the context provided.
    *   For each document, provide:
        *   `document_name`
        *   `document_purpose` (including audience)
        *   `responsible_role_type`: Infer the typical functional role or primary skill type (e.g., 'Project Manager', 'Financial Analyst', 'Legal Counsel') needed to lead the creation.
        *   `document_template_primary` / `document_template_secondary`: Suggest standard template names or sources (e.g., 'PMI', 'World Bank') if widely applicable. **If suggesting a generic template, explicitly note that country-specific or industry-specific versions may be required and should be checked.** If no standard template is common, state 'None Applicable' or leave null.
        *   `steps_to_create`: High-level steps, mentioning key inputs or approvals.

2.  **Documents to Find:** Identify specific existing documents, data sets, or information that must be obtained or located to inform the planning process.
    *   Infer these from the project description's requirements (e.g., needing funding implies finding GDP data, needing specific regulations implies finding legal texts).
    *   **Consolidate similar data requirements** (e.g., list 'National GDP Data' once, even if needed for multiple purposes or nations, rather than repeating).
    *   For each document/data set, provide:
        *   `document_name`
        *   `document_purpose` (including audience)
        *   `recency_requirement`: Infer guidance on how recent the information should ideally be (e.g., 'Most recent available', 'Last 2 years').
        *   `responsible_role_type`: Infer the typical functional role or skill type (e.g., 'Research Analyst', 'Regulatory Liaison') responsible for finding/verifying it.
        *   `steps_to_find`
        *   `access_difficulty`: Assess as Easy/Medium/Hard with brief justification.

**Instructions:**
- Ground your analysis firmly in the **user's project description**. Do not invent details or requirements not supported by the input.
- When suggesting standard PM documents, briefly tailor their purpose to the specific project context.
- When inferring roles, suggest a functional type (e.g., 'Legal', 'Technical', 'Finance') rather than a specific job title if appropriate.
- Focus *only* on identifying these necessary prerequisite documents/data. Do not generate implementation plans, execution strategies, or other topics.
- Ensure all specified fields (`document_name`, `document_purpose`, `responsible_role_type`, `recency_requirement`, `steps_to_find`, `access_difficulty`, `document_template_primary`, `document_template_secondary`, `steps_to_create`) are populated for every item where applicable.
- Ensure your output strictly adheres to the provided Pydantic schema `DocumentDetails` containing only `documents_to_create` and `documents_to_find`.
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

        markdown = cls.convert_to_markdown(cleanedup_document_details)

        result = IdentifyDocuments(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            cleanedup_document_details=cleanedup_document_details,
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
                document_purpose=item.document_purpose,
                responsible_role_type=item.responsible_role_type,
                document_template_primary=item.document_template_primary,
                document_template_secondary=item.document_template_secondary,
                steps_to_create=item.steps_to_create,
            )
            cleanedup_documents_to_create.append(document)

        cleanedup_documents_to_find = []
        documents_to_find = document_details.documents_to_find + document_details.documents_to_find_part2
        for item in documents_to_find:
            document = CleanedupFindDocumentItem(
                id=str(uuid4()),
                document_name=item.document_name,
                document_purpose=item.document_purpose,
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
                rows.append(f"### {i}. {item.document_name}, ID: {item.id}")
                rows.append(f"**Purpose:** {item.document_purpose}")
                if item.responsible_role_type:
                    rows.append(f"**Responsible Role Type:** {item.responsible_role_type}")
                if item.document_template_primary:
                    rows.append(f"**Primary Template:** {item.document_template_primary}")
                if item.document_template_secondary:
                    rows.append(f"**Secondary Template:** {item.document_template_secondary}")
                rows.append("**Steps:**\n")
                if item.steps_to_create:
                    for step in item.steps_to_create:
                        rows.append(f"- {step}")
                else:
                    rows.append("- *(No steps provided)*")            
        else:
            rows.append("*No documents identified to create.*")

        # Add documents to find section
        rows.append("\n## Documents to Find\n")
        if len(document_details.documents_to_find) > 0:
            for i, item in enumerate(document_details.documents_to_find, start=1):
                if i > 1:
                    rows.append("")
                rows.append(f"### {i}. {item.document_name}, ID: {item.id}")
                rows.append(f"**Purpose:** {item.document_purpose}")
                if item.recency_requirement:
                    rows.append(f"**Recency Requirement:** {item.recency_requirement}")
                if item.responsible_role_type:
                    rows.append(f"**Responsible Role Type:** {item.responsible_role_type}")
                rows.append(f"**Access Difficulty:** {item.access_difficulty}")
                rows.append("**Steps:**\n")
                if item.steps_to_find:
                    for step in item.steps_to_find:
                        rows.append(f"- {step}")
                else:
                    rows.append("- *(No steps provided)*")
        else:
            rows.append("*No documents identified to find.*")
                
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

    result = IdentifyDocuments.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}") 