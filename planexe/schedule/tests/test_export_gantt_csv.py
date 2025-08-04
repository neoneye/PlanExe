import unittest
from planexe.schedule.export_gantt_csv import ExportGanttCSV
from planexe.schedule.parse_schedule_input_data import parse_schedule_input_data
from planexe.schedule.schedule import ProjectSchedule
from planexe.utils.dedent_strip import dedent_strip

class TestExportGanttCSV(unittest.TestCase):
    def test_escape_cell(self):
        """Symbols that can break the CSV syntax."""
        f = ExportGanttCSV._escape_cell
        self.assertEqual(f("A"), "A")
        self.assertEqual(f("A:B"), "A:B")
        self.assertEqual(f("A;B"), "A_B")
        self.assertEqual(f("A'B"), "A_B")
        self.assertEqual(f("A\"B"), "A_B")
        self.assertEqual(f("A\nB"), "A\\nB")

    def test_to_gantt_csv(self):
        # Arrange
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
        activities = parse_schedule_input_data(input)
        for activity in activities:
            activity.title = f"Title{activity.id}"
        project_schedule = ProjectSchedule.create(activities)
        # Tooltips with dangerous symbols that can break the CSV syntax.
        task_id_to_tooltip_dict = {
            'A': 'A tooltip', 
            'B': 'Bline1\nBline2\nBline3', 
            'C': 'C;C;C', 
            'D': 'D:D:D',
            'E': 'E\nE\\nE\\\nE\\\\nE',
            'F': '"',
            'G': '\\"',
        }

        # Act
        s = ExportGanttCSV.to_gantt_csv(project_schedule, task_id_to_tooltip_dict)

        # Assert
        self.assertIn("project_key;project_name;project_description;project_start_date;project_end_date;project_progress;parent_project_key;originating_department", s)
        self.assertIn("A;TitleA;A tooltip;8/4/2025;8/7/2025;0;;PlanExe", s)
        self.assertIn("C;TitleC;C_C_C;8/4/2025;8/6/2025;0;A;PlanExe", s)
        self.assertIn("E;TitleE;E\\nE\\nE\\\\nE\\\\nE;8/6/2025;8/7/2025;0;C;PlanExe", s)
        self.assertIn("F;TitleF;_;8/7/2025;8/9/2025;0;C;PlanExe", s)
        self.assertIn("B;TitleB;Bline1\\nBline2\\nBline3;8/9/2025;8/11/2025;0;A;PlanExe", s)
        self.assertIn("D;TitleD;D:D:D;8/10/2025;8/14/2025;0;B;PlanExe", s)
        self.assertIn("G;TitleG;\\_;8/11/2025;8/15/2025;0;D;PlanExe", s)
        self.assertIn("H;TitleH;No description;8/15/2025;8/18/2025;0;F;PlanExe", s)