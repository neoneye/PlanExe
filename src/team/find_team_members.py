"""
From a project description, find a team for solving the job.

PROMPT> python -m src.team.find_team_members
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
    job_category_title: str = Field(
        description="Human readable title"
    )
    short_explanation: str = Field(
        description="Why that category of expert is relevant to solving the task."
    )
    people_needed: str = Field(
        description="Number of people needed."
    )

class DocumentDetails(BaseModel):
    brainstorm_of_needed_team_members: list[TeamMember] = Field(
        description="What experts may be needed with domain knowledge about the problem."
    )

FIND_TEAM_MEMBERS_SYSTEM_PROMPT = """
Pick a good team of humans for solving the task.

Ensure that the team consists of at least 5 members.

The "job_category_title" field must be a brief the title that captures what the role is about.
Such as area of expertise, group, subject, topic or domain.

Estimate how many people are needed for each role.
What is the minimum of people needed for the role.
What is the maximum of people needed for the role.
Use the people_needed field to specify the number of people needed for each role: 
- if only one person is needed, use "1".
- if two people are needed, use "2".
- When it can vary, use "min 5,max 10,depending on capacity".

Provide a short explanation of why that team member is relevant for the project.
"""

def find_team_members(llm: LLM, query: str, system_prompt: Optional[str]) -> dict:
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
        content=query,
    )
    chat_message_list.append(chat_message_user)

    sllm = llm.as_structured_llm(DocumentDetails)

    start_time = time.perf_counter()
    chat_response = sllm.chat(chat_message_list)
    end_time = time.perf_counter()
    duration = int(ceil(end_time - start_time))

    json_response = json.loads(chat_response.message.content)

    metadata = {
        "duration": duration,
    }
    json_response['metadata'] = metadata
    return json_response

def cleanup_team_members_and_assign_id(team_member_dict: dict) -> list:
    result_list = []
    team_members = team_member_dict['brainstorm_of_needed_team_members']
    for i, team_member in enumerate(team_members, start=1):
        item = {
            "id": i,
            "category": team_member['job_category_title'],
            "explanation": team_member['short_explanation'],
            "count": team_member['people_needed'],
        }
        result_list.append(item)
    return result_list

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")
    plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")

    print(f"Query:\n{plan_prompt}\n\n")
    json_response = find_team_members(llm, plan_prompt, FIND_TEAM_MEMBERS_SYSTEM_PROMPT)
    print(json.dumps(json_response, indent=2))
