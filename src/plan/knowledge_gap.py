"""
What's missing or underdeveloped in the plan.

Considering the knowledge cut off date with the current date, what topics may have been changed since then?
A small LLM may have domains where it has less knowledge than a larger LLM that have been trained on more data.
Take a look at the proposed plan and identify areas where the LLM may have less knowledge.

IDEA: Remove explicit review/critique sections from the source document before sending it to the LLM if you want the highest chance of a truly independent PM-based assessment. LLMs, even with strong negative constraints ("Do NOT simply extract..."), can be significantly influenced by explicit critique or review sections already present in the input text. Causing the LLM to echo the critique sections in its response, without adding any new critical insights.

PROMPT> python -m src.plan.knowledge_gap
"""
from datetime import datetime
from enum import Enum
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

class IssueCategory(str, Enum):
    COMPLETENESS_CLARITY = "Completeness & Clarity" # missing info, unclear, inconsistent, vague
    TIME_SENSITIVITY = "Time Sensitivity / Knowledge Cutoff" # volatile data, changing regulations, shifting market conditions, geopolitical risks

class PlanIssueItem(BaseModel):
    """Represents a single identified issue or area for improvement in the project plan."""
    category: IssueCategory = Field(description="The category of the identified issue.")
    issue_title: str = Field(description="Brief, descriptive title of the issue (e.g., 'Unclear Budget Allocation', 'Outdated Exchange Rate Assumption', 'Missing Regulatory Compliance Check').")
    issue_description: str = Field(description="Detailed description of the issue. For 'Completeness & Clarity', describe what's missing/unclear in the plan. For 'Time Sensitivity', explain *why* the referenced information (e.g., specific rate, regulation, technology, market condition) is likely outdated due to the time elapsed since common knowledge cutoffs and today's date, referencing the specific part of the plan.")
    issue_impact: str = Field(description="Potential impact or consequence if this issue is not addressed (e.g., 'Budget inaccuracy', 'Non-compliance risk', 'Project delays due to unforeseen market shifts').")
    issue_recommendation: str = Field(description="A concise recommendation. For 'Completeness & Clarity', suggest how to improve the *plan*. For 'Time Sensitivity', recommend **actions or tools** to get *current, real-world data* to validate or update the plan's assumption (e.g., 'Use real-time currency converter API', 'Check current government regulations website', 'Conduct fresh market analysis').")

class PlanAnalysisReport(BaseModel):
    """Container for all identified critical issues within the analyzed document."""
    identified_issues: list[PlanIssueItem] = Field(
        description="A prioritized list of critical issues identified in the project plan, including both structural gaps and time-sensitive vulnerabilities. Aim for the ~3-7 most critical issues overall."
    )

KNOWLEDGE_GAP_SYSTEM_PROMPT = """
You are an expert project management consultant and critical reviewer. Your primary task is to analyze the provided project plan text (`plan_text`) and, through your **independent assessment**, identify the **most critical 'plan issues'**. Apply the Pareto principle (80/20 rule) to focus on the vital few issues (~3-7) whose resolution would most significantly improve the plan's robustness and likelihood of success. These issues fall into two main categories:

1.  **Completeness & Clarity Gaps:** Issues related to the plan's internal structure, detail, and coherence based on standard project management principles.
2.  **Time Sensitivity / Knowledge Cutoff Vulnerabilities:** Issues where the plan relies on information or assumptions likely outdated due to the time elapsed between common LLM knowledge cutoff dates (generally 2022-2023) and today's date.

**Definitions of Issues:**

*   **Category: Completeness & Clarity**
    *   **Missing Critical Information:** Essential planning details absent (e.g., detailed budgets, specific metrics, risk mitigation details, scope boundaries, resource plans).
    *   **High-Impact Unclear Assumptions:** Core assumptions lack justification, clarity, impact assessment, or validation plans.
    *   **Overlooked Foundational Steps/Risks:** Standard PM processes or significant risks missing/underdeveloped.
    *   **Major Inconsistencies:** Significant contradictions between core plan components.
    *   **Critical Lack of Specificity:** Core objectives/strategies too vague to be actionable or trackable.
*   **Category: Time Sensitivity / Knowledge Cutoff**
    *   **Potentially Outdated Data/Rates:** Plan references specific data points highly prone to change (e.g., currency exchange rates, market statistics, specific technology costs/performance).
    *   **Obsolete Regulations/Policies:** Plan relies on compliance with regulations or policies known to evolve frequently (e.g., environmental laws, data privacy rules, trade agreements).
    *   **Shifting Market/Tech Landscape:** Plan assumptions about market conditions, competitor positions, or the state of relevant technology may no longer hold true.
    *   **Geopolitical/Economic Instability:** Plan implicitly assumes stability in regions known for volatility affecting factors like supply chains or currency (e.g., referencing a specific unstable currency rate).

**Instructions:**
- **Perform an Independent Assessment:** Evaluate the plan's quality against established PM best practices AND assess its vulnerability to real-world changes since typical knowledge cutoffs.
- **Identify Both Types of Issues:** Look for both structural plan gaps (`Completeness & Clarity`) AND potential issues arising from outdated information (`Time Sensitivity`).
- **De-prioritize Existing Critiques:** **Actively avoid** simply extracting or rephrasing the main points from any sections explicitly labeled as 'review', 'assessment', 'issues', etc., within the input. Focus on adding *new* critical insights or identifying time-sensitive vulnerabilities. If an issue overlaps with a review point, ensure significant additional context or impact analysis is provided.
- **Prioritize for Impact:** Focus **only** on the ~3-7 issues posing the **greatest potential threat** overall (considering both categories) to the project's core objectives, financial viability, timeline, legal standing, or quality. Ignore minor omissions.
- **Anchor to Provided Text:** Ground your findings in specific evidence (or lack thereof) from the `plan_text`. For time-sensitive issues, clearly state *what* element in the plan is potentially outdated.
- **External Knowledge Constraint (Clarified):** Do NOT introduce specific *current* external facts (e.g., "The *current* DKK/USD rate is X"). Instead, identify *that* a rate mentioned in the plan *is likely outdated* and recommend *how to check* the current rate. Your benchmark is general knowledge about what *types* of information change frequently.
- **Focus on the Plan & Actionability:** Critique the *plan's* issues. For `Completeness & Clarity`, recommend improving the *plan*. For `Time Sensitivity`, recommend **actions or tools** to get *current, real-world data* to validate or update the plan's assumption (e.g., 'Use real-time currency converter API/website', 'Check current official government regulation database', 'Conduct fresh market analysis survey', 'Consult recent geopolitical risk reports').
- **Maintain Tone:** Professional, critical, constructive.
- **Strict Schema Adherence:** Your response **MUST** strictly adhere to the provided Pydantic JSON schema (`PlanAnalysisReport` containing a list of `PlanIssueItem`). Ensure the `category` field is correctly assigned. No extra text outside the JSON structure.

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

        sllm = llm.as_structured_llm(PlanAnalysisReport)
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
    def convert_to_markdown(document_details: PlanAnalysisReport) -> str:
        """
        Convert the raw document details to markdown.
        """
        rows = []
        for i, identified_issue in enumerate(document_details.identified_issues, start=1):
            if i > 1:
                rows.append("")
            rows.append(f"## {i}. {identified_issue.issue_title}\n")
            rows.append(identified_issue.issue_description)
            rows.append(f"\n**Category:** {identified_issue.category.value}")
            rows.append(f"\n**Impact:** {identified_issue.issue_impact}")
            rows.append(f"\n**Recommendation:** {identified_issue.issue_recommendation}")
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from src.llm_factory import get_llm

    # llm = get_llm("ollama-llama3.1")
    llm = get_llm("openrouter-paid-gemini-2.0-flash-001")
    # llm = get_llm("openrouter-paid-openai-gpt-4o-mini")

    path = os.path.join(os.path.dirname(__file__), 'test_data', "deadfish_assumptions.md")
    # path = os.path.join(os.path.dirname(__file__), 'test_data', "solarfarm_consolidate_assumptions_short.md")
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
