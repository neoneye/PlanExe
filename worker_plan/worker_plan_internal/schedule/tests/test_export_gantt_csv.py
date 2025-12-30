import unittest
from datetime import date
from worker_plan_internal.schedule.export_gantt_csv import ExportGanttCSV
from worker_plan_internal.schedule.parse_schedule_input_data import parse_schedule_input_data
from worker_plan_internal.schedule.schedule import ProjectSchedule
from worker_plan_internal.utils.dedent_strip import dedent_strip

class TestExportGanttCSV(unittest.TestCase):
    def test_to_gantt_csv_without_duplicate_names(self):
        # Arrange
        input_str = dedent_strip("""
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
        activities = parse_schedule_input_data(input_str)
        for activity in activities:
            activity.title = f"Title{activity.id}"
        project_schedule = ProjectSchedule.create(activities)
        # Tooltips with dangerous symbols that can break the CSV syntax.
        task_id_to_tooltip_dict = {
            'A': 'A tooltip', 
            'B': 'Bline1\nBline2\nBline3', 
            'C': 'C;C,C', 
            'D': 'TitleD',
            'E': 'E\nE\\nE\\\nE\\\\nE',
            'F': '"',
            'G': '\\"',
        }
        project_start = date(2025, 8, 4)

        # Act
        s = ExportGanttCSV.to_gantt_csv(project_schedule, project_start, task_id_to_tooltip_dict)

        # Assert
        lines = [
            "project_key,project_name,project_description,project_start_date,project_end_date,project_progress,project_parent,originating_department",
            "A,TitleA,A tooltip,8/4/2025,8/7/2025,0,,PlanExe",
            'C,TitleC,"C;C,C",8/4/2025,8/6/2025,0,A,PlanExe',
            'E,TitleE,"E\nE\\nE\\\nE\\\\nE",8/6/2025,8/7/2025,0,C,PlanExe',
            'F,TitleF,"""",8/7/2025,8/9/2025,0,C,PlanExe',
            'B,TitleB,"Bline1\nBline2\nBline3",8/9/2025,8/11/2025,0,A,PlanExe',
            "D,TitleD,,8/10/2025,8/14/2025,0,B,PlanExe",
            'G,TitleG,"\\""",8/11/2025,8/15/2025,0,D,PlanExe',
            "H,TitleH,No description,8/15/2025,8/18/2025,0,F,PlanExe",
        ]
        expected_csv = "\n".join(lines) + "\n"
        self.assertEqual(s, expected_csv)

    def test_to_gantt_csv_with_duplicate_names(self):
        """
        The 'Title' is duplicated, and thus gets suffixes (1), (2), (3), etc.
        """
        # Arrange
        input_str = dedent_strip("""
            Activity;Predecessor;Duration;Comment
            A;-;1;Start node
            B;A(FS);1;
            C;B(FS);1;
            D;C(FS);1;
        """)
        activities = parse_schedule_input_data(input_str)
        for activity in activities:
            activity.title = "Title"
        project_schedule = ProjectSchedule.create(activities)
        task_id_to_tooltip_dict = {}
        project_start = date(1984, 1, 1)

        # Act
        s = ExportGanttCSV.to_gantt_csv(project_schedule, project_start, task_id_to_tooltip_dict)

        # Assert
        lines = [
            "project_key,project_name,project_description,project_start_date,project_end_date,project_progress,project_parent,originating_department",
            "A,Title (1),No description,1/1/1984,1/2/1984,0,,PlanExe",
            "B,Title (2),No description,1/2/1984,1/3/1984,0,A,PlanExe",
            "C,Title (3),No description,1/3/1984,1/4/1984,0,B,PlanExe",
            "D,Title (4),No description,1/4/1984,1/5/1984,0,C,PlanExe",
        ]
        expected_csv = "\n".join(lines) + "\n"
        self.assertEqual(s, expected_csv)
