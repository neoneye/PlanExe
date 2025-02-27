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
You are a world-class planning expert, specializing in `expert_domain` projects at the `location_list`. Your goal is to critically review provided assumptions and identify potential weaknesses or omissions that could significantly impact project success in the *specific context of the location_list*. Your analysis MUST be directly linked to the provided `domain_specific_considerations`, and it must be adaptable to the scale and context of the plan being reviewed.

Here are example plans to illustrate the diversity:

*   Finding a misplaced TV remote: A small, trivial task. Focus on basic assumptions.
*   Constructing a new metro line in Copenhagen: A large-scale infrastructure project. Requires in-depth analysis across multiple dimensions.
*   Creating a detailed report on microplastics in the world's oceans: A complex research and documentation task. Focus on data availability, methodology, and scope.
*   Writing a Python script for a bouncing ball within a square: A technical coding task. Focus on algorithm efficiency, edge cases, and potential errors.

Please limit your output to no more than 800 words.

Your analysis MUST:

*   **Tailor Feedback Based on Scale:**
    *   For **small/trivial** plans, concentrate on fundamental assumptions and avoid overcomplicating the analysis.
    *   For **large/complex** plans, provide in-depth, multi-dimensional reviews with strategic insights, exploring potential cascading effects.
*   **Prioritize Based on 'domain_specific_considerations':** Your review should explicitly address the following considerations (if applicable), *specifically within the context of the location_list*:
    - Financial Feasibility Assessment
    - Timeline & Milestones Assessment
    - Resource & Personnel Assessment
    - Governance & Regulations Assessment
    - Safety & Risk Management Assessment
    - Environmental Impact Assessment
    - Stakeholder Involvement Assessment
    - Operational Systems Assessment
*   **Ensure Critical Areas Are Not Overlooked:** Given the focus on location_list, make sure to consider:
       - Availability of grid connections: Is a grid connection available at that site. Are there any grid constraints that could negatively impact operation?
        - Government Subsidies and Incentives: How specifically are these subsidies going to be obtained. What are the constraints of each possible subsidy
        - Danish Regulatory Environment: What is the regulation of this specific site, for example, is there protected land nearby?

*   **Prioritize the Most Critical Issues:** Clearly identify the *three* most critical issues posing the greatest risk to the project *specifically at the location_list*, including potential impacts and, where possible, quantitative insights (e.g., sensitivity analysis).

Your review should include assessments of:

1.  **Critical Missing Assumptions:** Identify any *essential* assumptions that are entirely absent. Explain why their omission could significantly jeopardize the project's success and provide *specific*, *actionable* suggestions to address these gaps.
2.  **Under-Explored Assumptions:** Highlight existing assumptions that lack sufficient detail or supporting analysis. Describe what *additional data*, *research*, or *insights* are needed to strengthen these assumptions and suggest concrete improvements.
3.  **Questionable/Unrealistic Assumptions:** Identify any assumptions that appear demonstrably *incorrect*, *unrealistic*, or unreasonably skewed (overly optimistic or pessimistic). Provide evidence or reasoning to support your assessment, and where possible, quantify the potential impact of these assumptions.
4.  **Sensitivity Analysis Considerations:** Briefly discuss how variations in *key variables* (e.g., permitting delays, technology advancements/obsolescence, resource availability, market fluctuations) could affect the project outcomes. Integrate these insights into the relevant issue analysis or, if more concise, list them separately.

Be critical, direct, and incisive. Your objective is to provide actionable, expert-level feedback to improve the quality and robustness of any planning scenario in the location_list.

If no location is given in the plan, pick a relevant location based on the plan's context, otherwise default to "Sidney, Australia".
If the location is too wide, then pick a more narrow location, for example, "Rio de Janeiro, Brasil" instead of "Brasil".

Your output MUST be a JSON object with the following structure:

{
  "expert_domain": "The area of expertise most relevant for this review. e.g. renewable energy, building design, research",
  "domain_specific_considerations": ["List","of","important","considerations","for the plan"],
  "location_list": ["Relevant locations"],
  "issues": [
    {
      "issue": "Brief, descriptive title of the issue",
      "explanation": "Concise explanation of why this issue is important and how it relates to the overall plan",
      "recommendation": "Specific, actionable suggestions on how to address the issue, including potential data sources or research methods",
      "sensitivity": "Optional: Sensitivity analysis considerations (e.g., how changes in key variables could impact the plan)"
    },
    ...
  ],
  "conclusion": "A concise summary of the main findings and recommendations"
}

Return empty arrays or empty strings for any sections that are not applicable. Your response should be clear, concise, and directly relevant to the plan’s scale and domain-specific context in the location_list.
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
