"""
Review the team.

PROMPT> python -m src.team.review_team
"""
import os
import json
import time
import logging
from enum import Enum
from math import ceil
from dataclasses import dataclass
from typing import List, Optional
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
    ommisions: list[ReviewItem] = Field(
        description="The most significant omissions."
    )
    recommendations: list[ReviewItem] = Field(
        description="Suggestions and recommendations."
    )

ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_SYSTEM_PROMPT = """
You are an expert in project team composition and critical analysis. Your task is to analyze a team document for a project (e.g., establishing a solar farm) and identify key issues with the team structure. In your analysis, please:

1. Identify the most significant omissions in the document (e.g., missing roles or functions).
2. Suggest potential improvements to enhance the team's effectiveness.
3. Provide recommendations on any changes or additions needed.

Your output must be structured using JSON with two main sections: "Omissions" and "Potential Improvements". Each section should include a list of items, where each item contains the following keys:
- **Issue**: A brief title or name for the omission/improvement.
- **Explanation**: A concise description of why this issue is important.
- **Recommendation**: Specific suggestions on how to address the issue.

Example Output:
{
  "Omissions": [
    {
      "Issue": "Missing Operations & Maintenance Manager",
      "Explanation": "Post-construction, a dedicated role is needed to ensure ongoing maintenance and performance optimization of the solar farm.",
      "Recommendation": "Add a dedicated Operations & Maintenance Manager to oversee long-term performance and upkeep."
    }
  ],
  "Potential Improvements": [
    {
      "Issue": "Lack of Stakeholder Engagement Role",
      "Explanation": "Managing local community and regulatory relationships is critical to avoid future conflicts and delays.",
      "Recommendation": "Consider adding a Stakeholder or Community Engagement Specialist."
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

        system_prompt = ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_SYSTEM_PROMPT.strip()

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
    # llm = get_llm("deepseek-chat")

    path = "/Users/neoneye/Desktop/010-team.md"
    with open(path, 'r') as f:
        team_document_markdown = f.read()

    job_description = "Establish a solar farm in Denmark."

    review_team = ReviewTeam.execute(llm, job_description, team_document_markdown)
    json_response = review_team.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))
