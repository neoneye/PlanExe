from __future__ import annotations
"""
CPM: Critical Path Method – **decimal version**
Supports fractional durations & lags via ``decimal.Decimal``.
Originally adapted from the integer‑based implementation.
"""
import unittest
from decimal import Decimal, getcontext
from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Type
import re
import pandas as pd
from io import StringIO

# ────────────────────────────────────────────────────────────────────────────────
#  Global decimal configuration  
# ----------------------------------------------------------------------------
# Adjust the precision if your schedules require more than 28 significant digits.
getcontext().prec = 28
ZERO = Decimal("0")

# ────────────────────────────────────────────────────────────────────────────────
#  Dependency types
# ----------------------------------------------------------------------------
class DependencyType(Enum):
    FS = "FS"  # Finish‑to‑Start
    SS = "SS"  # Start‑to‑Start
    FF = "FF"  # Finish‑to‑Finish
    SF = "SF"  # Start‑to‑Finish

# ────────────────────────────────────────────────────────────────────────────────
#  Data classes
# ----------------------------------------------------------------------------
@dataclass
class PredecessorInfo:
    activity_id: str
    dep_type: DependencyType = DependencyType.FS  # default to FS
    lag: Decimal = field(default=ZERO)

@dataclass
class Activity:
    id: str
    duration: Decimal
    predecessors_str: str
    parsed_predecessors: List[PredecessorInfo] = field(default_factory=list)
    successors: List["Activity"] = field(default_factory=list)  # populated later

    # CPM dates
    es: Decimal = field(default=ZERO)  # Earliest Start
    ef: Decimal = field(default=ZERO)  # Earliest Finish
    ls: Optional[Decimal] = None       # Latest  Start
    lf: Optional[Decimal] = None       # Latest  Finish
    float: Optional[Decimal] = None    # Total   Float / Slack

    # Equality helpers (activities are unique by ID)
    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Activity):
            return NotImplemented
        return self.id == other.id

    # ────────────────────────────────────────────────────────────────────────
    #  Successor wiring (inverse of predecessor lists)
    # --------------------------------------------------------------------
    @classmethod
    def build_successor_links(cls, activities: Dict[str, "Activity"]) -> None:
        """Populate each activity's *successors* list from predecessor data."""
        # 1) clear any stale links (idempotent)
        for a in activities.values():
            a.successors.clear()

        # 2) build forward links
        for act in activities.values():
            for pred_info in act.parsed_predecessors:
                try:
                    pred = activities[pred_info.activity_id]
                except KeyError:
                    raise ValueError(
                        f"Predecessor '{pred_info.activity_id}' referenced by "
                        f"activity '{act.id}' not found."
                    )
                if act not in pred.successors:  # de‑dupe
                    pred.successors.append(act)

# ────────────────────────────────────────────────────────────────────────────────
#  Topological ordering (Kahn)
# ----------------------------------------------------------------------------

def _topological_order(activities: Dict[str, Activity]) -> List[Activity]:
    """Return activities in topological order or raise on cyclic dependency."""
    in_deg = {aid: len(a.parsed_predecessors) for aid, a in activities.items()}
    queue = deque([a for aid, a in activities.items() if in_deg[aid] == 0])
    order: List[Activity] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for succ in node.successors:
            in_deg[succ.id] -= 1
            if in_deg[succ.id] == 0:
                queue.append(succ)

    if len(order) != len(activities):
        cycles = [aid for aid, deg in in_deg.items() if deg > 0]
        raise RuntimeError(f"Cycle detected involving: {', '.join(cycles)}")

    return order

# ────────────────────────────────────────────────────────────────────────────────
#  Post‑schedule validation / warnings
# ----------------------------------------------------------------------------

def _collect_schedule_warnings(acts: Dict[str, Activity]) -> List[str]:
    warnings: List[str] = []

    # 1) temporal‑constraint violations
    for succ in acts.values():
        for info in succ.parsed_predecessors:
            pred = acts[info.activity_id]
            lag  = info.lag

            ok = {
                DependencyType.FS: succ.es >= pred.ef + lag,
                DependencyType.SS: succ.es >= pred.es + lag,
                DependencyType.FF: succ.ef >= pred.ef + lag,
                DependencyType.SF: succ.ef >= pred.es + lag,
            }[info.dep_type]

            if not ok:
                warnings.append(
                    "Constraint violation: "
                    f"{pred.id}->{succ.id} {info.dep_type.value}{lag:+} not satisfied "
                    f"(pred.EF={pred.ef}, succ.ES={succ.es}, succ.EF={succ.ef})"
                )

    # 2) negative float
    for a in acts.values():
        if a.float is not None and a.float < ZERO:
            warnings.append(
                f"Negative total float ({a.float}) on activity {a.id} "
                f"(ES={a.es}, LS={a.ls})."
            )

    return warnings

# ────────────────────────────────────────────────────────────────────────────────
#  CPM calculation (forward & backward pass)
# ----------------------------------------------------------------------------
@dataclass
class ProjectPlan:
    activities: Dict[str, Activity]
    project_duration: Decimal
    warnings: List[str] = field(default_factory=list)

    # --------------------------------------------------------------------
    #  Factory – compute CPM
    # --------------------------------------------------------------------
    @classmethod
    def create(cls: Type["ProjectPlan"], activities: List[Activity]) -> "ProjectPlan":
        acts: Dict[str, Activity] = {a.id: a for a in activities}
        if not acts:
            return cls(activities={}, project_duration=ZERO)

        # build successor links & ordering
        Activity.build_successor_links(acts)
        topo = _topological_order(acts)

        # ── Forward pass ────────────────────────────────────────────
        for node in topo:
            if not node.parsed_predecessors:  # start node
                node.es = ZERO
            else:
                node.es = max(
                    {
                        DependencyType.FS: lambda p, lag: p.ef + lag,
                        DependencyType.SS: lambda p, lag: p.es + lag,
                        DependencyType.FF: lambda p, lag: p.ef + lag - node.duration,
                        DependencyType.SF: lambda p, lag: p.es + lag - node.duration,
                    }[info.dep_type](acts[info.activity_id], info.lag)
                    for info in node.parsed_predecessors
                )
            node.ef = node.es + node.duration

        project_duration = max(a.ef for a in acts.values())

        # ── Backward pass ───────────────────────────────────────────
        for node in reversed(topo):
            if not node.successors:  # end node
                node.lf = project_duration
            else:
                node.lf = min(
                    {
                        DependencyType.FS: lambda s, link: s.ls - link.lag,
                        DependencyType.SS: lambda s, link: s.ls - link.lag + node.duration,
                        DependencyType.FF: lambda s, link: s.lf - link.lag,
                        DependencyType.SF: lambda s, link: s.lf - link.lag + node.duration,
                    }[link.dep_type](s, link)
                    for s in node.successors
                    for link in (next(p for p in s.parsed_predecessors if p.activity_id == node.id),)
                )
            node.ls = node.lf - node.duration
            node.float = node.ls - node.es

        warnings = _collect_schedule_warnings(acts)
        return cls(activities=acts, project_duration=project_duration, warnings=warnings)

    # --------------------------------------------------------------------
    #  Helper utilities
    # --------------------------------------------------------------------
    def get_critical_path_activities(self) -> List[Activity]:
        crit = [a for a in self.activities.values() if a.float == ZERO]
        crit.sort(key=lambda x: x.es)
        return crit

    def obtain_critical_path(self) -> List[str]:
        crit_nodes = self.get_critical_path_activities()
        if not crit_nodes:
            return []

        final_path: List[str] = []
        processed: Set[str] = set()
        min_es = min(n.es for n in crit_nodes)
        to_process = sorted(
            [n for n in crit_nodes if n.es == min_es], key=lambda x: x.id
        )
        current: Optional[Activity] = to_process[0] if to_process else None

        while current:
            if current.id in processed:
                break
            final_path.append(current.id)
            processed.add(current.id)
            next_on_path: List[Activity] = []

            for succ in current.successors:
                if succ.float != ZERO:
                    continue
                link = next(p for p in succ.parsed_predecessors if p.activity_id == current.id)
                lag = link.lag

                is_crit_link = {
                    DependencyType.FS: succ.es == current.ef + lag,
                    DependencyType.SS: succ.es == current.es + lag,
                    DependencyType.FF: succ.lf == current.lf + lag,
                    DependencyType.SF: succ.lf == current.es + lag + succ.duration,
                }[link.dep_type]

                if is_crit_link and succ.id not in processed:
                    next_on_path.append(succ)

            if next_on_path:
                next_on_path.sort(key=lambda x: (x.es, x.id))
                current = next_on_path[0]
            else:
                current = None
        return final_path

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

from decimal import Decimal as D

class TestCriticalPathDecimal(unittest.TestCase):
    """Updated test‑suite exercising decimal‑based CPM implementation."""

    def test_all_dependency_types_integer_data(self):
        """Original scenario – now using ``Decimal`` everywhere (integers still OK)."""
        data = """
        Activity;Predecessor;Duration;Comment
        A;-;3;Start node
        B;A(FS2);2;
        C;A(SS);2; C starts when A starts
        D;B(SS1);4; D starts 1 after B starts
        E;C(SF3);1; E starts 3 after C finishes (E_ef >= C_es + 3)? No SF is Start-Finish E_lf >= C_es + lag + E_dur
        F;C(FF3);2; F finishes 3 after C finishes
        G;D(SS1),E;4;Multiple preds (E is FS default)
        H;F(SF2),G;3;Multiple preds (G is FS default)
        """

        acts = parse_input_data(data)
        plan = ProjectPlan.create(acts)

        # project stats
        self.assertEqual(plan.project_duration, D("14"))
        self.assertListEqual(plan.obtain_critical_path(), ["A", "B", "D", "G", "H"])

        a = plan.activities  # shorthand
        # Floats
        self.assertEqual(a["A"].float, D("0"))
        self.assertEqual(a["B"].float, D("0"))
        self.assertEqual(a["C"].float, D("4"))
        self.assertEqual(a["D"].float, D("0"))
        self.assertEqual(a["E"].float, D("4"))
        self.assertEqual(a["F"].float, D("9"))
        self.assertEqual(a["G"].float, D("0"))
        self.assertEqual(a["H"].float, D("0"))

        # ES / LS spot‑checks
        self.assertEqual(a["A"].es, D("0"));  self.assertEqual(a["A"].ls, D("0"))
        self.assertEqual(a["B"].es, D("5"));  self.assertEqual(a["B"].ls, D("5"))
        self.assertEqual(a["C"].es, D("0"));  self.assertEqual(a["C"].ls, D("4"))
        self.assertEqual(a["D"].es, D("6"));  self.assertEqual(a["D"].ls, D("6"))
        self.assertEqual(a["E"].es, D("2"));  self.assertEqual(a["E"].ls, D("6"))
        self.assertEqual(a["F"].es, D("3"));  self.assertEqual(a["F"].ls, D("12"))
        self.assertEqual(a["G"].es, D("7"));  self.assertEqual(a["G"].ls, D("7"))
        self.assertEqual(a["H"].es, D("11")); self.assertEqual(a["H"].ls, D("11"))

    # ------------------------------------------------------------------
    def test_fractional_durations_and_lags(self):
        """Simple chain with fractional numbers to verify decimal math."""
        data = """
        Activity;Predecessor;Duration
        A;-;1.5
        B;A(FS0.75);2.25
        """
        acts = parse_input_data(data)
        plan = ProjectPlan.create(acts)

        self.assertEqual(plan.project_duration, D("4.5"))
        a = plan.activities
        # Activity A
        self.assertEqual(a["A"].es, D("0"))
        self.assertEqual(a["A"].ef, D("1.5"))
        # Activity B
        self.assertEqual(a["B"].es, D("2.25"))  # 1.5 + 0.75
        self.assertEqual(a["B"].ef, D("4.5"))
        # Floats on both should be zero
        self.assertEqual(a["A"].float, D("0"))
        self.assertEqual(a["B"].float, D("0"))


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
