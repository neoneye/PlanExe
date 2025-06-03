import unittest
from decimal import Decimal as D
from src.utils.dedent_strip import dedent_strip
from src.schedule.schedule import ProjectSchedule
from src.schedule.parse_schedule_input_data import parse_schedule_input_data

class TestSchedule(unittest.TestCase):
    def test_textbook_example_all_dependency_types(self):
        """
        As shown in the video:
        "Difficult network diagram example with lag solved" by "Engineer4Free" 
        https://www.youtube.com/watch?v=qTErIV6OqLg
        """
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

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;3;0;3;0;3;0
            B;2;5;7;5;7;0
            C;2;0;2;4;6;4
            D;4;6;10;6;10;0
            E;1;2;3;6;7;4
            F;2;3;5;12;14;9
            G;4;7;11;7;11;0
            H;3;11;14;11;14;0
        """)

        self.assertEqual(str(project_schedule), expected)
        self.assertEqual(project_schedule.project_duration, D("14"))
        self.assertListEqual(project_schedule.obtain_critical_path(), ["A", "B", "D", "G", "H"])

    def test_textbook_example_two_start_nodes_and_two_end_nodes(self):
        """
        As shown in the video:
        "Project Scheduling - PERT/CPM | Finding Critical Path" by "Joshua Emmanuel"
        https://www.youtube.com/watch?v=-TDh-5n90vk
        """
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;7
            B;-;9
            C;A(FS);12
            D;A(FS),B(FS);8
            E;D(FS);9
            F;C(FS),E(FS);6
            G;E(FS);5
        """)

        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;7;0;7;2;9;2
            B;9;0;9;0;9;0
            C;12;7;19;14;26;7
            D;8;9;17;9;17;0
            E;9;17;26;17;26;0
            F;6;26;32;26;32;0
            G;5;26;31;27;32;1
        """)

        self.assertEqual(str(project_schedule), expected)
        self.assertEqual(project_schedule.project_duration, D("32"))
        self.assertListEqual(project_schedule.obtain_critical_path(), ["B", "D", "E", "F"])

    def test_textbook_example_of_lags1(self):
        """
        As shown in the video:
        "Lags Part 1" by "James Marion"
        https://www.youtube.com/watch?v=nhRTJBQ1NPM
        """
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;2
            B;A(FS5);4
            C;B(SS3);3
            D;B(FS);5
            E;C(FS),D(FS);2
        """)

        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;2;0;2;0;2;0
            B;4;7;11;7;11;0
            C;3;10;13;13;16;3
            D;5;11;16;11;16;0
            E;2;16;18;16;18;0
        """)

        self.assertEqual(str(project_schedule), expected)
        self.assertEqual(project_schedule.project_duration, D("18"))
        self.assertListEqual(project_schedule.obtain_critical_path(), ["A", "B", "D", "E"])

    def test_textbook_example_of_lags2(self):
        """
        As shown in the video:
        "Lags Part 2" by "James Marion"
        https://www.youtube.com/watch?v=lQtpnHzvTT8
        """
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;2
            B;A(FS);2
            C;A(FS);4
            D;B(FS),C(SF7);3
            E;C(FS);3
            F;D(FF3),E(FS);1                 
        """)

        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;2;0;2;0;2;0
            B;2;2;4;4;6;2
            C;4;2;6;2;6;0
            D;3;6;9;6;9;0
            E;3;6;9;8;11;2
            F;1;11;12;11;12;0
        """)

        self.assertEqual(str(project_schedule), expected)
        self.assertEqual(project_schedule.project_duration, D("12"))
        self.assertListEqual(project_schedule.obtain_critical_path(), ["A", "C", "D", "F"])

    def test_fractional_durations_and_lags(self):
        """Simple chain with fractional numbers to verify decimal math."""

        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;1.5
            B;A(FS0.75);2.25
        """)
        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;1.5;0;1.5;0;1.5;0
            B;2.25;2.25;4.5;2.25;4.5;0
        """)

        self.assertEqual(str(project_schedule), expected) 
        self.assertEqual(project_schedule.project_duration, D("4.5"))

    def test_cycle_detection(self):
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;B;1
            B;A;1
        """)
        with self.assertRaises(RuntimeError):
            ProjectSchedule.create(parse_schedule_input_data(input))

    def test_dependency_type_finish_to_start_no_lag(self):
        """
        Waterfall.
        FS = Finish to Start
        """
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;1
            B;A(FS);1
            C;B(FS);1
            D;C(FS);1
        """)
        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;1;0;1;0;1;0
            B;1;1;2;1;2;0
            C;1;2;3;2;3;0
            D;1;3;4;3;4;0
        """)

        self.assertEqual(str(project_schedule), expected) 
        self.assertEqual(project_schedule.project_duration, D("4"))

    def test_dependency_type_finish_to_start(self):
        """FS = Finish to Start"""
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;3
            B;A(FS2);4
        """)
        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;3;0;3;0;3;0
            B;4;5;9;5;9;0
        """)

        self.assertEqual(str(project_schedule), expected) 
        self.assertEqual(project_schedule.project_duration, D("9"))

    def test_dependency_type_finish_to_finish(self):
        """FF = Finish to Finish"""
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;3
            B;A(FF2);4
        """)
        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;3;0;3;0;3;0
            B;4;1;5;1;5;0
        """)

        self.assertEqual(str(project_schedule), expected) 
        self.assertEqual(project_schedule.project_duration, D("5"))

    def test_dependency_type_start_to_finish(self):
        """SF = Start to Finish"""
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;3
            B;A(SF6);4
        """)
        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;3;0;3;0;3;0
            B;4;2;6;2;6;0
        """)

        self.assertEqual(str(project_schedule), expected) 
        self.assertEqual(project_schedule.project_duration, D("6"))

    def test_dependency_type_start_to_start(self):
        """SS = Start to Start"""
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;3
            B;A(SS2);4
        """)
        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;3;0;3;0;3;0
            B;4;2;6;2;6;0
        """)

        self.assertEqual(str(project_schedule), expected) 
        self.assertEqual(project_schedule.project_duration, D("6"))                

    def test_multiple_relationships_between_two_activities(self):
        input_data = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;4
            B;A(SS),A(FF2);3
        """)

        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input_data))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;4;0;4;0;4;0
            B;3;3;6;3;6;0
        """)

        self.assertEqual(str(project_schedule), expected)
        self.assertEqual(project_schedule.project_duration, D("6"))
        self.assertListEqual(project_schedule.obtain_critical_path(), ["A", "B"])

    def test_to_csv_sort_by_duration(self):
        """Ensure sorting by dataclass field like 'duration' works."""
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;2
            B;-;5
            C;-;3
        """)

        project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))
        csv_output = project_schedule.to_csv(sort_by="duration")
        durations = [line.split(";")[1] for line in csv_output.splitlines()[1:]]
        self.assertEqual(durations, ["2", "3", "5"])

if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
