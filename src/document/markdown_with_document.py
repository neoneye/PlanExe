def markdown_rows_with_document_to_create(section_index: int, document_json: dict) -> list[str]:
    rows = []
    rows.append("")
    document_name = document_json.get('document_name', 'Missing document_name')
    rows.append(f"## Create Document {section_index}: {document_name}")
    rows.append("")

    # ID
    doc_id = document_json.get("id", "Missing id")
    rows.append(f"**ID**: {doc_id}")
    
    # Description
    description = document_json.get('description', 'Missing description')
    rows.append(f"\n**Description**: {description}")
    
    # Responsible Role Type
    responsible_role_type = document_json.get('responsible_role_type', 'Missing responsible_role_type')
    rows.append(f"\n**Responsible Role Type**: {responsible_role_type}")
    
    # Document Templates
    if 'document_template_primary' in document_json:
        doc_template_primary = document_json.get('document_template_primary', None)
        rows.append(f"\n**Primary Template**: {doc_template_primary}")
    
    if 'document_template_secondary' in document_json:
        doc_template_secondary = document_json.get('document_template_secondary', None)
        rows.append(f"\n**Secondary Template**: {doc_template_secondary}")
    
    # Steps to Create (list)
    steps_to_create = document_json.get('steps_to_create')
    if steps_to_create and isinstance(steps_to_create, list):
        rows.append("\n**Steps to Create**:\n")
        for step in steps_to_create:
            rows.append(f"- {step}")
    else:
        rows.append("\n**Steps to Create**: Missing steps_to_create")
    
    # Approval Authorities
    approval_authorities = document_json.get('approval_authorities', 'Missing approval_authorities')
    rows.append(f"\n**Approval Authorities**: {approval_authorities}")
    
    # Essential Information (list)
    essential_information = document_json.get('essential_information')
    if essential_information and isinstance(essential_information, list):
        rows.append("\n**Essential Information**:\n")
        for info in essential_information:
            rows.append(f"- {info}")
    else:
        rows.append("\n**Essential Information**: Missing essential_information")
    
    # Risks of Poor Quality (list)
    risks_of_poor_quality = document_json.get('risks_of_poor_quality')
    if risks_of_poor_quality and isinstance(risks_of_poor_quality, list):
        rows.append("\n**Risks of Poor Quality**:\n")
        for risk in risks_of_poor_quality:
            rows.append(f"- {risk}")
    else:
        rows.append("\n**Risks of Poor Quality**: Missing risks_of_poor_quality")
    
    # Worst Case Scenario
    worst_case_scenario = document_json.get('worst_case_scenario', 'Missing worst_case_scenario')
    rows.append(f"\n**Worst Case Scenario**: {worst_case_scenario}")
    
    # Best Case Scenario
    best_case_scenario = document_json.get('best_case_scenario', 'Missing best_case_scenario')
    rows.append(f"\n**Best Case Scenario**: {best_case_scenario}")
    
    # Fallback Alternative Approaches (list)
    fallback_alternative_approaches = document_json.get('fallback_alternative_approaches')
    if fallback_alternative_approaches and isinstance(fallback_alternative_approaches, list):
        rows.append("\n**Fallback Alternative Approaches**:\n")
        for approach in fallback_alternative_approaches:
            rows.append(f"- {approach}")
    else:
        rows.append("\n**Fallback Alternative Approaches**: Missing fallback_alternative_approaches")
    
    return rows

def markdown_rows_with_document_to_find(section_index: int, document_json: dict) -> list[str]:
    rows = []
    rows.append("")
    document_name = document_json.get('document_name', 'Missing document_name')
    rows.append(f"## Find Document {section_index}: {document_name}")
    rows.append("")

    # ID
    doc_id = document_json.get('id', 'Missing id')
    rows.append(f"**ID**: {doc_id}")
    
    # Description
    description = document_json.get('description', 'Missing description')
    rows.append(f"\n**Description**: {description}")
    
    # Recency Requirement
    recency_requirement = document_json.get('recency_requirement', 'Missing recency_requirement')
    rows.append(f"\n**Recency Requirement**: {recency_requirement}")
    
    # Responsible Role Type
    responsible_role_type = document_json.get('responsible_role_type', 'Missing responsible_role_type')
    rows.append(f"\n**Responsible Role Type**: {responsible_role_type}")
    
    # Steps to Find (list)
    steps_to_find = document_json.get('steps_to_find')
    if steps_to_find and isinstance(steps_to_find, list):
        rows.append("\n**Steps to Find**:\n")
        for step in steps_to_find:
            rows.append(f"- {step}")
    else:
        rows.append("\n**Steps to Find**: Missing steps_to_find")
    
    # Access Difficulty
    access_difficulty = document_json.get('access_difficulty', 'Missing access_difficulty')
    rows.append(f"\n**Access Difficulty**: {access_difficulty}")
    
    # Essential Information (list)
    essential_information = document_json.get('essential_information')
    if essential_information and isinstance(essential_information, list):
        rows.append("\n**Essential Information**:\n")
        for info in essential_information:
            rows.append(f"- {info}")
    else:
        rows.append("\n**Essential Information**: Missing essential_information")
    
    # Risks of Poor Quality (list)
    risks_of_poor_quality = document_json.get('risks_of_poor_quality')
    if risks_of_poor_quality and isinstance(risks_of_poor_quality, list):
        rows.append("\n**Risks of Poor Quality**:\n")
        for risk in risks_of_poor_quality:
            rows.append(f"- {risk}")
    else:
        rows.append("\n**Risks of Poor Quality**: Missing risks_of_poor_quality")
    
    # Worst Case Scenario
    worst_case_scenario = document_json.get('worst_case_scenario', 'Missing worst_case_scenario')
    rows.append(f"\n**Worst Case Scenario**: {worst_case_scenario}")
    
    # Best Case Scenario
    best_case_scenario = document_json.get('best_case_scenario', 'Missing best_case_scenario')
    rows.append(f"\n**Best Case Scenario**: {best_case_scenario}")
    
    # Fallback Alternative Approaches (list)
    fallback_alternative_approaches = document_json.get('fallback_alternative_approaches')
    if fallback_alternative_approaches and isinstance(fallback_alternative_approaches, list):
        rows.append("\n**Fallback Alternative Approaches**:\n")
        for approach in fallback_alternative_approaches:
            rows.append(f"- {approach}")
    else:
        rows.append("\n**Fallback Alternative Approaches**: Missing fallback_alternative_approaches")
    
    return rows
