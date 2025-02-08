"""
Enrich each team member with a fictional background story and typical job activities.
"""
import os
import json
import time
from math import ceil
from typing import List, Optional
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

class TeamMember(BaseModel):
    """A human with domain knowledge."""
    id: int = Field(
        description="A unique id for the job_category."
    )
    job_background_story_of_employee: str = Field(
        description="Provide a fictional story for this person."
    )
    typical_job_activities: str = Field(
        description="Describe some typical activities in the job."
    )

class TeamDetails(BaseModel):
    team_members: list[TeamMember] = Field(
        description="The experts with domain knowledge about the problem."
    )

ENRICH_TEAM_MEMBERS_SYSTEM_PROMPT = """
Write a fictional background story about the person. It must be one paragraph that covers: 
- First name and last name.
- Location.
- What education, experience, and skills does this person have.
- Familiarity with the task.
- Why is this particular person is relevant.

The typical_job_activities describes relevant skills needed for this project.
"""

def enrich_team_members(llm: LLM, job_description: str, team_member_list: list, system_prompt: Optional[str]) -> dict:
    compact_json = json.dumps(team_member_list, separators=(',', ':'))

    user_prompt = f"""Project description:
{job_description}

Here is the list of team members that needs to be enriched:
{compact_json}
"""
    # print(user_prompt)

    chat_message_list = []
    if system_prompt:
        chat_message_list.append(
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            )
        )
    
    chat_message_user = ChatMessage(
        role=MessageRole.USER,
        content=user_prompt,
    )
    chat_message_list.append(chat_message_user)

    sllm = llm.as_structured_llm(TeamDetails)

    start_time = time.perf_counter()
    chat_response = sllm.chat(chat_message_list)
    end_time = time.perf_counter()
    duration = int(ceil(end_time - start_time))

    json_response = json.loads(chat_response.message.content)

    metadata = {
        "duration_warmup": duration,
    }
    json_response['metadata'] = metadata
    return json_response

def cleanup_enriched_team_members_and_merge_with_team_members(raw_enriched_team_member_dict: dict, team_member_list: list) -> list:
    result_team_member_list = team_member_list.copy()
    enriched_team_member_list = raw_enriched_team_member_dict['team_members']
    id_to_enriched_team_member = {item['id']: item for item in enriched_team_member_list}
    for team_member in result_team_member_list:
        id = team_member['id']
        enriched_team_member = id_to_enriched_team_member.get(id)
        if enriched_team_member:
            team_member['typical_job_activities'] = enriched_team_member['typical_job_activities']
            team_member['background_story'] = enriched_team_member['job_background_story_of_employee']
    return result_team_member_list

if __name__ == "__main__":
    from src.llm_factory import get_llm

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("deepseek-chat")

    job_description = "Investigate outbreak of a deadly new disease in the jungle."

    team_member_list = [
        {
            "id": 1,
            "category": "Medical Expertise",
            "explanation": "To identify and understand the pathogen, its symptoms, transmission methods, and potential treatments or vaccines."
        },
        {
            "id": 2,
            "category": "Epidemiologist",
            "explanation": "To track the spread of the disease, analyze patterns, and develop strategies to contain it."
        },
        {
            "id": 3,
            "category": "Field Research Specialist",
            "explanation": "To conduct on-the-ground investigations in challenging jungle environments, collect samples, and interact with affected communities."
        },
        {
            "id": 4,
            "category": "Logistics Coordinator",
            "explanation": "To manage the supply chain for equipment, medical supplies, and personnel transport to remote locations."
        }
    ]

    json_response = enrich_team_members(llm, job_description, team_member_list, ENRICH_TEAM_MEMBERS_SYSTEM_PROMPT)
    print(json.dumps(json_response, indent=2))
