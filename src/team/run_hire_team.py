"""
PROMPT> python -m src.team.run_hire_team
"""
from datetime import datetime
import os
import json
from src.team.find_team_members import FindTeamMembers
from src.team.enrich_team_members import EnrichTeamMembers
from src.team.enrich_team_members_with_environment_info import ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_SYSTEM_PROMPT, enrich_team_members_with_environment_info, cleanup_enriched_team_members_with_environment_info_and_merge_with_team_members
from src.team.create_markdown_document import create_markdown_document
from src.plan.find_plan_prompt import find_plan_prompt
from src.llm_factory import get_llm

llm = get_llm("ollama-llama3.1")
# llm = get_llm("openrouter-paid-gemini-2.0-flash-001")
# llm = get_llm("deepseek-chat", max_tokens=8192)

plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")

run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
print(f"Run id: {run_id}")
print(f"Plan: {plan_prompt}")

run_dir = f'run/{run_id}'

# Create the output folder if it doesn't exist
os.makedirs(run_dir, exist_ok=True)

plan_prompt_file = f'{run_dir}/001-plan.txt'
with open(plan_prompt_file, 'w') as f:
    f.write(plan_prompt)

print("Finding team members for this task...")
find_team_members = FindTeamMembers.execute(llm, plan_prompt)
team_members_raw_file = f'{run_dir}/002-team_members_raw.json'
with open(team_members_raw_file, 'w') as f:
    f.write(json.dumps(find_team_members.to_dict(), indent=2))

team_members_list = find_team_members.team_member_list
team_members_list_file = f'{run_dir}/003-team_members_list.json'
with open(team_members_list_file, 'w') as f:
    f.write(json.dumps(team_members_list, indent=2))

print(f"Number of team members: {len(team_members_list)}")
team_member_category_list = [item['category'] for item in team_members_list]
print(f"Team member categories: {team_member_category_list}")

print("Step A: Enriching team members...")
enrich_team_members = EnrichTeamMembers.execute(llm, plan_prompt, team_members_list)
enrich_team_members_raw_dict = enrich_team_members.to_dict()
enrich_team_members_raw_file = f'{run_dir}/004-enrich_team_members_raw.json'
with open(enrich_team_members_raw_file, 'w') as f:
    f.write(json.dumps(enrich_team_members_raw_dict, indent=2))

enrich_team_members_list = enrich_team_members.team_member_list
enrich_team_members_list_file = f'{run_dir}/005-enriched_team_members_list.json'
with open(enrich_team_members_list_file, 'w') as f:
    f.write(json.dumps(enrich_team_members_list, indent=2))
print("Step A: Done enriching team members.")

print("Step B: Enriching team members with environment info...")
enrich_team_members_with_environment_info_raw_dict = enrich_team_members_with_environment_info(llm, plan_prompt, enrich_team_members_list, ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_SYSTEM_PROMPT)
enrich_team_members_with_environment_info_raw_file = f'{run_dir}/006-enrich_team_members_with_environment_info_raw.json'
with open(enrich_team_members_with_environment_info_raw_file, 'w') as f:
    f.write(json.dumps(enrich_team_members_with_environment_info_raw_dict, indent=2))

enrich_team_members_with_environment_info_list = cleanup_enriched_team_members_with_environment_info_and_merge_with_team_members(enrich_team_members_with_environment_info_raw_dict, enrich_team_members_list)
enrich_team_members_with_environment_info_list_file = f'{run_dir}/007-enriched_team_members_with_environment_info_list.json'
with open(enrich_team_members_with_environment_info_list_file, 'w') as f:
    f.write(json.dumps(enrich_team_members_with_environment_info_list, indent=2))
print("Step B: Done enriching team members.")

print("Creating Markdown document...")
output_file = f'{run_dir}/008-team.md'
create_markdown_document(plan_prompt, enrich_team_members_with_environment_info_list_file, output_file)
print("Done creating Markdown document.")
