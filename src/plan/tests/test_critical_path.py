"""
CPM: Critical Path Method
https://en.wikipedia.org/wiki/Critical_path_method
https://en.wikipedia.org/wiki/Dependency_(project_management)
"""
import unittest
import re
from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Type

# Terminology is described here:
# https://en.wikipedia.org/wiki/Dependency_(project_management)
class DependencyType(Enum):
    FS = "FS" # Finish-to-Start
    SS = "SS" # Start-to-Start
    FF = "FF" # Finish-to-Finish
    SF = "SF" # Start-to-Finish

@dataclass
class PredecessorInfo:
    activity_id: str
    dep_type: DependencyType = DependencyType.FS # Default to FS if not specified
    lag: int = 0

@dataclass
class Activity:
    id: str
    duration: int
    predecessors_str: str
    parsed_predecessors: List[PredecessorInfo] = field(default_factory=list)
    successors: List['Activity'] = field(default_factory=list) # Activities that depend on this one
    es: int = 0 # Earliest Start
    ef: int = 0 # Earliest Finish
    ls: Optional[int] = None # Latest Start
    lf: Optional[int] = None # Latest Finish
    float: Optional[int] = None # Slack/Float

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Activity):
            return NotImplemented
        return self.id == other.id
    
    @classmethod
    def build_successor_links(cls, activities: Dict[str, "Activity"]) -> None:
        """
        Populate .successors for every activity so that it mirrors the
        .parsed_predecessors lists.

        • Clears existing successor lists (idempotent).  
        • Raises ValueError if a predecessor id is missing in *activities*.  
        """
        # 1. blank slate
        for act in activities.values():
            act.successors.clear()

        # 2. wire forward links
        for act in activities.values():
            for info in act.parsed_predecessors:
                try:
                    pred = activities[info.activity_id]
                except KeyError:
                    raise ValueError(
                        f"Predecessor '{info.activity_id}' referenced by "
                        f"activity '{act.id}' not found."
                    )
                if act not in pred.successors: # de‑dupe
                    pred.successors.append(act)

def _topological_order(activities: Dict[str, Activity]) -> List[Activity]:
    """
    Kahn’s algorithm - returns a topological order or raises on cycles
    https://en.wikipedia.org/wiki/Topological_sorting
    """
    in_deg = {aid: len(act.parsed_predecessors) for aid, act in activities.items()}
    q      = deque([act for aid, act in activities.items() if in_deg[aid] == 0])
    order  : List[Activity] = []

    while q:
        node = q.popleft()
        order.append(node)
        for succ in node.successors:
            in_deg[succ.id] -= 1
            if in_deg[succ.id] == 0:
                q.append(succ)

    if len(order) != len(activities):
        cycles = [aid for aid, d in in_deg.items() if d > 0]
        raise RuntimeError(f"Cycle detected involving: {', '.join(cycles)}")

    return order

@dataclass
class ProjectPlan:
    """Holds the results of the CPM calculation."""
    activities: Dict[str, Activity]
    project_duration: int

    @classmethod
    def create(cls: Type["ProjectPlan"], activities: List["Activity"]) -> "ProjectPlan":
        """Compute CPM dates using a single forward‑then‑backward topological sweep."""
        acts: Dict[str, Activity] = {a.id: a for a in activities}
        if not acts:
            return cls(activities={}, project_duration=0)

        Activity.build_successor_links(acts)
        topo = _topological_order(acts)

        # ── Forward pass ─────────────────────────────────────────────
        for node in topo:
            if not node.parsed_predecessors:               # start node
                node.es = 0
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

        # ── Backward pass ────────────────────────────────────────────
        for node in reversed(topo):
            if not node.successors:                          # end node
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
            node.ls   = node.lf - node.duration
            node.float = node.ls - node.es

        return cls(activities=acts, project_duration=project_duration)
    
    def get_critical_path_activities(self) -> list[Activity]:
        """Returns a list of Activity objects on the critical path, sorted by ES."""
        critical_nodes = [
            act for act in self.activities.values()
            # Ensure float is calculated and is 0
            if act.float is not None and act.float == 0
        ]
        critical_nodes.sort(key=lambda x: x.es)
        return critical_nodes

    def obtain_critical_path(self) -> list[str]:
        """
        Identifies one potential critical path sequence based on calculated values.
        Returns a list of activity IDs in sequence.
        """
        critical_path_nodes = self.get_critical_path_activities()
        if not critical_path_nodes:
            return []

        final_critical_path: list[str] = []
        processed_on_path: Set[str] = set()
        # Start from critical nodes with the earliest start time
        min_es = min(n.es for n in critical_path_nodes) # Safe due to check above
        nodes_to_process = sorted([n for n in critical_path_nodes if n.es == min_es], key=lambda x: x.id)

        # If multiple start nodes on critical path, pick the first alphabetically
        current_node: Optional[Activity] = nodes_to_process[0] if nodes_to_process else None

        while current_node:
            if current_node.id in processed_on_path: break # Avoid cycles in path traversal
            final_critical_path.append(current_node.id)
            processed_on_path.add(current_node.id)
            potential_next: list[Activity] = []

            for successor in current_node.successors:
                 # Successor must be critical
                 if successor.float is not None and successor.float == 0:
                    pred_info = next((p for p in successor.parsed_predecessors if p.activity_id == current_node.id), None)
                    if not pred_info: continue # Should not happen if successor list is correct

                    # Check if the specific link is critical
                    lag = pred_info.lag
                    is_critical_link = False
                    # Need LS/LF/ES/EF to be calculated
                    if successor.es is None or successor.lf is None or current_node.ef is None or current_node.es is None:
                        continue # Calculation incomplete, cannot determine link criticality

                    if pred_info.dep_type == DependencyType.FS and successor.es == current_node.ef + lag: is_critical_link = True
                    elif pred_info.dep_type == DependencyType.SS and successor.es == current_node.es + lag: is_critical_link = True
                    # For FF/SF, check if the *finish* times align correctly for criticality
                    elif pred_info.dep_type == DependencyType.FF and successor.lf == current_node.lf + lag: is_critical_link = True # LF based check
                    elif pred_info.dep_type == DependencyType.SF and successor.lf == current_node.es + lag + successor.duration: is_critical_link = True # Check if S.lf = A.es + lag + S.dur

                    # Alternative/Simpler critical link check for FF/SF (based on EF):
                    # elif pred_info.dep_type == DependencyType.FF and successor.ef == current_node.ef + lag: is_critical_link = True # Does EF work reliably? Check definition. Yes, if float=0, EF=LF
                    # elif pred_info.dep_type == DependencyType.SF and successor.ef == current_node.es + lag: is_critical_link = True # Check if S.ef = A.es + lag. Also seems plausible if float=0.

                    # Let's stick to the primary ES/EF based checks where possible, using LS/LF for FF/SF might be more robust if ES/EF alignmant isn't guaranteed by float=0 alone for these types.
                    # Rechecking FF: If A(FF lag) -> B, then B.ef >= A.ef + lag. If critical, B.ef = A.ef + lag? OR is it B.lf = A.lf + lag? Let's use LF.
                    # Rechecking SF: If A(SF lag) -> B, then B.ef >= A.es + lag. If critical, B.ef = A.es + lag? OR B.lf = A.es + lag + B.dur? Use LF version.

                    if is_critical_link and successor.id not in processed_on_path:
                        potential_next.append(successor)

            if potential_next:
                potential_next.sort(key=lambda x: (x.es, x.id)) # Prioritize earliest starting next critical task
                current_node = potential_next[0]
            else:
                current_node = None # End of this critical path segment
        return final_critical_path

def parse_dependency(dep_str: str) -> PredecessorInfo:
    dep_str = dep_str.strip()
    match = re.match(r"(\w+)(?:\(([SF]{2})(\d+)?\))?", dep_str)
    if not match: raise ValueError(f"Invalid dependency format: {dep_str}")
    activity_id, dep_type_str, lag_str = match.groups()
    dep_type = DependencyType.FS
    if dep_type_str:
        try: dep_type = DependencyType(dep_type_str.upper())
        except ValueError: raise ValueError(f"Invalid dependency type in: {dep_str}")
    lag = int(lag_str) if lag_str else 0
    return PredecessorInfo(activity_id=activity_id, dep_type=dep_type, lag=lag)

def parse_input_data(data: str) -> list[Activity]:
    activity_map: Dict[str, Activity] = {}  # Temporary map for building relationships
    lines = data.strip().split('\n')
    header = lines[0].strip().lower()
    start_line = 1 if 'activity' in header and 'predecessor' in header else 0
    
    # Create all activities
    for i, line in enumerate(lines[start_line:], start=start_line):
        if not line.strip(): continue

        # Split by semicolon, strip whitespace from each part
        parts = [part.strip() for part in line.split(';')]

        # We need at least 3 parts (ID, Predecessor, Duration)
        # Additional parts are ignored (considered comments)
        if len(parts) < 3:
             print(f"Warning: Skipping line {i+1} due to insufficient columns ({len(parts)}): '{line}'")
             continue

        try:
            # Take the first three parts
            id_str, pred_str, dur_str = parts[0], parts[1], parts[2]

            duration = int(dur_str)
            if duration <= 0: raise ValueError(f"Duration must be positive for Activity {id_str}")
            activity = Activity(id=id_str, duration=duration, predecessors_str=pred_str)
            if pred_str != '-':
                 for item in pred_str.split(','):
                     activity.parsed_predecessors.append(parse_dependency(item.strip()))
            if id_str in activity_map: raise ValueError(f"Duplicate Activity ID found: {id_str}")
            activity_map[id_str] = activity
        except (ValueError, IndexError) as e:
            print(f"Error parsing line: '{line}'. Reason: {e}"); raise
    
    return list(activity_map.values()) 

class TestCriticalPath(unittest.TestCase):
    def test_all_dependency_types(self):
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

        print("\n--- Test: All Dependency Types ---")
        print("Input Data:")
        print(data)

        print("\n--- Parsing Input ---")
        activities = parse_input_data(data)
        print(f"Parsed {len(activities)} activities:")
        for act in sorted(activities, key=lambda a: a.id):
             print(f"  ID: {act.id}, Duration: {act.duration}, Predecessors: {act.predecessors_str}")

        print("\n--- Calculating CPM ---")
        project_plan = ProjectPlan.create(activities)
        # -----------------------------

        print("\n--- Results ---")
        project_duration = project_plan.project_duration
        critical_path_nodes = project_plan.get_critical_path_activities()
        critical_path_ids = [n.id for n in critical_path_nodes]
        # Use obtain_critical_path to get a specific sequence
        critical_path_sequence = project_plan.obtain_critical_path()


        print(f"Project Duration: {project_duration}")
        print(f"Critical Path Nodes (Float=0): {', '.join(critical_path_ids)}")
        print(f"A Critical Path Sequence: {' -> '.join(critical_path_sequence)}")

        print("\n--- Activity Details (ES, EF, LS, LF, Float) ---")
        sorted_activities = sorted(project_plan.activities.values(), key=lambda x: x.id)
        print("ID | Dur | ES | EF | LS | LF | Float | Predecessors")
        print("---|-----|----|----|----|----|-------|-------------")
        for act in sorted_activities:
            preds_str = ', '.join([f"{p.activity_id}({p.dep_type.name}{p.lag if p.lag else ''})"
                                    for p in act.parsed_predecessors]) if act.parsed_predecessors else '-'
            # Handle Optional[int] for display
            ls_str = f"{act.ls:<2}" if act.ls is not None else "N/A"
            lf_str = f"{act.lf:<2}" if act.lf is not None else "N/A"
            float_str = f"{act.float:<5}" if act.float is not None else "N/A"

            print(f"{act.id:<2} | {act.duration:<3} | {act.es:<2} | {act.ef:<2} | {ls_str} | {lf_str} | {float_str} | {preds_str}")

        # --- Assertions (Recalculate expected values based on rules) ---
        # A: ES=0, EF=3
        # B: Dep=A(FS2). ES = max(A.ef+2) = 3+2=5. EF=5+2=7
        # C: Dep=A(SS). ES = max(A.es+0) = 0. EF=0+2=2
        # D: Dep=B(SS1). ES = max(B.es+1) = 5+1=6. EF=6+4=10
        # E: Dep=C(SF3). ES = max(C.es+3-E.dur) = 0+3-1=2. EF=2+1=3
        # F: Dep=C(FF3). ES = max(C.ef+3-F.dur) = 2+3-2=3. EF=3+2=5
        # G: Dep=D(SS1), E(FS0). ES = max(D.es+1, E.ef+0) = max(6+1, 3+0) = max(7, 3) = 7. EF=7+4=11
        # H: Dep=F(SF2), G(FS0). ES = max(F.es+2-H.dur, G.ef+0) = max(3+2-3, 11+0) = max(2, 11) = 11. EF=11+3=14

        # Project Duration = max EF = 14

        # Backward Pass (Start LF=14)
        # H: LF=14, LS=14-3=11
        # G: Dep for G is H(FS0). LF = min(H.ls-0) = 11. LS=11-4=7
        # F: Dep for F is H(SF2). LF = min(H.lf-2+F.dur) = min(14-2+2) = 14. LS=14-2=12
        # E: Dep for E is G(FS0). LF = min(G.ls-0) = 7. LS=7-1=6
        # D: Dep for D is G(SS1). LF = min(G.ls-1+D.dur) = min(7-1+4) = 10. LS=10-4=6
        # C: Dep for C are E(SF3), F(FF3). LF = min(E.lf-3+C.dur, F.lf-3) = min(7-3+2, 14-3) = min(6, 11) = 6. LS=6-2=4
        # B: Dep for B is D(SS1). LF = min(D.ls-1+B.dur) = min(6-1+2) = 7. LS=7-2=5
        # A: Dep for A are B(FS2), C(SS0). LF = min(B.ls-2, C.ls-0+A.dur) = min(5-2, 4-0+3) = min(3, 7) = 3. LS=3-3=0

        # Float = LS - ES
        # A: 0-0=0
        # B: 5-5=0
        # C: 4-0=4
        # D: 6-6=0
        # E: 6-2=4
        # F: 12-3=9
        # G: 7-7=0
        # H: 11-11=0

        self.assertEqual(project_duration, 14)
        self.assertEqual(critical_path_sequence, ['A', 'B', 'D', 'G', 'H']) # Based on obtain_critical_path logic
        self.assertEqual(project_plan.activities['A'].float, 0)
        self.assertEqual(project_plan.activities['B'].float, 0)
        self.assertEqual(project_plan.activities['C'].float, 4)
        self.assertEqual(project_plan.activities['D'].float, 0)
        self.assertEqual(project_plan.activities['E'].float, 4)
        self.assertEqual(project_plan.activities['F'].float, 9)
        self.assertEqual(project_plan.activities['G'].float, 0)
        self.assertEqual(project_plan.activities['H'].float, 0)

        # Check specific ES/LS values
        self.assertEqual(project_plan.activities['A'].es, 0)
        self.assertEqual(project_plan.activities['A'].ls, 0)
        self.assertEqual(project_plan.activities['B'].es, 5)
        self.assertEqual(project_plan.activities['B'].ls, 5)
        self.assertEqual(project_plan.activities['C'].es, 0)
        self.assertEqual(project_plan.activities['C'].ls, 4)
        self.assertEqual(project_plan.activities['D'].es, 6)
        self.assertEqual(project_plan.activities['D'].ls, 6)
        self.assertEqual(project_plan.activities['E'].es, 2)
        self.assertEqual(project_plan.activities['E'].ls, 6)
        self.assertEqual(project_plan.activities['F'].es, 3)
        self.assertEqual(project_plan.activities['F'].ls, 12)
        self.assertEqual(project_plan.activities['G'].es, 7)
        self.assertEqual(project_plan.activities['G'].ls, 7)
        self.assertEqual(project_plan.activities['H'].es, 11)
        self.assertEqual(project_plan.activities['H'].ls, 11)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)