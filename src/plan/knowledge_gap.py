"""
Considering the knowledge cut off date with the current date, what topics may have been changed since then?
A small LLM may have domains where it has less knowledge than a larger LLM that have been trained on more data.
Take a look at the proposed plan and identify areas where the LLM may have less knowledge.

PROMPT> python -m src.plan.knowledge_gap
"""
from datetime import datetime
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

class KnowledgeGapItem(BaseModel):
    """Represents a single identified knowledge gap in the project plan."""
    issue_title: str = Field(description="Brief, descriptive title of the knowledge gap (e.g., 'Unclear Budget Allocation for Marketing', 'Missing Contingency for Speaker Cancellation').")
    issue_description: str = Field(description="Detailed description of *what* specific information is missing, unclear, assumed without basis, or potentially overlooked in the plan text. Be specific about the section or topic.")
    issue_impact: str = Field(description="Potential impact or consequence if this knowledge gap is not addressed (e.g., 'Could lead to budget overruns', 'Risks low event attendance', 'May cause project delays').")
    issue_recommendation: str = Field(description="A concise recommendation on *how* to address this gap (e.g., 'Develop a detailed marketing budget breakdown', 'Create a backup speaker list', 'Conduct a specific risk assessment for X').")

class DocumentDetails(BaseModel):
    """Container for all identified knowledge gaps within the analyzed document."""
    knowledge_gaps: list[KnowledgeGapItem] = Field(
        description="A comprehensive list of knowledge gaps identified in the project plan. Aim for distinct, actionable gaps."
    )

KNOWLEDGE_GAP_SYSTEM_PROMPT = """
You are an expert project management consultant and critical reviewer. Your task is to meticulously analyze the provided project plan text and identify specific 'knowledge gaps'.

A 'knowledge gap' is defined as:
1.  **Missing Information:** Crucial details are absent (e.g., specific budget numbers, measurable KPIs, defined responsibilities, concrete timelines for sub-tasks).
2.  **Unclear Assumptions:** Assumptions are stated but lack justification, clarity, or assessment of their impact if proven wrong.
3.  **Overlooked Steps/Risks:** Essential project management steps, potential risks, or necessary compliance considerations appear to be missing or are mentioned too superficially without clear mitigation or action plans.
4.  **Inconsistencies:** Contradictory information or misalignment between different sections of the plan.
5.  **Lack of Specificity:** Plans or actions are described in vague terms without concrete details on *how* they will be executed or measured.

**Instructions:**
- Focus **exclusively** on the content within the provided `plan_text`. Do NOT introduce external knowledge, current events, or information beyond what is necessary to evaluate the plan's internal completeness and coherence based on standard project management principles.
- Your goal is to identify areas where the *plan itself* is lacking, not to critique the project idea's inherent viability based on outside factors unless the plan fails to address obvious internal contradictions or feasibility issues based *only* on what it states.
- Identify distinct and actionable knowledge gaps. Avoid overly broad or repetitive points.
- For each gap, provide a clear title, a detailed description referencing the plan's content (or lack thereof), the potential impact, and a constructive recommendation for addressing it *within the plan*.
- Maintain a professional, critical, yet constructive tone.
- Your response **MUST** strictly adhere to the provided Pydantic JSON schema (`DocumentDetails` containing a list of `KnowledgeGapItem`). Do not add any introductory text or explanations outside the JSON structure.

Today's date is TODAYS_DATE.
"""

@dataclass
class KnowledgeGap:
    """
    Considering the knowledge cut off date with the current date, what topics may have been changed since then?
    A small LLM may have domains where it has less knowledge than a larger LLM that have been trained on more data.
    Take a look at the proposed plan and identify areas where the LLM may have less knowledge.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'KnowledgeGap':
        """
        Invoke LLM with the data to be reviewed.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        system_prompt = KNOWLEDGE_GAP_SYSTEM_PROMPT.strip()
        system_prompt = system_prompt.replace("TODAYS_DATE", datetime.now().strftime("%Y-%m-%d"))

        logger.debug(f"User Prompt:\n{user_prompt}")

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

        result = KnowledgeGap(
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
        for i, knowledge_gap in enumerate(document_details.knowledge_gaps, start=1):
            if i > 1:
                rows.append("")
            rows.append(f"## {i}. {knowledge_gap.issue_title}")
            rows.append(knowledge_gap.issue_description)
            rows.append(f"\n### Impact\n{knowledge_gap.issue_impact}")
            rows.append(f"\n### Recommendation\n{knowledge_gap.issue_recommendation}")
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from src.llm_factory import get_llm

    # llm = get_llm("ollama-llama3.1")
    llm = get_llm("openrouter-paid-gemini-2.0-flash-001")

    path = os.path.join(os.path.dirname(__file__), 'test_data', "deadfish_assumptions.md")
    with open(path, 'r', encoding='utf-8') as f:
        assumptions_markdown = f.read()

    query = (
        f"File 'assumptions.md':\n{assumptions_markdown}"
    )
    print(f"Query:\n{query}\n\n")

    result = KnowledgeGap.execute(llm, query)
    json_response = result.to_dict(include_system_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")
