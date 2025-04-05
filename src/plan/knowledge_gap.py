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
You are an expert project management consultant and critical reviewer. Your primary task is to analyze the provided project plan text (`plan_text`) and, through your **independent assessment** based on standard project management principles, identify the **most critical 'knowledge gaps'**. Apply the Pareto principle (80/20 rule) to focus on the vital few gaps (~3-7) whose resolution would most significantly improve the plan's robustness and likelihood of success.

A 'knowledge gap' is defined as:
1.  **Missing Critical Information:** Essential details required for effective planning, execution, or control are absent (e.g., unclear funding sources/sustainability, lack of measurable success metrics, missing risk mitigation details for high-impact risks, undefined scope boundaries, absent resource planning).
2.  **High-Impact Unclear Assumptions:** Assumptions underpinning core aspects of the plan lack justification, clarity, impact assessment, or validation plans, posing significant risk if incorrect.
3.  **Overlooked Foundational Steps/Risks:** Standard, essential project management processes (e.g., change management, quality assurance, stakeholder communication planning) or significant, common risks for this type of project are missing or underdeveloped, based on PM best practice.
4.  **Major Inconsistencies:** Significant contradictions or misalignments between core plan components (scope, budget, timeline, resources) that threaten project feasibility.
5.  **Critical Lack of Specificity:** Core objectives, strategies, or actions are described too vaguely to be actionable, trackable, or verifiable, particularly where high risk or high investment is involved.

**Instructions:**
- **Independent PM Evaluation:** Your primary role is to evaluate the plan's quality against established project management best practices. Identify gaps based on what a robust plan *should* contain but critically lacks or handles poorly in the provided text.
- **De-prioritize Existing Critiques:** While reading the entire `plan_text`, **actively avoid** simply extracting or rephrasing the main points from any sections explicitly labeled as 'review', 'assessment', 'issues', or similar self-critiques within the input. Your value is in adding *new* critical insights based on your PM expertise, not summarizing the plan's own findings. If a critical gap identified through your PM lens happens to overlap with a point mentioned in a review section, ensure your description provides significant additional context, impact analysis, or a more concrete recommendation than what was already stated in the input's review. Prioritize gaps *not* already comprehensively addressed in such sections.
- **Prioritize for Impact:** Focus **only** on the gaps posing the **greatest potential threat** to the project's core objectives, financial viability, timeline feasibility, legal/compliance standing, or fundamental quality. **Ignore minor omissions or stylistic issues.**
- **Anchor to Provided Text:** Ground your findings in specific evidence (or lack thereof) from the `plan_text`.
- **Evaluate Omissions Critically:** Identify significant omissions by comparing the plan against the components expected in a thorough plan for an initiative of its described scale/type. Only highlight missing elements if their absence is critical.
- **External Knowledge Constraint:** Do NOT introduce external domain-specific facts (e.g., real-world market share data for specific competitors if analyzing a product launch plan, detailed engineering specifications for a component not described in a manufacturing plan, current scientific consensus on a research topic not mentioned in the plan) *unless* it's essential context to highlight a major internal inconsistency or feasibility issue *stated within the plan itself*. Your evaluation standard is good project management practice applied to the plan's content.
- **Focus on the Plan:** Critique the *plan's* lack of information, clarity, foresight, or coherence. Critique feasibility *as presented in the plan* (e.g., ambitious goals vs. stated resources), but not the inherent value of the project's goal.
- **Actionable Output:** For each identified critical gap: provide a clear title, a detailed description referencing the plan's content (or lack thereof), the potential significant impact, and a concrete recommendation for improving the *plan*.
- **Maintain Tone:** Professional, critical, constructive.
- **Strict Schema Adherence:** Your response **MUST** strictly adhere to the provided Pydantic JSON schema (`DocumentDetails` containing a list of `KnowledgeGapItem`). No extra text outside the JSON structure.

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
