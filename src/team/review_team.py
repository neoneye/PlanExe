"""
Review the team.

PROMPT> python -m src.team.review_team
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

logger = logging.getLogger(__name__)

class ReviewItem(BaseModel):
    issue: str = Field(
        description="A brief title or name for the omission/improvement."
    )
    explanation: str = Field(
        description="A concise description of why this issue is important."
    )
    recommendation: str = Field(
        description="Specific suggestions on how to address the issue."
    )

class DocumentDetails(BaseModel):
    omissions: list[ReviewItem] = Field(
        description="The most significant omissions."
    )
    potential_improvements: list[ReviewItem] = Field(
        description="Suggestions and recommendations."
    )

REVIEW_TEAM_SYSTEM_PROMPT = """
You are an expert in designing and evaluating team structures for diverse projects, ranging from small, everyday tasks to large, complex endeavors. Your task is to analyze a team document for a project and identify key issues with the team composition. In your analysis, please:

1. Identify the most significant omissions in the document (e.g., missing roles, support functions, or necessary expertise) that could hinder effective execution, keeping in mind that the project may be personal, trivial, or highly complex.
2. Identify potential improvements that would enhance the team's overall effectiveness, communication, and clarity—tailored to the project's scale and context.
3. Provide actionable, practical recommendations for addressing each identified issue. Ensure that your recommendations are appropriately scaled: avoid suggesting overly formal or business-oriented roles (such as a dedicated Marketing Specialist, Legal Advisor, or Safety Officer) if they are not necessary for the project's scope. For personal or trivial projects, consider suggesting adjustments or integrations into existing roles (for example, incorporating safety protocols into medical consultations or educational materials) rather than introducing a new formal role.
4. Analyze the document for any potential overlaps in roles or responsibilities. If there are redundant or overlapping roles, suggest adjustments or clarifications to minimize redundancy and improve overall role clarity.

Your output must be structured using JSON with two main sections: "omissions" and "potential_improvements". Each section should be a list of items, where each item contains the following keys:
- "issue": A brief title or name for the omission or improvement.
- "explanation": A concise description of why this issue is important, considering the project's goals and user experience.
- "recommendation": Specific, actionable suggestions on how to address the issue.

Example Output:
{
  "omissions": [
    {
      "issue": "Missing Role Clarity",
      "explanation": "Clear role definitions are critical to ensure that every team member understands their responsibilities, reducing confusion and delays.",
      "recommendation": "Review the team structure and explicitly define each role's responsibilities and expectations."
    }
  ],
  "potential_improvements": [
    {
      "issue": "Need for Clear Communication Protocols",
      "explanation": "Effective communication ensures that all team members understand the project's goals and their roles, regardless of scale.",
      "recommendation": "Establish regular check-ins and define clear communication channels, such as scheduled meetings or a dedicated messaging platform."
    },
    {
      "issue": "Overlap in Roles",
      "explanation": "Redundant or overlapping responsibilities can lead to confusion and inefficiencies, as efforts may be duplicated.",
      "recommendation": "Analyze the team structure for overlaps and clarify responsibilities or merge roles where appropriate to streamline the team."
    }
  ]
}
"""

@dataclass
class ReviewTeam:
    """
    Take a look at the proposed team and provide feedback on potential omissions and improvements.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, job_description: str, team_document_markdown: str) -> 'ReviewTeam':
        """
        Invoke LLM with the project description and team document to be reviewed.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(job_description, str):
            raise ValueError("Invalid job_description.")
        if not isinstance(team_document_markdown, str):
            raise ValueError("Invalid team_document_markdown.")

        user_prompt = (
            f"Project description:\n{job_description}\n\n"
            f"Document with team members:\n{team_document_markdown}"
        )

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = REVIEW_TEAM_SYSTEM_PROMPT.strip()

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

        result = ReviewTeam(
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

    path = os.path.join(os.path.dirname(__file__), 'test_data', "solarfarm_team_without_review.md")
    with open(path, 'r', encoding='utf-8') as f:
        team_document_markdown = f.read()
    job_description = "Establish a solar farm in Denmark."

    review_team = ReviewTeam.execute(llm, job_description, team_document_markdown)
    json_response = review_team.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))
