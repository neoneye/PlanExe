"""
Enrich the team members with what kind of equipment and facilities they need for the task.
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
    equipment_needs: str = Field(
        description="What expensive resources are needed for the daily job."
    )
    facility_needs: str = Field(
        description="What facilities are needed for the daily job."
    )

class DocumentDetails(BaseModel):
    team_members: list[TeamMember] = Field(
        description="The experts with domain knowledge about the problem."
    )

ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_SYSTEM_PROMPT = """
Identify what kind of equipment and facilities are needed for the daily job of each team member.
"""

def enrich_team_members_with_environment_info(llm: LLM, job_description: str, team_member_list: list, system_prompt: Optional[str]) -> dict:
    compact_json = json.dumps(team_member_list, separators=(',', ':'))

    user_prompt = f"""Project description:
{job_description}

Here is the list of team members that needs to be enriched:
{compact_json}
"""
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

    sllm = llm.as_structured_llm(DocumentDetails)

    start_time = time.perf_counter()
    chat_response = sllm.chat(chat_message_list)
    end_time = time.perf_counter()

    json_response = json.loads(chat_response.message.content)

    duration = int(ceil(end_time - start_time))

    metadata = {
        "duration": duration,
    }
    json_response['metadata'] = metadata
    return json_response

def cleanup_enriched_team_members_with_environment_info_and_merge_with_team_members(raw_enriched_team_member_dict: dict, team_member_list: list) -> list:
    result_team_member_list = team_member_list.copy()
    enriched_team_member_list = raw_enriched_team_member_dict['team_members']
    id_to_enriched_team_member = {item['id']: item for item in enriched_team_member_list}
    for team_member in result_team_member_list:
        id = team_member['id']
        enriched_team_member = id_to_enriched_team_member.get(id)
        if enriched_team_member:
            team_member['equipment_needs'] = enriched_team_member['equipment_needs']
            team_member['facility_needs'] = enriched_team_member['facility_needs']
    return result_team_member_list

if __name__ == "__main__":
    from src.llm_factory import get_llm

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("deepseek-chat")

    job_description = "Establish a new police station in a high crime area."

    team_member_list = [
        {
            "id": 1,
            "category": "Law Enforcement",
            "explanation": "Police officers and detectives are essential for patrolling, investigation, and maintaining public safety."
        },
        {
            "id": 2,
            "category": "Administration",
            "explanation": "Administrative staff manage paperwork, scheduling, and coordination of police activities."
        },
        {
            "id": 3,
            "category": "Forensics",
            "explanation": "Forensic experts analyze crime scene evidence to support investigations."
        },
        {
            "id": 4,
            "category": "Community Relations",
            "explanation": "Officers or liaisons engage with the community to build trust and cooperation."
        }
    ]

    json_response = enrich_team_members_with_environment_info(llm, job_description, team_member_list, ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_SYSTEM_PROMPT)
    print(json.dumps(json_response, indent=2))
