"""
CSV serialization of the gantt chart data.

This module uses pandas to generate CSV output. The separator is a comma,
and fields containing special characters (like commas or newlines) are
quoted according to standard CSV conventions.

In my opinion CSV is a terrible format for PlanExe data.
Extra data about the tasks aren't stored in the CSV file.
For proper serialization/deserialization then json or xml will be a better choice.

PROMPT> python -m planexe.schedule.export_gantt_csv
"""
from datetime import date, timedelta
import pandas as pd
from planexe.schedule.schedule import ProjectSchedule
from planexe.utils.enumerate_duplicate_strings import enumerate_duplicate_strings

class ExportGanttCSV:
    @staticmethod
    def to_gantt_csv(
        project_schedule: ProjectSchedule,
        project_start: date,
        task_id_to_tooltip_dict: dict[str, str]
    ) -> str:
        if not isinstance(project_schedule, ProjectSchedule):
            raise ValueError("project_schedule must be a ProjectSchedule")
        if not isinstance(project_start, date):
            raise ValueError("project_start must be a date")
        if not isinstance(task_id_to_tooltip_dict, dict):
            raise ValueError("task_id_to_tooltip_dict must be a dict")

        # Enumerate duplicate activity titles.
        # Duplicated gets assigned a suffix like this: (1), (2), (3), etc.
        id_to_name_with_possible_duplicates: dict[str, str] = {}
        activities = sorted(project_schedule.activities.values(), key=lambda a: a.es)
        for act in activities:
            id_to_name_with_possible_duplicates[act.id] = act.title or act.id
        id_to_name_without_duplicates = enumerate_duplicate_strings(id_to_name_with_possible_duplicates)
        
        data_rows: list[dict[str, str]] = []
        # order tasks by early‑start so the chart looks natural
        activities = sorted(project_schedule.activities.values(), key=lambda a: a.es)
        for act_index, act in enumerate(activities, start=1):
            activity_start = project_start + timedelta(days=float(act.es))
            activity_end = activity_start + timedelta(days=float(act.duration))

            project_name = id_to_name_without_duplicates.get(act.id, f'{act.id} ({act_index})')
            project_description = task_id_to_tooltip_dict.get(act.id, "No description")

            # This is a kludge solution. Use the first predecessor as the parent, ignore the rest.
            # This is the shortcoming of using CSV and not json or xml.
            parent_id = None
            for pred in act.parsed_predecessors:
                parent_id = pred.activity_id
                break

            project_key = act.id

            # No need for a description when it's the identical to the the name.
            if project_description == project_name:
                project_description = ""

            project_start_date = activity_start.strftime("%-m/%-d/%Y")
            project_end_date = activity_end.strftime("%-m/%-d/%Y")
            project_progress = "0"
            project_parent = ""
            originating_department = "PlanExe"

            if parent_id is not None:
                parent_activity = project_schedule.activities.get(parent_id)
                if parent_activity is not None:
                    project_parent = parent_activity.id

            data_rows.append({
                "project_key": project_key,
                "project_name": project_name,
                "project_description": project_description,
                "project_start_date": project_start_date,
                "project_end_date": project_end_date,
                "project_progress": project_progress,
                "project_parent": project_parent,
                "originating_department": originating_department,
            })

        df = pd.DataFrame(data_rows)
        return df.to_csv(sep=',', index=False, lineterminator='\n')

    @staticmethod
    def save(project_schedule: ProjectSchedule, path: str, project_start: date, task_id_to_tooltip_dict: dict[str, str]) -> None:
        csv_text = ExportGanttCSV.to_gantt_csv(project_schedule, project_start, task_id_to_tooltip_dict)
        with open(path, "w", encoding="utf-8") as f:
            f.write(csv_text)

if __name__ == "__main__":
    from planexe.schedule.parse_schedule_input_data import parse_schedule_input_data
    from planexe.schedule.schedule import ProjectSchedule
    from planexe.utils.dedent_strip import dedent_strip

    input = dedent_strip("""
        Activity;Predecessor;Duration;Comment
        A;-;1;Start node
        B;A(FS);2;
        C;B(FS);3;
    """)
    project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))
    task_id_to_tooltip_dict = {
        'A': 'TooltipA', 
        'B': 'TooltipB', 
        'C': 'TooltipC', 
    }
    project_start = date(1984, 12, 30)
    ExportGanttCSV.save(project_schedule, "gantt.csv", project_start, task_id_to_tooltip_dict) 