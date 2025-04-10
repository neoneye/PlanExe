def markdown_rows_with_document_to_create(section_index: int, document_json: dict) -> list[str]:
    rows = []
    rows.append("")

    document_name = document_json.get('document_name', 'Missing document_name')
    rows.append(f"## Create Document {section_index}, {document_name}")

    description = document_json.get('description', 'Missing description')
    rows.append(f"\n{description}")

    responsible_role_type = document_json.get('responsible_role_type', 'Missing responsible_role_type')
    rows.append(f"\n**Responsible Role Type**: {responsible_role_type}")

    return rows

def markdown_rows_with_document_to_find(section_index: int, document_json: dict) -> list[str]:
    rows = []
    rows.append("")

    document_name = document_json.get('document_name', 'Missing document_name')
    rows.append(f"## Find Document {section_index}, {document_name}")

    description = document_json.get('description', 'Missing description')
    rows.append(f"\n{description}")

    responsible_role_type = document_json.get('responsible_role_type', 'Missing responsible_role_type')
    rows.append(f"\n**Responsible Role Type**: {responsible_role_type}")

    return rows 