"""
From a project description, find a team for solving the job.

PROMPT> python -m src.team.find_team_members
"""
import os
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class TeamMember(BaseModel):
    job_category_title: str = Field(
        description="Human readable title"
    )
    short_explanation: str = Field(
        description="Why that category of expert is relevant to solving the task."
    )
    people_needed: str = Field(
        description="Number of people needed."
    )
    consequences_of_not_having_this_role: str = Field(
        description="Consequences of not having this role."
    )

class DocumentDetails(BaseModel):
    brainstorm_of_needed_team_members: list[TeamMember] = Field(
        description="What experts may be needed with domain knowledge about the problem."
    )

FIND_TEAM_MEMBERS_SYSTEM_PROMPT = """
You are a highly skilled team architect and project support expert. Your mission is to analyze project descriptions and brainstorm a diverse range of *potential* human support roles. The goal is to provide a *comprehensive list of candidates* for the user to consider.

Based on the user's project description, brainstorm a team of potential human support roles. Aim for a *full list of 8 candidates*, even if some roles are less critical than others. The team should cover all crucial aspects of the project, from initial planning and preparation to execution, problem-solving, and ongoing support (if applicable). Think broadly and consider a variety of potential support needs.

**Output Requirements:**

1.  **Team Size:** The team *must* consist of *exactly 8 candidates*. If you identify fewer than 8 essential roles, brainstorm additional support roles that could potentially benefit the project, even in a minor way.

2.  **Role Titles:** Provide a clear, concise "job_category_title" that accurately describes the role's primary contribution or area of support.

3.  **Role Explanations:** Provide a brief "short_explanation" for each role, outlining its potential contribution to the project.

4.  **Consequences (If Applicable):** If a role is truly essential, describe the potential negative *consequences* of not having that support. If the role is less critical, this section can be omitted or kept brief.

5.  **People Count / Resource Level:** Use the "people_needed" field to specify the level of support required.

6.  **Project Phases / Support Stages:** Consider all relevant stages of the project or journey:
    *   **Planning & Preparation**
    *   **Execution**
    *   **Monitoring & Adjustment**
    *   **Maintenance & Sustainability**

**Essential Considerations for EVERY Role/Resource:**

*   **Specific Expertise:**
*   **Key Responsibilities:**
*   **Direct Impact (if applicable):**
*   **Project Dependencies:**
*   **Relevant Skills:**
*   **Role Priority:**

**Important Notes:**

*   Your primary goal is to provide a *complete list of 8 potential candidates*.
*   Do not omit any roles to meet the team size requirement. Brainstorm additional potential support roles as needed.
*   Be creative and think broadly about the different ways in which the user could benefit from human support.
"""

@dataclass
class FindTeamMembers:
    """
    From a project description, find a team for solving the job.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    team_member_list: list[dict]

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'FindTeamMembers':
        """
        Invoke LLM to find a team.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = FIND_TEAM_MEMBERS_SYSTEM_PROMPT.strip()

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

        team_member_list = cls.cleanup_team_members_and_assign_id(chat_response.raw)

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = FindTeamMembers(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
            team_member_list=team_member_list,
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

    def cleanup_team_members_and_assign_id(document_details: DocumentDetails) -> list:
        result_list = []
        team_members = document_details.brainstorm_of_needed_team_members
        for i, team_member in enumerate(team_members, start=1):
            item = {
                "id": i,
                "category": team_member.job_category_title,
                "explanation": team_member.short_explanation,
                "consequences": team_member.consequences_of_not_having_this_role,
                "count": team_member.people_needed,
            }
            result_list.append(item)
        return result_list
    
if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")
    plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")

    print(f"Query:\n{plan_prompt}\n\n")
    result = FindTeamMembers.execute(llm, plan_prompt)
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print("\n\nTeam members:")
    json_team = result.team_member_list
    print(json.dumps(json_team, indent=2))
