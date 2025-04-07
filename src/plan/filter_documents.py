"""
Filter documents by identifying duplicates and irrelevant documents.

This module analyzes document lists to identify:
- Duplicate documents (near identical or similar documents)
- Irrelevant documents (documents that don't align with project goals)
- Documents that can be consolidated

The result is a cleaner, more focused list of essential documents.

PROMPT> python -m src.plan.filter_documents
"""
import os
import json
import time
import logging
from uuid import uuid4
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

class DocumentEnrichment(BaseModel):
    """Represents the enrichment decision for a document."""
    document_id: str = Field(
        description="The ID of the document being evaluated."
    )
    document_name: str = Field(
        description="The name of the document being evaluated."
    )
    keep_remove: KeepRemove = Field(
        description="Whether the document should be kept or removed."
    )
    keep_remove_reason: str = Field(
        description="The reason for the keep/remove decision."
    )
    similar_document_ids: Optional[List[str]] = Field(
        default=None,
        description="IDs of documents that are similar to this one, if any."
    )
    consolidation_suggestion: Optional[str] = Field(
        default=None,
        description="Suggestion for how to consolidate this document with others, if applicable."
    )

class DocumentEnrichmentResult(BaseModel):
    """The result of enriching a list of documents."""
    document_enrichment_list: List[DocumentEnrichment] = Field(
        description="Enrichment decisions for documents."
    )
    summary: str = Field(
        description="A summary of the enrichment decisions."
    )

FILTER_DOCUMENTS_SYSTEM_PROMPT = """
You are an expert in project planning and documentation. Your task is to analyze the provided document lists and identify:
1. Duplicate or near-identical documents
2. Irrelevant documents that don't align with the project goals
3. Documents that could be consolidated

For each document in the provided lists, determine whether it should be kept or removed, and provide a clear reason for your decision.

When evaluating documents:
- Consider the document name, description, and purpose
- Look for semantic similarity between documents
- Assess the relevance to the project goals
- Consider whether the document adds unique value to the project

For documents that are similar but not identical, suggest how they could be consolidated.

Your analysis should result in a cleaner, more focused list of essential documents that will be most valuable for the project planning process.
"""

@dataclass
class FilterDocuments:
    """
    Analyzes document lists to identify duplicates and irrelevant documents.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    enrichment_result: DocumentEnrichmentResult
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'FilterDocuments':
        """
        Invoke LLM with the document details to analyze.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = FILTER_DOCUMENTS_SYSTEM_PROMPT.strip()

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

        result = FilterDocuments(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            enrichment_result=enrichment_result,
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
    def convert_to_markdown(result: DocumentEnrichmentResult) -> str:
        """
        Convert the enrichment result to markdown.
        """
        rows = []
        
        rows.append("## Document Enrichments\n")
        if len(result.document_enrichment_list) > 0:
            for i, item in enumerate(result.document_enrichment_list, start=1):
                if i > 1:
                    rows.append("")
                rows.append(f"### {i}. {item.document_name}")
                rows.append(f"\n**ID:** {item.document_id}")
                rows.append(f"\n**Decision:** {item.keep_remove.value}")
                rows.append(f"\n**Reason:** {item.keep_remove_reason}")
                if item.similar_document_ids:
                    rows.append("\n**Similar Documents:**")
                    for doc_id in item.similar_document_ids:
                        rows.append(f"- {doc_id}")
                if item.consolidation_suggestion:
                    rows.append(f"\n**Consolidation Suggestion:** {item.consolidation_suggestion}")
        else:
            rows.append("\n*No documents identified.*")

        rows.append(f"\n**Summary:** {result.summary}")

        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from src.llm_factory import get_llm

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("openrouter-paid-gemini-2.0-flash-001")

    path = os.path.join(os.path.dirname(__file__), 'test_data', "silo_identified_documents.md")
    with open(path, 'r', encoding='utf-8') as f:
        identified_documents_markdown = f.read()

    query = (
        f"File 'documents.md':\n{identified_documents_markdown}"
    )
    print(f"Query:\n{query}\n\n")

    result = FilterDocuments.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
    