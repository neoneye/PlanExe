"""
CSV serialization of the gantt chart data.

In my opinion CSV is a terrible format for PlanExe data.
With CSV it's uncertain what symbols are allowed. So I'm purging the symbols that are known to break the CSV syntax.
Extra data about the tasks aren't stored in the CSV file.
For proper serialization/deserialization then json or xml will be a better choice.

PROMPT> python -m planexe.schedule.export_gantt_csv
"""
from datetime import date, timedelta
from planexe.schedule.schedule import ProjectSchedule

class ExportGanttCSV:
    @staticmethod
    def _escape_cell(text: str) -> str:
        """Replace characters that could break CSV syntax."""
        text = text.replace(';', '_')
        text = text.replace('\'', '_')
        text = text.replace('\"', '_')
        text = text.replace('\n', '\\n')
        return text
    
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

        separator = ";"

        column_names: list[str] = [
            "project_key",
            "project_name",
            "project_description",
            "project_start_date",
            "project_end_date",
            "project_progress",
            "project_parent",
            "originating_department",
        ]
        row0 = separator.join(column_names)
        rows: list[str] = [row0]

        # order tasks by early‑start so the chart looks natural
        activities = sorted(project_schedule.activities.values(), key=lambda a: a.es)
        for act in activities:
            activity_start = project_start + timedelta(days=float(act.es))
            activity_end = activity_start + timedelta(days=float(act.duration))

            project_name_raw = act.title if act.title else act.id
            project_description_raw = task_id_to_tooltip_dict.get(act.id, "No description")

            # This is a kludge solution. Use the first predecessor as the parent, ignore the rest.
            # This is the shortcoming of using CSV and not json or xml.
            parent_id = None
            for pred in act.parsed_predecessors:
                parent_id = pred.activity_id
                break

            project_key = act.id
            project_name = ExportGanttCSV._escape_cell(project_name_raw)
            project_description = ExportGanttCSV._escape_cell(project_description_raw)

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

            column_values: list[str] = [
                project_key,
                project_name,
                project_description,
                project_start_date,
                project_end_date,
                project_progress,
                project_parent,
                originating_department,
            ]
            row = separator.join(column_values)
            rows.append(row)

        return "\n".join(rows)

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