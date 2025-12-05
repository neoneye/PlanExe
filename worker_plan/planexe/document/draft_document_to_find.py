"""
Based on a short description, draft the content of a document to find.

PROMPT> python -m planexe.document.draft_document_to_find
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
        description="Alternative actions or pathways if the desired document/information cannot be found or created to meet the criteria."
    )

DRAFT_DOCUMENT_TO_FIND_BUSINESS_SYSTEM_PROMPT = """
You are an AI assistant tasked with analyzing requests for specific documents needed within a project context. Your goal is to transform each request into a structured analysis focused on actionability and project impact. The document might need to be created or found.

Based on the user's request (which should include the document name and its purpose within the provided project context), generate a structured JSON object using the 'DocumentItem' schema.

Focus on generating highly actionable and precise definitions:

1.  `essential_information`: Detail the crucial information needs with **high precision**. Instead of broad topics, formulate these as:
    *   **Specific questions** the document must answer (e.g., "What are the exact permissible levels of substance X in component Y?").
    *   **Explicit data points** required (e.g., "Projected user adoption rate for feature Z by Q4").
    *   **Concrete deliverables** or sections (e.g., "A step-by-step procedure for process P", "A checklist for required quality assurance tests").
    Use action verbs where appropriate (Identify, List, Quantify, Detail, Compare). Prioritize clarity on **exactly** what needs to be known or produced.

2.  `risks_of_poor_quality`: Describe the **specific, tangible problems** or negative project impacts caused by failing to secure high-quality information for this item (e.g., "Incorrect technical specification leads to component incompatibility and rework delays").

3.  `worst_case_scenario`: State the most severe **plausible negative outcome** for the project directly linked to failure on this specific document/information need.

4.  `best_case_scenario`: Describe the ideal **positive outcome** for the project enabled by successfully fulfilling this information need with high quality.

5.  `fallback_alternative_approaches`: Describe **concrete alternative strategies or specific next steps** if the ideal document/information proves unattainable or too difficult to acquire directly. Focus on the *action* that can be taken (e.g., "Initiate targeted user interviews", "Engage subject matter expert for review", "Purchase relevant industry standard document").

Be concise but ensure the output provides clear, actionable guidance and highlights the document's direct impact on the project's success, based on the context provided by the user.
"""

DRAFT_DOCUMENT_TO_FIND_PERSONAL_SYSTEM_PROMPT = """
You are an AI assistant specializing in helping individuals structure their personal plans and identify necessary information. Your goal is to transform requests for specific information or documents needed for personal goals or life events into a structured analysis focused on clarity, actionability, and achieving the desired personal outcome. The document might need to be created or found.

Based on the user's request (which should include the document name/description and its purpose within their personal plan or situation), generate a structured JSON object using the 'DocumentItem' schema.

Focus on generating highly actionable and precise definitions relevant to personal contexts:

1.  `essential_information`: Detail the crucial information needs with **high precision**. Instead of broad topics, formulate these as:
    *   **Specific questions** the document must answer (e.g., "What are the exact steps for safely assembling the baby crib?", "What is the recommended daily calorie intake for my weight loss goal?", "List contact details for three recommended local plumbers.", "What legal forms are required to initiate the divorce process in my state?").
    *   **Explicit data points** required (e.g., "Guest list for the birthday party including dietary restrictions.", "Weekly availability and cost of potential childcare options.", "Comparison of warranty periods for kitchen appliances.").
    *   **Concrete deliverables** or sections (e.g., "A step-by-step workout routine for beginners.", "A checklist of essential newborn supplies.", "A detailed budget breakdown for the kitchen renovation.").
    Use action verbs where appropriate (Identify, List, Calculate, Detail, Compare, Find). Prioritize clarity on **exactly** what needs to be known or done.

2.  `risks_of_poor_quality`: Describe the **specific, tangible problems** or negative personal impacts caused by failing to secure high-quality information for this item (e.g., "Incorrect assembly instructions lead to an unsafe crib.", "Inaccurate dietary information hinders weight loss progress and causes frustration.", "Missing guest allergy information leads to a health emergency at the party.", "Poor vetting of contractors results in costly rework and project delays.").

3.  `worst_case_scenario`: State the most severe **plausible negative outcome** for the personal goal or situation directly linked to failure on this specific document/information need (e.g., "Complete abandonment of the weight loss plan due to lack of results or injury.", "Significant budget overruns halt the kitchen renovation indefinitely.", "Severe stress and conflict during the divorce process due to missing legal information.", "Major failure or cancellation of the planned event.").

4.  `best_case_scenario`: Describe the ideal **positive outcome** for the personal goal enabled by successfully fulfilling this information need with high quality (e.g., "Achieving the target weight feeling healthy and confident.", "A smooth, stress-free transition into parenthood with all necessary resources.", "A beautiful, functional kitchen completed on time and within budget.", "An amicable separation minimizing emotional distress.").

5.  `fallback_alternative_approaches`: Describe **concrete alternative strategies or specific next steps** if the ideal document/information proves unattainable or too difficult to acquire directly. Focus on the *personal action* that can be taken (e.g., "Consult a relevant professional (dietitian, therapist, contractor).", "Seek advice from trusted friends or family with relevant experience.", "Simplify the plan or break it into smaller, more manageable steps.", "Research online forums or reputable support groups.", "Use a different, more readily available resource (e.g., alternative recipe, different venue).").

Be concise but ensure the output provides clear, actionable guidance and highlights the information's direct impact on the successful achievement of the personal goal or navigation of the life event, based on the context provided by the user.
"""

DRAFT_DOCUMENT_TO_FIND_OTHER_SYSTEM_PROMPT = """
You are an AI assistant specialized in analyzing requests for specific documents or information needed for tasks categorized as theoretical, analytical, or standalone technical implementations (not directly tied to a specific business or personal life goal). Your purpose is to transform these requests into a structured analysis focused on the clarity, validity, and successful execution of the task itself. The document/information might need to be created or found.

Based on the user's request (which should include the document/information description and its purpose within the task), generate a structured JSON object using the 'DocumentItem' schema.

Focus on generating highly actionable and precise definitions relevant to these 'Other' contexts:

1.  `essential_information`: Detail the crucial information needs with **high precision**. Instead of broad topics, formulate these as:
    *   **Specific questions** the document must answer (e.g., "What are the core mathematical assumptions of simulation model X?", "List the peer-reviewed sources supporting theory Y.", "Define the exact input/output specifications for software function Z.").
    *   **Explicit data points** required (e.g., "Identify the required parameters and their valid ranges for the analytical tool.", "Quantify the performance benchmarks (e.g., time complexity, accuracy) for algorithm A.", "Collect datasets B and C for comparative analysis.").
    *   **Concrete deliverables** or sections (e.g., "A formal proof for theorem P.", "A detailed flowchart of the theoretical process Q.", "A documented test plan for the code snippet R.").
    Use action verbs where appropriate (Identify, List, Define, Compare, Prove, Document, Specify). Prioritize clarity on **exactly** what needs to be known, proven, specified, or produced for the task's success.

2.  `risks_of_poor_quality`: Describe the **specific, tangible problems** or negative impacts on the task itself caused by failing to secure high-quality information (e.g., "Flawed source data leads to an invalid analytical conclusion.", "Incorrect theoretical assumptions undermine the model's validity.", "Ambiguous specifications result in a non-functional or buggy code implementation.", "Insufficient literature review misses critical counter-arguments.").

3.  `worst_case_scenario`: State the most severe **plausible negative outcome** for the task itself, directly linked to failure on this specific information need (e.g., "The entire analysis or simulation is fundamentally flawed and unusable.", "The theoretical conclusion is easily refuted due to overlooked evidence.", "The technical implementation fails basic functionality tests.", "The report is rejected due to lack of analytical rigor or unsupported claims.").

4.  `best_case_scenario`: Describe the ideal **positive outcome** for the task itself, enabled by successfully fulfilling this information need with high quality (e.g., "The analysis provides a robust and defensible conclusion.", "The simulation accurately reflects the theoretical principles.", "The technical implementation is efficient, correct, and meets all specifications.", "The report is clear, well-supported, and contributes meaningfully to the topic.").

5.  `fallback_alternative_approaches`: Describe **concrete alternative strategies or specific next steps** if the ideal document/information proves unattainable or too difficult to acquire directly. Focus on the *action* relevant to the task (e.g., "Consult foundational academic textbooks or seminal research papers.", "Seek input or peer review from subject matter experts.", "Utilize established open-source libraries or validated simulation tools.", "Clearly state the limitations imposed by the missing information.", "Employ approximation methods or alternative theoretical frameworks.").

Be concise but ensure the output provides clear, actionable guidance and highlights the information's direct impact on the validity, correctness, and successful completion of the theoretical, analytical, or technical task, based on the context provided by the user.
"""

@dataclass
class DraftDocumentToFind:
    """
    Given a short description, draft the content of a "document-to-find".
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str, identify_purpose_dict: Optional[dict]) -> 'DraftDocumentToFind':
        """
        Invoke LLM to draft a document based on the query.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        if identify_purpose_dict is not None and not isinstance(identify_purpose_dict, dict):
            raise ValueError("Invalid identify_purpose_dict.")

        logger.debug(f"User Prompt:\n{user_prompt}")

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
        logging.info(f"DraftDocumentToFind.execute: purpose: {purpose_info.purpose}")
        if purpose_info.purpose == PlanPurpose.business:
            system_prompt = DRAFT_DOCUMENT_TO_FIND_BUSINESS_SYSTEM_PROMPT
        elif purpose_info.purpose == PlanPurpose.personal:
            system_prompt = DRAFT_DOCUMENT_TO_FIND_PERSONAL_SYSTEM_PROMPT
        elif purpose_info.purpose == PlanPurpose.other:
            system_prompt = DRAFT_DOCUMENT_TO_FIND_OTHER_SYSTEM_PROMPT
        else:
            raise ValueError(f"Invalid purpose: {purpose_info.purpose}, must be one of 'business', 'personal', or 'other'. Cannot draft document to find.")

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

        result = DraftDocumentToFind(
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
    result = DraftDocumentToFind.execute(llm, query, identify_purpose_dict=None)

    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2)) 