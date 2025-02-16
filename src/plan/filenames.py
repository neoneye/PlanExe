from enum import Enum

class FilenameEnum(str, Enum):
    INITIAL_PLAN = "001-plan.txt"
    MAKE_ASSUMPTIONS_RAW = "002-1-make_assumptions_raw.json"
    MAKE_ASSUMPTIONS = "002-2-make_assumptions.json"
    DISTILL_ASSUMPTIONS_RAW = "003-distill_assumptions.json"
    PRE_PROJECT_ASSESSMENT_RAW = "004-1-pre_project_assessment_raw.json"
    PRE_PROJECT_ASSESSMENT = "004-2-pre_project_assessment.json"
    PROJECT_PLAN = "005-project_plan.json"
    SWOT_RAW = "006-1-swot_analysis_raw.json"
    SWOT_MARKDOWN = "006-2-swot_analysis.md"
    EXPERTS_RAW = "007-1-experts_raw.json"
    EXPERTS_CLEAN = "007-2-experts.json"
    EXPERT_CRITICISM_RAW_TEMPLATE = "008-1-{}-expert_criticism_raw.json"
    EXPERT_CRITICISM_MARKDOWN = "008-2-expert_criticism.md"
    WBS_LEVEL1_RAW = "009-1-wbs_level1_raw.json"
    WBS_LEVEL1 = "009-2-wbs_level1.json"
    WBS_LEVEL2_RAW = "010-1-wbs_level2_raw.json"
    WBS_LEVEL2 = "010-2-wbs_level2.json"
    WBS_PROJECT_LEVEL1_AND_LEVEL2 = "011-wbs_project_level1_and_level2.json"
    PITCH_RAW = "012-1-pitch_raw.json"
    PITCH_CONVERT_TO_MARKDOWN_RAW = "012-2-pitch_to_markdown_raw.json"
    PITCH_MARKDOWN = "012-3-pitch.md"
    TASK_DEPENDENCIES_RAW = "013-task_dependencies_raw.json"
    TASK_DURATIONS_RAW_TEMPLATE = "014-1-{}-task_durations_raw.json"
    TASK_DURATIONS = "014-2-task_durations.json"
    WBS_LEVEL3_RAW_TEMPLATE = "015-1-{}-wbs_level3_raw.json"
    WBS_LEVEL3 = "015-2-wbs_level3.json"
    WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_FULL = "015-3-wbs_project_level1_and_level2_and_level3.json"
    WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_CSV = "015-4-wbs_project_level1_and_level2_and_level3.csv"
    REPORT = "016-report.html"
    PIPELINE_COMPLETE = "999-pipeline_complete.txt"
