"""
Based on a short description, draft the content of a document to find.

PROMPT> python -m src.plan.draft_document_to_find
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

DRAFT_DOCUMENT_TO_FIND_SYSTEM_PROMPT = """
You are an AI assistant for the PlanExe planning system. Your task is to analyze a request for a specific document needed for a project. This document might need to be created or found.

Based on the user's request (which should include the document name and its purpose), generate a structured JSON object using the 'DocumentItem' schema.

Focus on clearly defining:
1. `essential_information`: What critical content, data, or answers MUST be in the document.
2. `risks_of_poor_quality`: The specific problems caused by a bad version of this document.
3. `worst_case_scenario`: The most severe potential negative outcome related to this document.
4. `best_case_scenario`: The ideal positive outcome enabled by a good version of this document.
5. `fallback_alternative_approaches`: What to do if the ideal document/information isn't attainable.

Be concise and focus on the document's role and impact within the project context provided by the user.
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
    def execute(cls, llm: LLM, user_prompt: str) -> 'DraftDocumentToFind':
        """
        Invoke LLM to draft a document based on the query.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        system_prompt = DRAFT_DOCUMENT_TO_FIND_SYSTEM_PROMPT.strip()

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
    from src.llm_factory import get_llm
    from src.prompt.prompt_catalog import PromptCatalog
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
    result = DraftDocumentToFind.execute(llm, query)

    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2)) 