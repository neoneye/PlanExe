"""
Based on a short description, draft the content of a document to create.

PROMPT> python -m planexe.document.draft_document_to_create
"""
import json
import time
import logging
from math import ceil
from typing import Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from planexe.assume.identify_purpose import IdentifyPurpose, PlanPurposeInfo, PlanPurpose

logger = logging.getLogger(__name__)

class DocumentItem(BaseModel):
    essential_information: list[str] = Field(
        description="Bullet points describing the crucial information, key points, sections, data, or answers this document must provide."
    )
    risks_of_poor_quality: list[str] = Field(
        description="Specific negative consequences or project impacts if the document is incomplete, inaccurate, outdated, unclear, or misleading."
    )
    worst_case_scenario: str = Field(
        description="The most severe potential consequence or project risk (e.g., compliance failure, financial loss, major delays, misinformation) if the document is deficient or incorrect."
    )
    best_case_scenario: str = Field(
        description="The ideal outcome or positive impact if the document fully meets or exceeds expectations (e.g., accelerated decisions, reduced risk, competitive advantage)."
    )
    fallback_alternative_approaches: list[str] = Field(
        description="Alternative actions or pathways if the desired document/information cannot be created to meet the criteria."
    )

DRAFT_DOCUMENT_TO_CREATE_BUSINESS_SYSTEM_PROMPT = """
You are an AI assistant tasked with analyzing requests for specific documents that need to be **created** within a project context. Your goal is to transform each request into a structured analysis focused on actionability, necessary inputs, decision enablement, and project impact.

Based on the user's request (which should include the document name and its purpose within the provided project context), generate a structured JSON object using the 'DocumentItem' schema.

Focus on generating highly actionable and precise definitions:

1.  `essential_information`: Detail the crucial information needs with **high precision**. Instead of broad topics, formulate these as:
    *   **Specific questions** the document must answer (e.g., "What are the key performance indicators for process X?").
    *   **Explicit data points** or analysis required (e.g., "Calculate the projected ROI based on inputs A, B, C").
    *   **Concrete deliverables** or sections (e.g., "A section detailing stakeholder roles and responsibilities", "A risk mitigation plan for the top 5 identified risks").
    *   **Necessary inputs or potential sources** required to create the content (e.g., "Requires access to sales data from Q1", "Based on interviews with the engineering team", "Utilizes findings from the Market Demand Data document").
    Use action verbs where appropriate (Identify, List, Quantify, Detail, Compare, Analyze, Define). Prioritize clarity on **exactly** what needs to be known, produced, or decided based on this document.

2.  `risks_of_poor_quality`: Describe the **specific, tangible problems** or negative project impacts caused by failing to **create** a high-quality document (e.g., "An unclear scope definition leads to significant rework and budget overruns", "Inaccurate financial assessment prevents securing necessary funding").

3.  `worst_case_scenario`: State the most severe **plausible negative outcome** for the project directly linked to failure in **creating** or effectively using this document.

4.  `best_case_scenario`: Describe the ideal **positive outcome** and **key decisions directly enabled** by successfully creating this document with high quality (e.g., "Enables go/no-go decision on Phase 2 funding", "Provides clear requirements for the development team, reducing ambiguity").

5.  `fallback_alternative_approaches`: Describe **concrete alternative strategies for the creation process** or specific next steps if creating the ideal document proves too difficult, slow, or resource-intensive. Focus on the *action* that can be taken regarding the creation itself (e.g., "Utilize a pre-approved company template and adapt it", "Schedule a focused workshop with stakeholders to define requirements collaboratively", "Engage a technical writer or subject matter expert for assistance", "Develop a simplified 'minimum viable document' covering only critical elements initially").

Be concise but ensure the output provides clear, actionable guidance for the creator, highlights necessary inputs, and clarifies the document's role in decision-making and project success, based on the context provided by the user.
"""

DRAFT_DOCUMENT_TO_CREATE_PERSONAL_SYSTEM_PROMPT = """
You are an AI assistant specializing in helping individuals structure their personal plans and identify necessary documents that need to be **created**. Your goal is to transform requests for specific documents needed for personal goals or life events into a structured analysis focused on clarity, actionability, necessary inputs, enabling personal decisions, and achieving the desired personal outcome.

Based on the user's request (which should include the document name/description and its purpose within their personal plan or situation), generate a structured JSON object using the 'DocumentItem' schema.

Focus on generating highly actionable and precise definitions relevant to personal contexts:

1.  `essential_information`: Detail the crucial information needs with **high precision**. Instead of broad topics, formulate these as:
    *   **Specific questions** the document must answer (e.g., "What specific meals align with my dietary goals for the next week?", "What are the key steps and timeline for baby-proofing the living room?", "List the pros and cons of countertop materials A vs. B.", "What is the final guest list and seating arrangement for the party?", "What are the primary points to discuss during the initial separation conversation?").
    *   **Explicit data points** or analysis required (e.g., "Calculate estimated weekly grocery cost for the meal plan.", "Compare the safety ratings and features of different car seats.", "Itemize the projected costs for each phase of the kitchen renovation.", "Detail the schedule of activities for the birthday party.", "List shared financial assets and liabilities.").
    *   **Concrete deliverables** or sections (e.g., "A daily exercise schedule.", "A contact list for emergency childcare.", "A mood board showing desired kitchen aesthetics.", "A shopping list for party supplies.", "A summary of personal goals for the next year post-separation.").
    *   **Necessary inputs or potential sources** required to create the content (e.g., "Requires review of personal health goals and dietary restrictions.", "Based on information from parenting websites and safety checklists.", "Utilizes quotes gathered from contractors and material suppliers.", "Depends on finalized RSVPs and venue layout.", "Informed by personal reflection and journaling.").
    Use action verbs where appropriate (Identify, List, Calculate, Detail, Compare, Outline, Plan, Reflect). Prioritize clarity on **exactly** what needs to be known, produced, or decided based on this document.

2.  `risks_of_poor_quality`: Describe the **specific, tangible problems** or negative personal impacts caused by failing to **create** a high-quality document (e.g., "An unclear meal plan leads to abandoning the diet.", "A poorly researched baby supply list results in missing essential items during a critical time.", "An incomplete renovation plan causes significant delays and unexpected costs.", "A confusing party schedule leads to guest frustration and missed activities.", "A poorly thought-out separation plan increases emotional distress and conflict.").

3.  `worst_case_scenario`: State the most severe **plausible negative outcome** for the personal goal or situation directly linked to failure in **creating** or effectively using this document (e.g., "Complete failure to achieve the weight loss goal, leading to disappointment and health setbacks.", "Overwhelming stress and inability to cope during the newborn phase due to lack of preparation.", "Halting the kitchen renovation mid-project due to budget mismanagement.", "Major event failure causing embarrassment and strained relationships.", "Escalation of conflict and significant financial hardship during separation.").

4.  `best_case_scenario`: Describe the ideal **positive outcome** and **key personal decisions directly enabled** by successfully creating this document with high quality (e.g., "Enables consistent adherence to the fitness plan, leading to goal achievement.", "Provides a clear roadmap for newborn care, increasing confidence.", "Allows for informed decisions on kitchen layout and materials, resulting in the desired outcome within budget.", "Ensures the party runs smoothly, creating positive memories.", "Facilitates a clearer, calmer approach to navigating the relationship change.").

5.  `fallback_alternative_approaches`: Describe **concrete alternative strategies for the creation process** or specific next steps if creating the ideal document proves too difficult, slow, or resource-intensive. Focus on the *personal action* that can be taken regarding the creation itself (e.g., "Use a template found online (e.g., meal planner, baby checklist, budget template).", "Discuss the plan structure with a trusted friend, family member, or mentor.", "Consult a relevant professional for guidance on specific sections (e.g., nutritionist, contractor, event planner, therapist).", "Create a simpler version focusing only on the absolute essential elements.", "Break the document creation into smaller, more manageable tasks over time.").

Be concise but ensure the output provides clear, actionable guidance for the creator, highlights necessary inputs, and clarifies the document's role in personal decision-making and achieving personal goals or navigating life events, based on the context provided by the user.
"""

DRAFT_DOCUMENT_TO_CREATE_OTHER_SYSTEM_PROMPT = """
You are an AI assistant specialized in analyzing requests for specific documents that need to be **created** for tasks categorized as theoretical, analytical, or standalone technical implementations (not directly tied to a specific business or personal life goal). Your purpose is to transform these requests into a structured analysis focused on the necessary content, potential pitfalls in creation, the impact of the created document on the task's validity and success, and alternative creation methods.

Based on the user's request (which should include the document name/description and its purpose within the task), generate a structured JSON object using the 'DocumentItem' schema.

Focus on generating highly actionable and precise definitions relevant to these 'Other' contexts:

1.  `essential_information`: Detail the crucial information, structure, and analysis that the **created document** must contain with **high precision**. Instead of broad topics, formulate these as:
    *   **Specific questions** the document's content must answer (e.g., "What is the logical flow of the mathematical proof?", "How is the simulation model validated against known benchmarks?", "What specific data structures and algorithms will be used in the implementation?").
    *   **Explicit data points** or analysis required *within the document* (e.g., "Include a section comparing the performance results of algorithm A vs. B.", "Detail the error analysis for the numerical method used.", "Present the derived theoretical equations in standard notation.").
    *   **Concrete deliverables** or sections required *in the document* (e.g., "A clearly defined 'Methodology' section.", "A 'System Architecture Diagram' for the technical design.", "An 'Assumptions and Limitations' section for the analysis.").
    *   **Necessary inputs or potential sources** required *to create the document's content* (e.g., "Requires results from previously run simulations.", "Based on theorems X, Y, and Z.", "Utilizes data from dataset P.", "Input from technical requirements specification Q.").
    Use action verbs where appropriate (Define, Specify, Analyze, Prove, Document, Structure, Validate, Compare). Prioritize clarity on **exactly** what needs to be written, calculated, diagrammed, or proven *within this specific document*.

2.  `risks_of_poor_quality`: Describe the **specific, tangible problems** or negative impacts on the task itself caused by failing to **create** a high-quality document (e.g., "An illogical structure makes the theoretical argument impossible to follow or verify.", "Omitting the methodology section prevents others from reproducing the analysis.", "Ambiguous definitions in the specification lead to incorrect or incompatible code implementation.", "Failure to document limitations results in misapplication of the findings/tool.").

3.  `worst_case_scenario`: State the most severe **plausible negative outcome** for the task itself, directly linked to failure in **creating** or effectively structuring this document (e.g., "The entire research finding presented in the paper is dismissed due to poor structure and undocumented methods.", "The simulation plan is unexecutable because critical parameters weren't defined in the document.", "The developed code fails integration tests because the design document was flawed or incomplete.").

4.  `best_case_scenario`: Describe the ideal **positive outcome** and **key task advancements or validations directly enabled** by successfully **creating** this document with high quality (e.g., "Provides a clear, rigorous, and easily verifiable presentation of the theoretical results.", "Enables efficient and accurate implementation based on well-defined specifications.", "Allows for successful peer review and validation of the analytical methods used.", "Serves as a definitive reference for the technical design or analytical approach.").

5.  `fallback_alternative_approaches`: Describe **concrete alternative strategies for the document creation process** or specific next steps if creating the ideal document proves too difficult, slow, or resource-intensive. Focus on the *action* that can be taken regarding the creation itself (e.g., "Utilize a standard academic paper structure (IMRaD).", "Adopt a widely accepted technical documentation template (e.g., RFC structure, API documentation standards).", "Create a detailed outline or flowchart first to structure the content before writing.", "Develop a minimal viable document containing only the absolute core specifications/findings initially.", "Collaborate with a peer or mentor to review the document structure and clarity during creation.").

Be concise but ensure the output provides clear, actionable guidance for the **creator** of the document, highlights necessary inputs for content generation, and clarifies the created document's role in ensuring the validity, reproducibility, and success of the theoretical, analytical, or technical task, based on the context provided by the user.
"""

@dataclass
class DraftDocumentToCreate:
    """
    Given a short description, draft the content of a "document-to-create".
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str, identify_purpose_dict: Optional[dict]) -> 'DraftDocumentToCreate':
        """
        Invoke LLM to draft a document based on the query.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        if identify_purpose_dict is not None and not isinstance(identify_purpose_dict, dict):
            raise ValueError("Invalid identify_purpose_dict.")

        if identify_purpose_dict is None:
            logging.info("No identify_purpose_dict provided, identifying purpose.")
            identify_purpose = IdentifyPurpose.execute(llm, user_prompt)
            identify_purpose_dict = identify_purpose.to_dict()
        else:
            logging.info("identify_purpose_dict provided, using it.")

        # Parse the identify_purpose_dict
        logging.debug(f"IdentifyPurpose json {json.dumps(identify_purpose_dict, indent=2)}")
        try:
            purpose_info = PlanPurposeInfo(**identify_purpose_dict)
        except Exception as e:
            logging.error(f"Error parsing identify_purpose_dict: {e}")
            raise ValueError("Error parsing identify_purpose_dict.") from e

        # Select the appropriate system prompt based on the purpose
        logging.info(f"DraftDocumentToCreate.execute: purpose: {purpose_info.purpose}")
        if purpose_info.purpose == PlanPurpose.business:
            system_prompt = DRAFT_DOCUMENT_TO_CREATE_BUSINESS_SYSTEM_PROMPT
        elif purpose_info.purpose == PlanPurpose.personal:
            system_prompt = DRAFT_DOCUMENT_TO_CREATE_PERSONAL_SYSTEM_PROMPT
        elif purpose_info.purpose == PlanPurpose.other:
            system_prompt = DRAFT_DOCUMENT_TO_CREATE_OTHER_SYSTEM_PROMPT
        else:
            raise ValueError(f"Invalid purpose: {purpose_info.purpose}, must be one of 'business', 'personal', or 'other'. Cannot draft document to create.")

        system_prompt = system_prompt.strip()

        chat_message_list = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt
            )
        ]

        start_time = time.perf_counter()

        sllm = llm.as_structured_llm(DocumentItem)
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.error(f"DocumentItem failed to chat with LLM: {e}")
            raise ValueError(f"Failed to chat with LLM: {e}")
        json_response = json.loads(chat_response.message.content)

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration

        result = DraftDocumentToCreate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata
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

if __name__ == "__main__":
    from planexe.llm_factory import get_llm
    from planexe.prompt.prompt_catalog import PromptCatalog
    import os

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    prompt_catalog = PromptCatalog()
    prompt_catalog.load(os.path.join(os.path.dirname(__file__), '..', 'fiction', 'data', 'simple_fiction_prompts.jsonl'))
    prompt_item = prompt_catalog.find("0e8e9b9d-95dd-4632-b47c-dcc4625a556d")

    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    llm = get_llm("ollama-llama3.1")

    print(f"\n\nQuery: {query}")
    result = DraftDocumentToCreate.execute(llm, query, identify_purpose_dict=None)

    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2)) 