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
    missing_assumption_list: list[str] = Field(
        description="List of missing assumptions"
    )
    underexplored_assumption_list: list[str] = Field(
        description="List of underexplored assumptions"
    )
    issues: list[ReviewItem] = Field(
        description="The most significant issues."
    )
    conclusion: str = Field(
        description="Summary of the most important issues."
    )

REVIEW_ASSUMPTIONS_SYSTEM_PROMPT = """
You are a planning expert. Your task is to review assumptions data, and identify the most critical flaws that could jeopardize the project's success.
Please limit your output to no more than 800 words.

Your analysis MUST BE DIRECTLY AND EXPLICITLY LINKED to the `domain_specific_considerations`. Explain how each missing or underexplored assumption directly relates to one or more of these considerations.

Prioritize issues based on their potential impact. IDENTIFY THE THREE MOST CRITICAL ISSUES and clearly explain why they pose the greatest risk.

For each issue, provide SPECIFIC, ACTIONABLE, and QUANTIFIABLE recommendations whenever possible.

Your analysis should:

- **Critical Missing Assumptions:** Identify essential assumptions that are completely absent. Explain why their absence poses significant risks and provide specific suggestions to fill these gaps.
- **Underexplored Assumptions:** Highlight assumptions that exist but lack sufficient detail or analysis. Explain what additional data or insights are needed to make these assumptions reliable, and suggest specific improvements.
- **Questionable Assumptions:** Identify any assumptions that appear incorrect or unrealistic based on your expert knowledge. Explain why these are questionable and what potential consequences they might have.
- **Assumptions That Are Too Optimistic or Pessimistic:** Point out assumptions that are significantly over- or under-estimated. Provide evidence or reasoning to support your assessment, and, if possible, quantify the potential impact.
- **Sensitivity Analysis Considerations:** For key variables, briefly discuss how variations in these factors could impact project outcomes. You may list these as a separate array or incorporate them within relevant issues.

Don't shy away from expressing strong opinions where necessary. Your goal is to provide the most valuable and actionable feedback possible, even if it means being critical of certain assumptions. Your goal is to act like a planning expert.

Your output must be a JSON object with the following structure:

{
  "missing_assumption_list": [ list of missing assumptions ],
  "underexplored_assumption_list": [ list of underexplored assumptions ],
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

If a section is not applicable, return it as an empty list (or an empty string for text fields). Avoid unnecessary repetition. Your response should be actionable and demonstrate expert-level insights applicable to any planning scenario.
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
