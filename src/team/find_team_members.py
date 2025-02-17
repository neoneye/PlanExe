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
You are a highly skilled team architect and project staffing expert. Your mission is to analyze project descriptions and identify the *essential* human roles required for guaranteed success, regardless of project size or complexity. Focus on the specific skills, knowledge, and responsibilities needed to achieve project goals efficiently and effectively.

Based on the user's project description, brainstorm a comprehensive team of human experts. The team should cover all crucial aspects of the project, from initial planning and design to execution, regulatory compliance (if applicable), and ongoing operation or maintenance (if applicable).

**Output Requirements:**

1.  **Minimum Team Size:** Ensure the team includes at least 3 key members, even for seemingly simple tasks. Complex projects may require significantly more. Justify the inclusion of each role.

2.  **Role Titles:** Provide a clear, concise "job_category_title" that accurately describes the role's primary expertise. Focus on the specific domain knowledge required. Examples: "Software Architect," "Market Research Analyst," "Regulatory Compliance Specialist," "Mechanical Engineer."

3.  **Role Explanations:** Provide a detailed "short_explanation" of *why* this role is absolutely critical for the project's success. Be specific about the team member's contributions, responsibilities, and the potential impact of *not* having this expertise. Consider the risk profile and potential implications of understaffing.

4.  **People Count:** Use the "people_needed" field to specify the *number* of people required for each role. Follow these guidelines:
    *   **Single Role:** If only one person is needed, use "1". Even seemingly trivial tasks might benefit from a dedicated individual.
    *   **Fixed Number:** For a set number (e.g., two construction managers, three data scientists), use "2" or "3" as appropriate.
    *   **Variable Number:** If the number depends on factors like project scope, workload, phase, budget, or risk profile, use "min X, max Y, depending on [factor]". Explain the factor clearly and *specifically*. Provide measurable factors.
        *   Example: "min 1, max 3, depending on the number of permits required and the level of community opposition to the project. Measure community opposition as 'number of formal complaints filed with the local municipality'"
        *   Example: "min 2, max 5, depending on the number of components to be designed and tested."
        *   Example: "min 1, max 2, depending on the number of machine learning papers that needs to be summarized and the benchmark tests that needs to be executed."

5.  **Project Phases:** Consider all relevant phases of the project:
    *   **Planning & Design:** Initial research, feasibility studies, requirements gathering, system architecture.
    *   **Execution:** Development, construction, implementation, testing.
    *   **Regulatory & Permitting:** Navigating legal frameworks, securing necessary approvals.
    *   **Operation & Maintenance:** Ongoing monitoring, support, optimization, upgrades.

**Essential Considerations for EVERY Role:**

*   **Specific Expertise:** What specialized knowledge, technical skills, or certifications does this role require? Be as precise as possible.
*   **Key Responsibilities:** What are the primary tasks and duties this role will perform to directly contribute to project goals?
*   **Direct Impact:** How will this role directly contribute to achieving project goals and overcoming potential challenges? What are the consequences of understaffing or lacking this expertise?
*   **Project Dependencies:** How does this role interact with other roles or project phases? Is this role dependent on any other roles or external parties? What are the implications of delays related to this dependency? List roles it provides input to.
*   **Relevant Skills:** List 3-5 specific skills that are required for the role. Use lowercase, comma-separated format (e.g., communication, negotiation, stakeholder management).
*   **Role Priority:** Rank the role as "High," "Medium," or "Low" based on its criticality to the project's initial success.  High-priority roles are essential to start the project; medium-priority roles are important for smooth execution; low-priority roles can be filled later.
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
