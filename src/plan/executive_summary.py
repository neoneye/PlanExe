"""
One-pager that summarizes the plan.

https://en.wikipedia.org/wiki/Executive_summary

- The executive summary should always be placed at the beginning of the report.
- It's designed to be read first. Its purpose is to provide a high-level overview of the report's contents so that readers can quickly understand the key findings and recommendations.
- It helps readers decide how to engage with the rest of the report. Knowing the key takeaways upfront allows readers to prioritize which sections they need to read in detail.
- It provides context for the rest of the report. Having a clear understanding of the report's purpose and main findings makes it easier to interpret the details presented in the body of the report.

The primary target audience for the executive summary is senior management, executives, investors, and other key decision-makers. These individuals typically have limited time and need to quickly understand the most important information in the report.

PROMPT> python -m src.plan.executive_summary
"""
import os
import json
import time
import logging
from math import ceil
from typing import Optional
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole

logger = logging.getLogger(__name__)

class DocumentDetails(BaseModel):
    audience_tailoring: str = Field(
        description="Adapt the tone and detail based on who will be reading this summary (individual hobbyist, corporate, government, etc.)."
    )
    focus_and_context: str = Field(
        description="A short statement about why this project or plan exists and its overall objectives."
    )
    purpose_and_goals: str = Field(
        description="A crisp statement of the project's main goals and success criteria."
    )
    key_deliverables_and_outcomes: str = Field(
        description="Bulleted summary of the expected end-products or results from the plan."
    )
    high_level_approach: str = Field(
        description="An outline of major steps or phases to accomplish the goals."
    )
    timeline_and_budget: str = Field(
        description="A short estimate of time and top-level budget"
    )
    risks_and_mitigations: str = Field(
        description="Identify 1-2 major risks and how you plan to reduce or address them."
    )
    action_orientation: str = Field(
        description="Explain the immediate actions or next steps needed to move forward. Summarize who, what, and when."
    )
    overall_takeaway: str = Field(
        description="A final, concise statement emphasizing the main point or value of the plan (e.g., expected benefits, ROI, key success metric)."
    )

EXECUTIVE_SUMMARY_SYSTEM_PROMPT = """
You are an expert at creating *executive summaries of project *review reports*. Your task is to convert the input Markdown into a *concise, high-impact, one-page summary that provides key decision-makers with the most important findings and actionable recommendations from the review*. This executive summary should be placed at the beginning of the report.

Adapt the tone and detail based on who will be reading this summary (individual hobbyist, corporate, government, senior management, executives, investors, and other key decision-makers, etc.).

**Key Principles:**
- **Focus on Actionability:** Prioritize information that will *drive immediate decisions and actions*. Highlight the *most urgent issues* the project team must address.
- **Quantify Impacts:** *Whenever possible, quantify the potential benefits of implementing recommendations* (e.g., cost savings, time improvements, ROI increases). Use realistic estimates if precise data is unavailable.
- **Prioritize Findings:** *Highlight the MOST CRITICAL findings from the review, not just a general overview of the project*. If applicable, indicate the severity or likelihood of each risk to help decision-makers prioritize.
- **Be Concise:** Every sentence must have extreme clarity and succinctness.
- **Clarify Scope and Stakeholders:** Where relevant, mention stakeholder context (e.g., who commissioned the review, who benefits from it) and any environmental or regulatory compliance concerns. If you include a budget figure, specify if it covers only immediate next steps or the entire plan.
- **Highlight Intangible Benefits:** If relevant, note any intangible or non-financial benefits (e.g., community goodwill, brand perception, or compliance improvements).
- **Focus on the Report:** Ensure this is an executive summary of the *review report*, not just a summary of the project itself.

**Output Requirements:**
- Use only plain Markdown (no bold formatting or other styling).
- Retain headings using only '#' and '##'. Convert any deeper levels to these.
- Use bullet lists with a hyphen and a space.

**Structure of the Executive Summary:**
1. **Report Purpose:** Clearly state the purpose of the review report. What questions did the review aim to answer? What sources of information were used (e.g., SWOT analysis, expert interviews, existing documentation)?
2. **Critical Findings:** Highlight the 3–5 most critical findings from the review. These should be the areas that pose the greatest risk to the project’s success or present major opportunities.
3. **Key Recommendations:** For each critical finding, provide a specific, actionable recommendation. What concrete steps should the project team take to address the issue? If there are multiple deliverables or phases, indicate which have the highest priority.
4. **Expected Benefits:** For each recommendation, quantify or estimate the expected benefits (cost savings, time improvements, or ROI increases) and call out any intangible benefits or regulatory advantages.
5. **Key Next Steps:** End with a clear call to action, outlining the immediate next steps the project team should take. Specify if these steps need to happen within a particular timeframe or budget range.

**Tone and Style:**
- Use clear, concise, and professional language.
- Avoid technical jargon and overly complex sentences.
- Focus on the most important information that decision-makers need to know.

**Audience:**
- The primary audience is senior management, executives, investors, and other key decision-makers who have limited time and need to quickly understand the project’s value and key takeaways.
"""

@dataclass
class ExecutiveSummary:
    system_prompt: Optional[str]
    user_prompt: str
    response: str
    markdown: str
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'ExecutiveSummary':
        """
        Invoke LLM with a long markdown document that needs an executive summary.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        system_prompt = EXECUTIVE_SUMMARY_SYSTEM_PROMPT.strip()
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

        result = ExecutiveSummary(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            markdown=markdown,
            metadata=metadata,
        )
        logger.debug("ExecutiveSummary instance created successfully.")
        return result    

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        d['markdown'] = self.markdown
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
        rows.append(f"## Focus and Context\n{document_details.focus_and_context}")
        rows.append(f"\n## Purpose and Goals\n{document_details.purpose_and_goals}")
        rows.append(f"\n## Key Deliverables and Outcomes\n{document_details.key_deliverables_and_outcomes}")
        rows.append(f"\n## High-Level Approach\n{document_details.high_level_approach}")
        rows.append(f"\n## Timeline and Budget\n{document_details.timeline_and_budget}")
        rows.append(f"\n## Risks and Mitigations\n{document_details.risks_and_mitigations}")
        rows.append(f"\n## Action Orientation\n{document_details.action_orientation}")
        rows.append(f"\n## Overall Takeaway\n{document_details.overall_takeaway}")
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)
    
if __name__ == "__main__":
    from src.llm_factory import get_llm

    path = os.path.join(os.path.dirname(__file__), 'test_data', 'solarfarm_consolidate_assumptions_short.md')
    with open(path, 'r', encoding='utf-8') as f:
        the_markdown = f.read()

    model_name = "ollama-llama3.1"
    llm = get_llm(model_name)

    query = the_markdown
    input_bytes_count = len(query.encode('utf-8'))
    print(f"Query: {query}")
    result = ExecutiveSummary.execute(llm, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.markdown}")

    output_bytes_count = len(result.markdown.encode('utf-8'))
    print(f"\n\nInput bytes count: {input_bytes_count}")
    print(f"Output bytes count: {output_bytes_count}")
    bytes_saved = input_bytes_count - output_bytes_count
    print(f"Bytes saved: {bytes_saved}")
    print(f"Percentage saved: {bytes_saved / input_bytes_count * 100:.2f}%")

