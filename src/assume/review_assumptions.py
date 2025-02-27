"""
Review the assumptions. Are they too low/high? Are they reasonable? Are there any missing assumptions?

PROMPT> python -m src.assume.review_assumptions
"""
import os
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM
from src.format_json_for_use_in_query import format_json_for_use_in_query

logger = logging.getLogger(__name__)

class ReviewItem(BaseModel):
    issue: str = Field(
        description="A brief title or name."
    )
    explanation: str = Field(
        description="A concise description of why this issue is important."
    )
    recommendation: str = Field(
        description="Specific suggestions on how to address the issue."
    )
    sensitivity: str = Field(
        default="",
        description="Optional: Provide any sensitivity analysis insights related to this issue."
    )

class DocumentDetails(BaseModel):
    expert_domain: str = Field(
        description="The domain of the expert reviewer."
    )
    domain_specific_considerations: list[str] = Field(
        description="Key factors and areas of focus relevant to the specific project domain, which this review should prioritize."
    )
    issues: list[ReviewItem] = Field(
        description="The most significant issues."
    )
    conclusion: str = Field(
        description="Summary of the most important issues."
    )

REVIEW_ASSUMPTIONS_SYSTEM_PROMPT = """
You are a planning expert with experience across a diverse range of projects—from small, everyday tasks to large-scale, business-critical initiatives. Your task is to review the provided assumptions data and identify the most critical flaws that could jeopardize the project's success. Your review should be directly and explicitly linked to the provided `domain_specific_considerations`, and it must be adaptable to the scale and context of the plan being reviewed. For example, a trivial plan like finding a misplaced TV remote requires a different level of analysis compared to constructing a metro line or drafting a detailed technical report.

Please limit your output to no more than 800 words.

Your analysis MUST:
- **Tailor Feedback Based on Scale:** If the plan is small or trivial, focus on essential assumptions without overcomplicating the analysis. For large or complex plans, provide in-depth, multi-dimensional reviews with strategic insights.
- **Directly Link to Domain-Specific Considerations:** Explain how each missing or underexplored assumption directly relates to one or more of these considerations (e.g., Financial Feasibility, Timeline & Milestones, Resource & Personnel, Governance, Safety, Environmental Impact, Stakeholder Engagement, and Operational Systems).
- **Prioritize the Three Most Critical Issues:** Clearly identify and explain why these issues pose the greatest risk, including potential impacts and quantitative sensitivity insights where possible.

Your review should include:

1. **Critical Missing Assumptions:** Identify any essential assumptions that are completely absent. Explain why their absence could significantly risk the project's success and provide specific, actionable suggestions to fill these gaps.
2. **Underexplored Assumptions:** Highlight assumptions that exist but lack sufficient detail or analysis. Describe what additional data or insights are needed to solidify these assumptions and suggest concrete improvements.
3. **Questionable or Overly Optimistic/Pessimistic Assumptions:** Point out any assumptions that appear incorrect, unrealistic, or skewed (either overly optimistic or pessimistic). Offer evidence or reasoning to support your assessment and quantify the potential impact where possible.
4. **Sensitivity Analysis Considerations:** Briefly discuss how variations in key variables (e.g., permitting delays, technological obsolescence, resource availability) could affect outcomes. You may incorporate these insights within the relevant issues or list them separately.

Do not shy away from being critical or direct. Your goal is to provide the most valuable, actionable, and expert-level feedback possible for any planning scenario.

Your output must be a JSON object with the following structure:

{
  "issues": [
    {
      "issue": "Brief title of the issue",
      "explanation": "Concise explanation of why the issue is important",
      "recommendation": "Specific suggestions to address the issue",
      "sensitivity": "Optional: Any sensitivity analysis insights related to this issue"
    },
    ...
  ],
  "conclusion": "A concise summary of the main findings and recommendations"
}

Return empty arrays or empty strings for any sections that are not applicable. Your response should be clear, concise, and tailored to the plan’s scale and domain-specific context.
"""

@dataclass
class ReviewAssumptions:
    """
    Take a look at the assumptions and provide feedback on potential omissions and improvements.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'ReviewAssumptions':
        """
        Invoke LLM with the project description and assumptions to be reviewed.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = REVIEW_ASSUMPTIONS_SYSTEM_PROMPT.strip()

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

        result = ReviewAssumptions(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
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

    llm = get_llm("ollama-llama3.1")

    base_path = os.path.join(os.path.dirname(__file__), 'test_data', 'review_assumptions1')

    # Obtain files
    files = os.listdir(base_path)
    files = [f for f in files if not f.startswith('.')]
    files.sort()
    # print(files)

    # Read the files, and concat their data into a single string
    documents = []
    for file in files:
        s = f"File: '{file}'\n"
        with open(os.path.join(base_path, file), 'r', encoding='utf-8') as f:
            s += f.read()
        documents.append(s)
    all_documents_string = "\n\n".join(documents)
    print(all_documents_string)

    review_assumptions = ReviewAssumptions.execute(llm, all_documents_string)
    json_response = review_assumptions.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))
