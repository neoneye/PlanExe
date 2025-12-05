def markdown_rows_with_info_about_one_expert(section_index: int, expert_detail_json: dict) -> list[str]:
    rows = []

    expert_title = expert_detail_json.get('title', 'Missing title')
    rows.append(f"# {section_index} Expert: {expert_title}")

    expert_knowledge = expert_detail_json.get('knowledge', 'Missing knowledge')
    rows.append(f"\n**Knowledge**: {expert_knowledge}")

    expert_why = expert_detail_json.get('why', 'Missing why')
    rows.append(f"\n**Why**: {expert_why}")

    expert_what = expert_detail_json.get('what', 'Missing what')
    rows.append(f"\n**What**: {expert_what}")

    expert_skills = expert_detail_json.get('skills', 'Missing skills')
    rows.append(f"\n**Skills**: {expert_skills}")

    expert_search_query = expert_detail_json.get('search_query', 'Missing search_query')
    rows.append(f"\n**Search**: {expert_search_query}")

    return rows

def markdown_rows_with_criticism_from_one_expert(section_index: int, expert_criticism_json: dict) -> list[str]:
    rows = []

    rows.append("")
    user_primary_actions = expert_criticism_json.get('user_primary_actions', None)
    rows.append(f"## {section_index}.1 Primary Actions\n")
    if isinstance(user_primary_actions, list) and len(user_primary_actions) > 0:
        for action in user_primary_actions:
            rows.append(f"- {action}")
    else:
        rows.append("Empty")

    user_secondary_actions = expert_criticism_json.get('user_secondary_actions', None)
    rows.append(f"\n## {section_index}.2 Secondary Actions\n")
    if isinstance(user_secondary_actions, list) and len(user_secondary_actions) > 0:
        for action in user_secondary_actions:
            rows.append(f"- {action}")
    else:
        rows.append("Empty")

    follow_up_consultation = expert_criticism_json.get('follow_up_consultation', None)
    rows.append(f"\n## {section_index}.3 Follow Up Consultation\n")
    if follow_up_consultation:
        rows.append(follow_up_consultation)
    else:
        rows.append("Empty")

    start_subsection_index = 4
    negative_feedback_list = expert_criticism_json.get('negative_feedback_list', [])
    for feedback_index, feedback_item in enumerate(negative_feedback_list):
        rows.append("")

        subsection_index = start_subsection_index + feedback_index
        prefix_a = f"{section_index}.{subsection_index}.A"
        prefix_b = f"{section_index}.{subsection_index}.B"
        prefix_c = f"{section_index}.{subsection_index}.C"
        prefix_d = f"{section_index}.{subsection_index}.D"
        prefix_e = f"{section_index}.{subsection_index}.E"
        
        title = feedback_item.get('feedback_title', 'Missing feedback_title')
        feedback_verbose = feedback_item.get('feedback_verbose', 'Missing feedback_verbose')
        rows.append(f"## {prefix_a} Issue - {title}\n")
        rows.append(feedback_verbose)

        problem_tag_list = feedback_item.get('feedback_problem_tags', None)
        rows.append(f"\n### {prefix_b} Tags\n")
        if isinstance(problem_tag_list, list) and len(problem_tag_list) > 0:
            for tag in problem_tag_list:
                rows.append(f"- {tag}")
        else:
            rows.append("Empty")

        feedback_mitigation = feedback_item.get('feedback_mitigation', None)
        rows.append(f"\n### {prefix_c} Mitigation\n")
        if feedback_mitigation:
            rows.append(feedback_mitigation)
        else:
            rows.append("Empty")

        feedback_consequence = feedback_item.get('feedback_consequence', None)
        rows.append(f"\n### {prefix_d} Consequence\n")
        if feedback_consequence:
            rows.append(feedback_consequence)
        else:
            rows.append("Empty")

        feedback_root_cause = feedback_item.get('feedback_root_cause', None)
        rows.append(f"\n### {prefix_e} Root Cause\n")
        if feedback_root_cause:
            rows.append(feedback_root_cause)
        else:
            rows.append("Empty")

    return rows