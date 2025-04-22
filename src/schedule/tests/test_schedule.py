import unittest
from decimal import Decimal
from decimal import Decimal as D
from src.utils.dedent_strip import dedent_strip
from typing import Dict, List
import re
import pandas as pd
from io import StringIO
from src.schedule.schedule import Activity, PredecessorInfo, DependencyType, ProjectPlan, ZERO

# ────────────────────────────────────────────────────────────────────────────────
#  Parsing helpers
# ----------------------------------------------------------------------------
_DEF_RE = re.compile(r"(\w+)(?:\(([SF]{2})([-+]?\d+(?:\.\d+)?)?\))?", re.IGNORECASE)


def parse_dependency(dep_str: str) -> PredecessorInfo:
    dep_str = dep_str.strip()
    m = _DEF_RE.fullmatch(dep_str)
    if not m:
        raise ValueError(f"Invalid dependency format: {dep_str}")
    act_id, dep_type_str, lag_str = m.groups()
    dep_type = DependencyType(dep_type_str.upper()) if dep_type_str else DependencyType.FS
    lag = Decimal(lag_str) if lag_str else ZERO
    return PredecessorInfo(activity_id=act_id, dep_type=dep_type, lag=lag)

# -----------------------------------------------------------------------------
#  Main input parser (semicolon‑separated data)
# -----------------------------------------------------------------------------

def parse_input_data(data: str) -> List[Activity]:
    """Parse a semicolon‑separated text block into ``Activity`` objects."""
    df = pd.read_csv(
        StringIO(data),
        sep=";",
        comment="#",
        dtype=str,
        keep_default_na=False,
    )

    # normalise column names
    df.columns = df.columns.str.strip().str.lower()
    required = {"activity", "predecessor", "duration"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    # duplication early exit
    if df["activity"].duplicated(keep=False).any():
        dups = df.loc[df["activity"].duplicated(keep=False), "activity"].tolist()
        raise ValueError(f"Duplicate activity IDs: {', '.join(dups)}")

    activities: Dict[str, Activity] = {}

    for _, row in df.iterrows():
        act_id = row["activity"].strip()
        duration_str = row["duration"].strip()
        if duration_str == "":
            raise ValueError(f"Duration empty for activity {act_id}")
        try:
            duration = Decimal(duration_str)
        except Exception:
            raise ValueError(f"Non‑numeric duration for activity {act_id}: '{duration_str}'")
        if duration <= ZERO:
            raise ValueError(f"Duration must be positive for {act_id}")

        pred_str = row["predecessor"].strip() or "-"
        act = Activity(id=act_id, duration=duration, predecessors_str=pred_str)

        if pred_str != "-":
            for item in pred_str.split(","):
                act.parsed_predecessors.append(parse_dependency(item))

        activities[act_id] = act

    return list(activities.values())

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

        plan = ProjectPlan.create(parse_input_data(input))

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

        self.assertEqual(str(plan), expected)
        self.assertEqual(plan.project_duration, D("14"))
        self.assertListEqual(plan.obtain_critical_path(), ["A", "B", "D", "G", "H"])

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

        plan = ProjectPlan.create(parse_input_data(input))

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

        self.assertEqual(str(plan), expected)
        self.assertEqual(plan.project_duration, D("32"))
        self.assertListEqual(plan.obtain_critical_path(), ["B", "D", "E", "F"])

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

        plan = ProjectPlan.create(parse_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;2;0;2;0;2;0
            B;4;7;11;7;11;0
            C;3;10;13;13;16;3
            D;5;11;16;11;16;0
            E;2;16;18;16;18;0
        """)

        self.assertEqual(str(plan), expected)
        self.assertEqual(plan.project_duration, D("18"))
        self.assertListEqual(plan.obtain_critical_path(), ["A", "B", "D", "E"])

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

        plan = ProjectPlan.create(parse_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;2;0;2;0;2;0
            B;2;2;4;4;6;2
            C;4;2;6;2;6;0
            D;3;6;9;6;9;0
            E;3;6;9;8;11;2
            F;1;11;12;11;12;0
        """)

        self.assertEqual(str(plan), expected)
        self.assertEqual(plan.project_duration, D("12"))
        self.assertListEqual(plan.obtain_critical_path(), ["A", "C", "D", "F"])

    def test_fractional_durations_and_lags(self):
        """Simple chain with fractional numbers to verify decimal math."""

        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;1.5
            B;A(FS0.75);2.25
        """)
        plan = ProjectPlan.create(parse_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;1.5;0;1.5;0;1.5;0
            B;2.25;2.25;4.5;2.25;4.5;0
        """)

        self.assertEqual(str(plan), expected) 
        self.assertEqual(plan.project_duration, D("4.5"))

    def test_cycle_detection(self):
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;B;1
            B;A;1
        """)
        with self.assertRaises(RuntimeError):
            ProjectPlan.create(parse_input_data(input))

    def test_dependency_type_finish_to_start(self):
        """FS = Finish to Start"""
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;3
            B;A(FS2);4
        """)
        plan = ProjectPlan.create(parse_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;3;0;3;0;3;0
            B;4;5;9;5;9;0
        """)

        self.assertEqual(str(plan), expected) 
        self.assertEqual(plan.project_duration, D("9"))

    def test_dependency_type_finish_to_finish(self):
        """FF = Finish to Finish"""
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;3
            B;A(FF2);4
        """)
        plan = ProjectPlan.create(parse_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;3;0;3;0;3;0
            B;4;1;5;1;5;0
        """)

        self.assertEqual(str(plan), expected) 
        self.assertEqual(plan.project_duration, D("5"))

    def test_dependency_type_start_to_finish(self):
        """SF = Start to Finish"""
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;3
            B;A(SF6);4
        """)
        plan = ProjectPlan.create(parse_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;3;0;3;0;3;0
            B;4;2;6;2;6;0
        """)

        self.assertEqual(str(plan), expected) 
        self.assertEqual(plan.project_duration, D("6"))

    def test_dependency_type_start_to_start(self):
        """SS = Start to Start"""
        input = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;3
            B;A(SS2);4
        """)
        plan = ProjectPlan.create(parse_input_data(input))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;3;0;3;0;3;0
            B;4;2;6;2;6;0
        """)

        self.assertEqual(str(plan), expected) 
        self.assertEqual(plan.project_duration, D("6"))                

    def test_multiple_relationships_between_two_activities(self):
        input_data = dedent_strip("""
            Activity;Predecessor;Duration
            A;-;4
            B;A(SS),A(FF2);3
        """)

        plan = ProjectPlan.create(parse_input_data(input_data))

        expected = dedent_strip("""
            Activity;Duration;ES;EF;LS;LF;Float
            A;4;0;4;0;4;0
            B;3;3;6;3;6;0
        """)

        self.assertEqual(str(plan), expected)
        self.assertEqual(plan.project_duration, D("6"))
        self.assertListEqual(plan.obtain_critical_path(), ["A", "B"])

if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
