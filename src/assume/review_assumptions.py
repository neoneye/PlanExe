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
    location_list: list[str] = Field(
        description="Specific locations or sites relevant to the project. Be as specific as possible. Street, city, country."
    )
    issues: list[ReviewItem] = Field(
        description="The most significant issues."
    )
    conclusion: str = Field(
        description="Summary of the most important issues."
    )

REVIEW_ASSUMPTIONS_SYSTEM_PROMPT = """
You are a world-class planning expert specializing in `expert_domain` projects located at `location_list`. Your task is to critically review the provided assumptions and identify potential weaknesses or omissions that could significantly impact project success. Your analysis should be directly linked to the domain-specific considerations outlined below and be tailored to the project’s scale and context.

**Important:** Instead of using a fixed list, dynamically derive the key domain-specific considerations from the project details provided. Consider aspects such as:
- Financial Viability & ROI,
- Timeline & Milestone Realism,
- Resource & Personnel Availability,
- Regulatory Compliance (e.g., local or regional laws),
- Infrastructure Feasibility & Environmental Impact,
- Government Subsidies & Incentive Strategies,
- Safety Protocols & Risk Management,
- Stakeholder Engagement & Community Outreach,
- Technological Infrastructure & Operational Sustainability.

Additionally, if the project involves a specific sector (e.g., renewable energy), consider sector-specific factors such as grid connection feasibility, subsidy acquisition, and environmental constraints. Your analysis should clearly articulate the three most critical issues, including quantitative sensitivity where possible.

Please limit your output to no more than 800 words.

Your analysis MUST:
1. Identify Critical Missing Assumptions.
2. Highlight Under-Explored Assumptions.
3. Challenge Questionable or Unrealistic Assumptions.
4. Discuss Sensitivity Analysis for key variables.

If no location is provided, default to "Sidney, Australia". If the location is too broad, choose a more specific region.

Return your response as a JSON object with the following structure:
{
  "expert_domain": "The area of expertise most relevant for this review",
  "domain_specific_considerations": ["List", "of", "relevant", "considerations"],
  "location_list": ["Relevant locations"],
  "issues": [
    {
      "issue": "Title of the issue",
      "explanation": "Explanation of why this issue is important",
      "recommendation": "Actionable suggestions to address the issue",
      "sensitivity": "Optional sensitivity analysis details"
    },
    ...
  ],
  "conclusion": "Summary of main findings and recommendations"
}
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
