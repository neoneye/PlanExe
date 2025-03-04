from enum import Enum

class FilenameEnum(str, Enum):
    INITIAL_PLAN = "001-plan.txt"
    PLAN_TYPE_RAW = "002-1-plan_type_raw.json"
    PHYSICAL_LOCATIONS_RAW = "002-2-physical_locations_raw.json"
    PHYSICAL_LOCATIONS_MARKDOWN = "002-3-physical_locations.md"
    CURRENCY_STRATEGY_RAW = "002-4-currency_strategy_raw.json"
    CURRENCY_STRATEGY_MARKDOWN = "002-5-currency_strategy.md"
    IDENTIFY_RISKS_RAW = "002-6-identify_risks_raw.json"
    IDENTIFY_RISKS_MARKDOWN = "002-7-identify_risks.md"
    MAKE_ASSUMPTIONS_RAW = "002-8-make_assumptions_raw.json"
    MAKE_ASSUMPTIONS_CLEAN = "002-9-make_assumptions.json"
    MAKE_ASSUMPTIONS_MARKDOWN = "002-10-make_assumptions.md"
    DISTILL_ASSUMPTIONS_RAW = "003-distill_assumptions.json"
    PRE_PROJECT_ASSESSMENT_RAW = "004-1-pre_project_assessment_raw.json"
    PRE_PROJECT_ASSESSMENT = "004-2-pre_project_assessment.json"
    PROJECT_PLAN = "005-project_plan.json"
    FIND_TEAM_MEMBERS_RAW = "006-1-find_team_members_raw.json"
    FIND_TEAM_MEMBERS_CLEAN = "006-2-find_team_members.json"
    ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_RAW = "007-1-enrich_team_members_contract_type_raw.json"
    ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_CLEAN = "007-2-enrich_team_members_contract_type.json"
    ENRICH_TEAM_MEMBERS_BACKGROUND_STORY_RAW = "008-1-enrich_team_members_background_story_raw.json"
    ENRICH_TEAM_MEMBERS_BACKGROUND_STORY_CLEAN = "008-2-enrich_team_members_background_story.json"
    ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_RAW = "009-1-enrich_team_members_environment_info_raw.json"
    ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_CLEAN = "009-2-enrich_team_members_environment_info.json"
    REVIEW_TEAM_RAW = "010-review_team_raw.json"
    TEAM_MARKDOWN = "011-team.md"
    SWOT_RAW = "012-1-swot_analysis_raw.json"
    SWOT_MARKDOWN = "012-2-swot_analysis.md"
    EXPERTS_RAW = "013-1-experts_raw.json"
    EXPERTS_CLEAN = "013-2-experts.json"
    EXPERT_CRITICISM_RAW_TEMPLATE = "014-1-{}-expert_criticism_raw.json"
    EXPERT_CRITICISM_MARKDOWN = "014-2-expert_criticism.md"
    WBS_LEVEL1_RAW = "015-1-wbs_level1_raw.json"
    WBS_LEVEL1 = "015-2-wbs_level1.json"
    WBS_LEVEL2_RAW = "016-1-wbs_level2_raw.json"
    WBS_LEVEL2 = "016-2-wbs_level2.json"
    WBS_PROJECT_LEVEL1_AND_LEVEL2 = "017-wbs_project_level1_and_level2.json"
    PITCH_RAW = "018-1-pitch_raw.json"
    PITCH_CONVERT_TO_MARKDOWN_RAW = "018-2-pitch_to_markdown_raw.json"
    PITCH_MARKDOWN = "018-3-pitch.md"
    TASK_DEPENDENCIES_RAW = "019-task_dependencies_raw.json"
    TASK_DURATIONS_RAW_TEMPLATE = "020-1-{}-task_durations_raw.json"
    TASK_DURATIONS = "020-2-task_durations.json"
    WBS_LEVEL3_RAW_TEMPLATE = "021-1-{}-wbs_level3_raw.json"
    WBS_LEVEL3 = "021-2-wbs_level3.json"
    WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_FULL = "021-3-wbs_project_level1_and_level2_and_level3.json"
    WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_CSV = "021-4-wbs_project_level1_and_level2_and_level3.csv"
    REPORT = "022-report.html"
    PIPELINE_COMPLETE = "999-pipeline_complete.txt"
