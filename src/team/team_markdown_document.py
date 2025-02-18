"""
Create a Markdown document containing details about the team.

PROMPT> python -m src.team.team_markdown_document
"""
import json

class TeamMarkdownDocumentBuilder:
    """
    A class to build a Markdown document containing details about the team.
    """
    def __init__(self):
        self.rows = []

    def append_separator(self):
        self.rows.append("\n---\n")
    
    def append_plan_prompt(self, plan_prompt: str):
        """The main topic text to include in the Markdown"""
        self.rows.append("# The plan\n")
        self.rows.append(plan_prompt.strip())

    def append_role(self, entry: dict, role_index: int):
        self.rows.append(f"\n## {role_index}. {entry['category']}")
        if 'contract_type' in entry:
            self.rows.append(f"\n**Contract Type**: `{entry['contract_type']}`")
        if 'contract_type_justification' in entry:
            self.rows.append(f"\n**Contract Type Justification**: {entry['contract_type_justification']}")
        if 'explanation' in entry:
            self.rows.append(f"\n**Explanation**:\n{entry['explanation']}")
        if 'consequences' in entry:
            self.rows.append(f"\n**Consequences**:\n{entry['consequences']}")
        if 'count' in entry:
            self.rows.append(f"\n**People Count**:\n{entry['count']}")
        if 'typical_job_activities' in entry:
            self.rows.append(f"\n**Typical Activities**:\n{entry['typical_job_activities']}")
        if 'background_story' in entry:
            self.rows.append(f"\n**Background Story**:\n{entry['background_story']}")
        if 'equipment_needs' in entry:
            self.rows.append(f"\n**Equipment Needs**:\n{entry['equipment_needs']}")
        if 'facility_needs' in entry:
            self.rows.append(f"\n**Facility Needs**:\n{entry['facility_needs']}")
    
    def append_roles(self, roles_data: list[dict]):
        for entry_index, entry in enumerate(roles_data, start=1):
            self.append_role(entry, entry_index)

    def append_review_item(self, review_item: dict, review_index: int):
        issue = review_item.get('issue', "Review Item")
        self.rows.append(f"\n## {review_index}. {issue}")
        if 'explanation' in review_item:
            self.rows.append(f"\n{review_item['explanation']}")
        if 'recommendation' in review_item:
            self.rows.append(f"\n**Recommendation**:\n{review_item['recommendation']}")
    
    def append_review_items(self, review_items: list[dict]):
        for review_index, review_item in enumerate(review_items, start=1):
            self.append_review_item(review_item, review_index)
    
    def to_string(self) -> str:
        return "\n".join(self.rows)

    def write_to_file(self, output_file_path: str):
        markdown_representation = self.to_string()
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(markdown_representation)

if __name__ == "__main__":
    import os

    plan_prompt = "Establish a solar farm in Denmark."

    path1 = os.path.join(os.path.dirname(__file__), 'test_data', "solarfarm_roles_list.json")
    with open(path1, 'r', encoding='utf-8') as f:
        roles_list = json.load(f)

    path2 = os.path.join(os.path.dirname(__file__), 'test_data', "solarfarm_team_review.json")
    with open(path2, 'r', encoding='utf-8') as f:
        team_review = json.load(f)

    builder2 = TeamMarkdownDocumentBuilder()
    builder2.append_plan_prompt(plan_prompt)
    builder2.append_separator()
    builder2.rows.append(f"# Roles")
    builder2.append_roles(roles_list)
    builder2.append_separator()
    review_omissions = team_review.get('omissions', [])
    builder2.rows.append(f"# Omissions")
    builder2.append_review_items(review_omissions)
    builder2.append_separator()
    review_potential_improvements = team_review.get('potential_improvements', [])
    builder2.rows.append(f"# Potential Improvements")
    builder2.append_review_items(review_potential_improvements)

    print(builder2.to_string())
