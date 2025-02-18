import json

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
    
    # Begin constructing the Markdown content
    rows = []
    
    # 1. Add the main text content as a top-level section
    rows.append("# The plan")
    rows.append("")
    rows.append(plan_prompt.strip())
    rows.append("")
    rows.append("---")
    rows.append("")
    
    # 2. Loop through each entry in the JSON and format as Markdown
    for entry in roles_data:
        # Each entry will be displayed under a subsection
        rows.append(f"## Role {entry['id']} - {entry['category']}")
        if 'explanation' in entry:
            rows.append("")
            rows.append(f"**Explanation**:\n{entry['explanation']}")
        if 'consequences' in entry:
            rows.append("")
            rows.append(f"**Consequences**:\n{entry['consequences']}")
        if 'count' in entry:
            rows.append("")
            rows.append(f"**People Count**:\n{entry['count']}")
        if 'typical_job_activities' in entry:
            rows.append("")
            rows.append(f"**Typical Activities**:\n{entry['typical_job_activities']}")
        if 'background_story' in entry:
            rows.append("")
            rows.append(f"**Background Story**:\n{entry['background_story']}")
        if 'equipment_needs' in entry:
            rows.append("")
            rows.append(f"**Equipment Needs**:\n{entry['equipment_needs']}")
        if 'facility_needs' in entry:
            rows.append("")
            rows.append(f"**Facility Needs**:\n{entry['facility_needs']}")
        rows.append("")
        rows.append("---")
        rows.append("")
    
    # Write everything to the output markdown file
    with open(output_file_path, 'w', encoding='utf-8') as out_f:
        out_f.write("\n".join(rows))
    
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