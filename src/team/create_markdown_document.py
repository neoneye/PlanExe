import json

class TeamMarkdownDocumentBuilder:
    def __init__(self):
        self.rows = []

    def append_plan_prompt(self, plan_prompt: str):
        """The main topic text to include in the Markdown"""
        self.rows.append("# The plan\n")
        self.rows.append(plan_prompt.strip())
        self.rows.append("\n---\n")

    def append_role(self, entry: dict):
        self.rows.append(f"## Role {entry['id']} - {entry['category']}")
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
        self.rows.append("\n---\n")
    
    def append_roles(self, roles_data: list[dict]):
        for entry in roles_data:
            self.append_role(entry)
    
    def to_string(self) -> str:
        return "\n".join(self.rows)

    def write_to_file(self, output_file_path: str):
        markdown_representation = self.to_string()
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(markdown_representation)

def create_markdown_document(plan_prompt: str, team_member_list_json_file_path: str, output_file_path: str):
    """
    Reads text content and JSON data, then writes a Markdown document.
    
    :param text_content: str, the main topic text to include in the Markdown
    :param json_file_path: str, path to the JSON file
    :param output_file_path: str, path to output the generated Markdown file
    """
    # Load JSON data
    with open(team_member_list_json_file_path, 'r', encoding='utf-8') as f:
        roles_data = json.load(f)
    
    builder = TeamMarkdownDocumentBuilder()

    builder.append_plan_prompt(plan_prompt)
    builder.append_roles(roles_data)

    builder.write_to_file(output_file_path)
    
    print(f"Markdown document has been created at: {output_file_path}")


if __name__ == "__main__":
    # Your text snippet
    plan_prompt = "Deep cave exploration to find new lifeforms in extreme conditions."
    
    # Path to your JSON file
    # TODO: Eliminate hardcoded paths
    json_path = "/Users/neoneye/Desktop/planexe_data/005-enriched_team_members_list.json"
    
    # Output Markdown file path
    output_path = "output.md"
    
    # Create the markdown document
    create_markdown_document(plan_prompt, json_path, output_path)