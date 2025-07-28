"""
PROMPT> python -m planexe.schedule.export_gantt_to_csv
"""
from datetime import date, timedelta
from planexe.schedule.schedule import ProjectSchedule, PredecessorInfo

class ExportGanttToCSV:
    @staticmethod
    def _escape_cell(text: str) -> str:
        """Replace characters that could break CSV syntax."""
        text = text.replace(':', '\\:')
        text = text.replace(';', '\\;')
        return text
    
    @staticmethod
    def to_gantt_to_csv(
        project_schedule: ProjectSchedule
    ) -> str:
        project_start = date.today()

        separator = ";"


        column_names: list[str] = [
            "project_key",
            "project_name",
            "originating_department",
            "project_description",
            "project_start_date",
            "project_end_date",
            "project_progress",
            "parent_project_key",
            "parent_project_name",
            "dependent_on_parent_project_key",
        ]
        row0 = separator.join(column_names)
        rows: list[str] = [row0]

        # order tasks by early‑start so the chart looks natural
        activities = sorted(project_schedule.activities.values(), key=lambda a: a.es)
        for index, act in enumerate(activities, start=1):
            start   = project_start + timedelta(days=float(act.es))
            dur_txt = f"{int(act.duration)}d" if act.duration % 1 == 0 else f"{act.duration}d"

            name = act.title if act.title else act.id
            label = ExportGanttToCSV._escape_cell(name)

            # Use the first predecessor as the parent, Ignore the rest.
            parent_id = None
            for pred in act.parsed_predecessors:
                parent_id = pred.activity_id
                break
            # print(f"parent_id: {parent_id}")

            project_key = act.id
            project_name = "Sample Upload Project 1"
            originating_department = "PlanExe Team"
            project_description = label
            project_start_date = start.strftime("%-m/%-d/%Y")
            project_end_date = (start + timedelta(days=float(act.duration))).strftime("%-m/%-d/%Y")
            project_progress = "0"
            parent_project_key = ""
            parent_project_name = ""
            dependent_on_parent_project_key = ""

            if parent_id is not None:
                parent_activity = project_schedule.activities.get(parent_id)
                if parent_activity is not None:
                    parent_project_key = parent_activity.id
                    parent_project_name_raw = parent_activity.title if parent_activity.title else parent_activity.id
                    parent_project_name = ExportGanttToCSV._escape_cell(parent_project_name_raw)
                    dependent_on_parent_project_key = parent_activity.id

            column_values: list[str] = [
                project_key,
                project_name,
                originating_department,
                project_description,
                project_start_date,
                project_end_date,
                project_progress,
                parent_project_key,
                parent_project_name,
                dependent_on_parent_project_key,
            ]
            row = separator.join(column_values)
            rows.append(row)

        return "\n".join(rows)

    @staticmethod
    def save(project_schedule: ProjectSchedule, path: str, **kwargs) -> None:
        csv_text = ExportGanttToCSV.to_gantt_to_csv(project_schedule)
        with open(path, "w", encoding="utf-8") as f:
            f.write(csv_text)

if __name__ == "__main__":
    from planexe.schedule.parse_schedule_input_data import parse_schedule_input_data
    from planexe.schedule.schedule import ProjectSchedule
    from planexe.utils.dedent_strip import dedent_strip

    input = dedent_strip("""
        Activity;Predecessor;Duration;Comment
        A;-;3;Start node
        B;A(FS2);2;
        C;A(SS);2; C starts when A starts
        D;B(SS1);4; D starts 1 after B starts
        E;C(SF3);1; E starts 3 after C finishes (E_ef >= C_es + 3)? No SF is Start-Finish E_lf >= C_es + lag + E_dur
        F;C(FF3);2; F finishes 3 after C finishes
        G;D(SS1),E;4;Multiple preds (E is FS default)
        H;F(SF2),G;3;Multiple preds (G is FS default)
    """)

    project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))
    ExportGanttToCSV.save(project_schedule, "gantt.csv") 