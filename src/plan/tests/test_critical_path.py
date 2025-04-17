import unittest
import re
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
    ls: int = float('inf') # Latest Start
    lf: int = float('inf') # Latest Finish
    float: int = float('inf') # Slack/Float
    forward_pass_done: bool = False
    backward_pass_done: bool = False

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Activity):
            return NotImplemented
        return self.id == other.id

@dataclass
class ProjectPlan:
    """Holds the results of the CPM calculation."""
    activities: Dict[str, Activity]
    project_duration: int

    @classmethod
    def create(cls: Type['ProjectPlan'], activities: list[Activity]) -> 'ProjectPlan':
        """
        CPM: Critical Path Method
        https://en.wikipedia.org/wiki/Critical_path_method

        Performs Forward Pass, Backward Pass, calculates Float on the provided activities.
        Returns a new ProjectPlan instance containing the activities with calculated values
        and the project duration.

        Args:
            cls: The class itself (ProjectPlan).
            activities: A list of Activity objects to process.

        Returns:
            A new ProjectPlan instance with calculated data.

        Raises:
            ValueError: If no start activities are found or other input inconsistencies.
            RuntimeError: If forward/backward pass fails (e.g., due to cycles).
        """
        # Convert list to dictionary for internal processing
        activities_dict = {act.id: act for act in activities}
        
        if not activities_dict:
            return cls(activities={}, project_duration=0) # Use cls to construct

        # Reset calculation helpers (allows recalculation if needed)
        for act in activities_dict.values():
            act.es = 0
            act.ef = 0
            act.ls = float('inf')
            act.lf = float('inf')
            act.float = float('inf')
            act.forward_pass_done = False
            act.backward_pass_done = False

        start_nodes = [act for act in activities_dict.values() if not act.parsed_predecessors]
        end_nodes = [act for act in activities_dict.values() if not act.successors]

        if not start_nodes:
            if activities_dict:
                 raise ValueError("No start activities found. Check for cycles or missing dependencies.")
            else:
                 return cls(activities={}, project_duration=0) # Empty project

        # --- Forward Pass (Calculate ES, EF) ---
        processed_forward_count = 0
        queue = start_nodes[:]
        for node in queue:
            node.ef = node.duration
            node.forward_pass_done = True
            processed_forward_count += 1

        forward_q = start_nodes[:]
        iter_count = 0
        max_iters = len(activities_dict) * len(activities_dict)

        while forward_q and iter_count < max_iters:
            iter_count += 1
            current_node = forward_q.pop(0)

            for successor in current_node.successors:
                all_preds_done = all(activities_dict[p.activity_id].forward_pass_done
                                     for p in successor.parsed_predecessors)

                if all_preds_done:
                    max_potential_es = 0
                    for pred_info in successor.parsed_predecessors:
                        pred_act = activities_dict[pred_info.activity_id]
                        potential_es = 0
                        lag = pred_info.lag

                        if pred_info.dep_type == DependencyType.FS: potential_es = pred_act.ef + lag
                        elif pred_info.dep_type == DependencyType.SS: potential_es = pred_act.es + lag
                        elif pred_info.dep_type == DependencyType.FF: potential_es = pred_act.ef + lag - successor.duration
                        elif pred_info.dep_type == DependencyType.SF: potential_es = pred_act.es + lag - successor.duration

                        max_potential_es = max(max_potential_es, potential_es)

                    if max_potential_es > successor.es or not successor.forward_pass_done:
                        successor.es = max_potential_es
                        successor.ef = successor.es + successor.duration

                        if not successor.forward_pass_done:
                             successor.forward_pass_done = True
                             processed_forward_count += 1
                             if successor not in forward_q:
                                forward_q.append(successor)
                        elif successor not in forward_q:
                             forward_q.append(successor)

        if processed_forward_count < len(activities_dict):
             remaining_ids = [aid for aid, act in activities_dict.items() if not act.forward_pass_done]
             raise RuntimeError(f"Could not complete forward pass. Check for cycles or unconnected activities. Remaining: {remaining_ids}")
        if iter_count >= max_iters:
            raise RuntimeError(f"Forward pass exceeded max iterations. Check for cycles.")

        # --- Project Duration ---
        project_duration = 0
        if activities_dict:
             project_duration = max(node.ef for node in activities_dict.values() if node.forward_pass_done)

        # --- Backward Pass (Calculate LF, LS) ---
        processed_backward_count = 0
        backward_q = [n for n in activities_dict.values() if n.ef == project_duration and n.forward_pass_done]
        if not backward_q:
            backward_q = end_nodes[:] if end_nodes else list(activities_dict.values())

        for node in backward_q:
             node.lf = project_duration
             node.ls = node.lf - node.duration
             node.backward_pass_done = True
             processed_backward_count += 1

        iter_count = 0
        processed_for_backward = {node.id for node in backward_q}
        nodes_to_process_backward = set()
        for node in backward_q:
            for pred_info in node.parsed_predecessors:
                 pred_act = activities_dict[pred_info.activity_id]
                 if pred_act.id not in processed_for_backward:
                     nodes_to_process_backward.add(pred_act)
        backward_process_list = list(nodes_to_process_backward)

        while backward_process_list and iter_count < max_iters:
             iter_count += 1
             current_node = backward_process_list.pop(0)

             if not current_node.successors:
                 if not current_node.backward_pass_done:
                      current_node.lf = project_duration
                      current_node.ls = current_node.lf - current_node.duration
                      current_node.backward_pass_done = True
                      processed_backward_count += 1
                 continue

             all_succs_done = all(succ.backward_pass_done for succ in current_node.successors)

             if all_succs_done:
                min_potential_lf = float('inf')
                for successor in current_node.successors:
                    pred_info = next((p for p in successor.parsed_predecessors if p.activity_id == current_node.id), None)
                    if not pred_info: raise RuntimeError(f"Consistency error: Cannot find {current_node.id} in predecessors of {successor.id}")

                    potential_lf = float('inf')
                    lag = pred_info.lag

                    if pred_info.dep_type == DependencyType.FS: potential_lf = successor.ls - lag
                    elif pred_info.dep_type == DependencyType.SS: potential_lf = successor.ls - lag + current_node.duration
                    elif pred_info.dep_type == DependencyType.FF: potential_lf = successor.lf - lag
                    elif pred_info.dep_type == DependencyType.SF: potential_lf = successor.lf - lag + current_node.duration

                    min_potential_lf = min(min_potential_lf, potential_lf)

                if min_potential_lf < current_node.lf or not current_node.backward_pass_done:
                     current_node.lf = min_potential_lf
                     current_node.ls = current_node.lf - current_node.duration

                     if not current_node.backward_pass_done:
                         current_node.backward_pass_done = True
                         processed_backward_count += 1
                         processed_for_backward.add(current_node.id)
                         for pred_info in current_node.parsed_predecessors:
                             pred_act = activities_dict[pred_info.activity_id]
                             if pred_act.id not in processed_for_backward and pred_act not in backward_process_list:
                                  backward_process_list.append(pred_act)
                     elif current_node.id not in processed_for_backward:
                         processed_for_backward.add(current_node.id)
                         for pred_info in current_node.parsed_predecessors:
                             pred_act = activities_dict[pred_info.activity_id]
                             if pred_act.id not in processed_for_backward and pred_act not in backward_process_list:
                                  backward_process_list.append(pred_act)

        if processed_backward_count < len(activities_dict):
            remaining_ids = [aid for aid, act in activities_dict.items() if not act.backward_pass_done]
            print(f"Warning: Could not complete backward pass for all nodes. Processed: {processed_backward_count}/{len(activities_dict)}. Remaining: {remaining_ids}")
            for rem_id in remaining_ids:
                 rem_node = activities_dict[rem_id]
                 if not rem_node.backward_pass_done:
                     print(f"Assigning default LF/LS to potentially unconnected node: {rem_id}")
                     rem_node.lf = project_duration
                     rem_node.ls = rem_node.lf - rem_node.duration

        if iter_count >= max_iters:
             raise RuntimeError(f"Backward pass exceeded max iterations. Check for cycles.")

        # --- Calculate Float ---
        for activity in activities_dict.values():
            if activity.backward_pass_done and activity.forward_pass_done:
                 activity.float = activity.ls - activity.es
            else:
                 activity.float = float('inf') # Indicate incomplete

        return cls(activities=activities_dict, project_duration=project_duration)

    def get_critical_path_activities(self) -> list[Activity]:
        """Returns a list of Activity objects on the critical path, sorted by ES."""
        critical_nodes = [
            act for act in self.activities.values()
            # Ensure float is calculated and is 0
            if act.float != float('inf') and act.float == 0
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
        min_es = min(n.es for n in critical_path_nodes) if critical_path_nodes else 0
        nodes_to_process = sorted([n for n in critical_path_nodes if n.es == min_es], key=lambda x: x.id)

        current_node: Optional[Activity] = nodes_to_process[0] if nodes_to_process else None

        while current_node:
            if current_node.id in processed_on_path: break
            final_critical_path.append(current_node.id)
            processed_on_path.add(current_node.id)
            potential_next: list[Activity] = []

            for successor in current_node.successors:
                 if successor.float == 0: # Successor must be critical
                    pred_info = next((p for p in successor.parsed_predecessors if p.activity_id == current_node.id), None)
                    if not pred_info: continue
                    lag = pred_info.lag
                    is_critical_link = False
                    if pred_info.dep_type == DependencyType.FS and successor.es == current_node.ef + lag: is_critical_link = True
                    elif pred_info.dep_type == DependencyType.SS and successor.es == current_node.es + lag: is_critical_link = True
                    elif pred_info.dep_type == DependencyType.FF and successor.ef == current_node.ef + lag: is_critical_link = True
                    elif pred_info.dep_type == DependencyType.SF and successor.ef == current_node.es + lag: is_critical_link = True

                    if is_critical_link and successor.id not in processed_on_path:
                        potential_next.append(successor)

            if potential_next:
                potential_next.sort(key=lambda x: (x.es, x.id))
                current_node = potential_next[0]
            else:
                current_node = None
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
    
    # First pass: create all activities
    for line in lines[start_line:]:
        if not line.strip(): continue
        try:
            id_str, pred_str, dur_str = [part.strip() for part in line.split(';')]
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
    
    # Second pass: build successor relationships
    activities = list(activity_map.values())
    for activity in activities:
        for pred_info in activity.parsed_predecessors:
            pred_activity = activity_map.get(pred_info.activity_id)
            if pred_activity:
                if activity not in pred_activity.successors:
                    pred_activity.successors.append(activity)
            else:
                 raise ValueError(f"Predecessor '{pred_info.activity_id}' for activity '{activity.id}' not found.")
    
    return activities

class TestCriticalPath(unittest.TestCase):
    def test_all_dependency_types(self):
        data = """
        Activity;Predecessor;Duration
        A;-;3
        B;A(FS2);2
        C;A(SS);2
        D;B(SS1);4
        E;C(SF3);1
        F;C(FF3);2
        G;D(SS1),E;4
        H;F(SF2),G;3
        """

        print("--- Parsing Input ---")
        activities = parse_input_data(data)
        print(f"Parsed {len(activities)} activities.")

        print("\n--- Calculating CPM ---")
        project_plan = ProjectPlan.create(activities)
        # -----------------------------

        print("\n--- Results ---")
        project_duration = project_plan.project_duration
        critical_path = project_plan.obtain_critical_path()

        print(f"Project Duration: {project_duration}")
        print(f"Critical Path: {' -> '.join(critical_path)}")

        print("\n--- Activity Details (ES, EF, LS, LF, Float) ---")
        sorted_activities = sorted(project_plan.activities.values(), key=lambda x: x.id)
        print("ID | Dur | ES | EF | LS | LF | Float | Predecessors")
        print("---|-----|----|----|----|----|-------|-------------")
        for act in sorted_activities:
            preds_str = ', '.join([f"{p.activity_id}({p.dep_type.name}{p.lag if p.lag else ''})"
                                    for p in act.parsed_predecessors]) if act.parsed_predecessors else '-'
            float_str = f"{act.float:<5}" if act.float != float('inf') else "inf"
            ls_str = f"{act.ls:<2}" if act.ls != float('inf') else "inf"
            lf_str = f"{act.lf:<2}" if act.lf != float('inf') else "inf"
            print(f"{act.id:<2} | {act.duration:<3} | {act.es:<2} | {act.ef:<2} | {ls_str} | {lf_str} | {float_str} | {preds_str}")

        self.assertEqual(project_duration, 14)
        self.assertEqual(critical_path, ['A', 'B', 'D', 'G', 'H'])
        self.assertEqual(project_plan.activities['A'].float, 0)
        self.assertEqual(project_plan.activities['B'].float, 0)
        self.assertEqual(project_plan.activities['C'].float, 4)
        self.assertEqual(project_plan.activities['D'].float, 0)
        self.assertEqual(project_plan.activities['E'].float, 4)
        self.assertEqual(project_plan.activities['F'].float, 9)
        self.assertEqual(project_plan.activities['G'].float, 0)
        self.assertEqual(project_plan.activities['H'].float, 0)
