"""
Filter documents by identifying duplicates and irrelevant documents.

This module analyzes document lists to identify:
- Duplicate documents (near identical or similar documents)
- Irrelevant documents (documents that don't align with project goals)
- Documents that can be consolidated

The result is a cleaner, more focused list of essential documents.

PROMPT> python -m src.plan.filter_documents_to_find
"""
import os
import json
import time
import logging
from math import ceil
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class KeepRemove(str, Enum):
    """Enum to indicate whether a document should be kept or removed."""
    keep = 'keep'
    remove = 'remove'

class DocumentItem(BaseModel):
    id: int = Field(
        description="The ID of the document being evaluated."
    )
    rationale: str = Field(
        description="The reason for the keep/remove decision."
    )
    keep_remove: KeepRemove = Field(
        description="Whether the document should be kept or removed."
    )

class DocumentEnrichmentResult(BaseModel):
    """The result of enriching a list of documents."""
    document_list: List[DocumentItem] = Field(
        description="List of documents with the decision to keep or remove."
    )
    summary: str = Field(
        description="A summary of the enrichment decisions."
    )

FILTER_DOCUMENTS_TO_FIND_SYSTEM_PROMPT = """
You are an expert AI assistant for project planning documentation. Your task is to analyze a list of potential documents (from user input) against a provided project plan (also from user input). Evaluate each document for the *initial planning phase* ONLY. The initial phase typically involves defining the core business model, assessing high-level feasibility (including major risks and market context), understanding primary compliance categories (like basic EU-level requirements), and securing initial resources, *before* detailed operational planning, country-specific implementation, or in-depth logistics setup begins. Determine if each document should be kept or removed based on relevance, duplication, and timeliness *relative to the project plan*.

**CRITICAL OUTPUT REQUIREMENTS:**
- Respond with a JSON object matching the `DocumentEnrichmentResult` schema.
- The `keep_remove` field must be 'keep' or 'remove'.
- The `rationale` field **MUST BE AN EXPLANATORY SENTENCE OR TWO**.

**ABSOLUTELY FORBIDDEN RATIONALES:**
- Single words: 'keep', 'remove', 'relevant', 'irrelevant', 'duplicate'.
- Short phrases: 'remove due to irrelevance', 'remove due to duplication', 'keep for relevance'.
- **Any rationale that does not explain *WHY* based on the project plan is INCORRECT.**

**HOW TO WRITE THE RATIONALE (MANDATORY):**
1.  State the decision implicitly or explicitly.
2.  **Connect the decision DIRECTLY to a specific aspect, goal, requirement, or phase mentioned in the USER-PROVIDED PROJECT PLAN.**
3.  If removing for duplication or significant overlap, clearly state **WHICH other document ID** it duplicates/overlaps with and why keeping both is redundant for the *initial phase needs*.

**EXAMPLES OF CORRECT RATIONALES (Use this style):**
- **Keep Example:** "Keep: This document provides the specific [XYZ regulations] required for the compliance checks outlined in the project plan's initial phase."
- **Keep Example:** "Keep: Essential market statistics needed to perform the market analysis task defined in the project plan's initial feasibility assessment."
- **Remove (Irrelevant) Example:** "Remove: Details operational procedures for year 2, which is outside the scope of the defined initial planning phase focused on business model and feasibility."
- **Remove (Irrelevant) Example:** "Remove: Focuses on [Unrelated Topic], which is not mentioned as a requirement or goal in the provided project plan for the initial stage."
- **Remove (Duplicate) Example:** "Remove: Duplicates the core compliance information found in document ID [Number]. Keeping both is redundant for the initial assessment needed by the plan."
- **Remove (Duplicate) Example:** "Remove: Provides similar market trend overview as ID [Number]; ID [Number] is sufficient for the high-level market context analysis required by the plan's initial phase."

**Document Evaluation Criteria (Use these to inform your rationale):**
1.  **Relevance to Plan:** Does it directly support a task/goal in the *provided plan's initial phase*?
2.  **Uniqueness:** Does it offer unique info not in other listed docs relevant to the initial phase?
3.  **Duplication:** Is it functionally identical or does it have significant content overlap with another listed doc, making one redundant for the *initial phase needs*?
4.  **Timeliness for Plan:** Is it needed for the *initial phase* described in the plan, or specifically for later stages?

**Final Output:**
Produce a single JSON object containing `document_list` (with **detailed, compliant rationales**) and a `summary`. The summary should briefly recap the decisions and **mention any potential consolidations** for similar documents (even if both were kept initially). Strictly adhere to the `DocumentEnrichmentResult` schema and the rationale instructions above.
"""

@dataclass
class FilterDocumentsToFind:
    """
    Analyzes document lists to identify duplicates and irrelevant documents.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    enrichment_result: DocumentEnrichmentResult
    metadata: dict
    markdown: str
    ids_to_keep: set[str]
    ids_to_remove: set[str]

    @staticmethod
    def process_documents_and_integer_ids(identified_documents_raw_json: list[dict]) -> tuple[list[dict], dict[int, str]]:
        """
        Prepare the documents for processing by the LLM.

        Reduce the number of fields in the documents to just the document name and the document description.
        Avoid using the uuid as the id, since it trend to confuses the LLM.
        Instead of uuid, use an integer id.
        """
        if not isinstance(identified_documents_raw_json, list):
            raise ValueError("identified_documents_raw_json is not a list.")

        # Only keep the 'document_name' and 'description' from each document and remove the rest.
        # Enumerate the documents with an integer id.
        process_documents = []
        integer_id_to_document_uuid = {}
        for doc in identified_documents_raw_json:
            if 'document_name' not in doc or 'description' not in doc or 'id' not in doc:
                logger.error(f"Document is missing required keys: {doc}")
                continue

            document_name = doc.get('document_name', '')
            document_description = doc.get('description', '')
            document_id = doc.get('id', '')

            current_index = len(process_documents)

            name = f"{document_name}\n{document_description}"
            dict = {
                'id': current_index,
                'name': name
            }
            process_documents.append(dict)
            integer_id_to_document_uuid[current_index] = document_id

        return process_documents, integer_id_to_document_uuid

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'FilterDocumentsToFind':
        """
        Invoke LLM with the document details to analyze.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = FILTER_DOCUMENTS_TO_FIND_SYSTEM_PROMPT.strip()

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

        sllm = llm.as_structured_llm(DocumentEnrichmentResult)
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

        enrichment_result = chat_response.raw

        markdown = cls.convert_to_markdown(enrichment_result)
        ids_to_keep, ids_to_remove = cls.extract_ids_to_keep_remove(enrichment_result)

        result = FilterDocumentsToFind(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            enrichment_result=enrichment_result,
            metadata=metadata,
            markdown=markdown,
            ids_to_keep=ids_to_keep,
            ids_to_remove=ids_to_remove
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
    def extract_ids_to_keep_remove(result: DocumentEnrichmentResult) -> tuple[set[int], set[int]]:
        """
        Convert the enrichment result to a set of document IDs to keep and remove.
        """
        ids_to_keep = set()
        ids_to_remove = set()
        for item in result.document_list:
            if item.keep_remove == KeepRemove.remove:
                ids_to_remove.add(item.id)
            elif item.keep_remove == KeepRemove.keep:
                ids_to_keep.add(item.id)
            else:
                ids_to_remove.add(item.id)
                logger.error(f"Invalid keep_remove value: {item.keep_remove}, document_id: {item.id}. Removing the document.")
        return ids_to_keep, ids_to_remove

    @staticmethod
    def convert_to_markdown(result: DocumentEnrichmentResult) -> str:
        """
        Convert the enrichment result to markdown.
        """
        rows = []
        
        rows.append("## Documents\n")
        if len(result.document_list) > 0:
            for i, item in enumerate(result.document_list, start=1):
                if i > 1:
                    rows.append("")
                rows.append(f"### ID {item.id}")
                rows.append(f"\n**Decision:** {item.keep_remove.value}")
                rows.append(f"\n**Rationale:** {item.rationale}")
        else:
            rows.append("\n*No documents identified.*")

        rows.append(f"\n**Summary:** {result.summary}")

        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    plan_prompt = find_plan_prompt("5c4b4fee-267a-409b-842f-4833d86aa215")

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("openrouter-paid-gemini-2.0-flash-001")

    path = os.path.join(os.path.dirname(__file__), 'test_data', "eu_prep_identified_documents_to_find.json")
    with open(path, 'r', encoding='utf-8') as f:
        identified_documents_raw_json = json.load(f)

    process_documents, integer_id_to_document_uuid = FilterDocumentsToFind.process_documents_and_integer_ids(identified_documents_raw_json)

    print(f"integer_id_to_document_uuid: {integer_id_to_document_uuid}")

    query = (
        f"File 'plan.txt':\n{plan_prompt}\n\n"
        f"File 'documents.json':\n{process_documents}"
    )
    print(f"Query:\n{query}\n\n")

    result = FilterDocumentsToFind.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
    print(f"\n\nIDs to keep:\n{result.ids_to_keep}")
    print(f"\n\nIDs to remove:\n{result.ids_to_remove}")
