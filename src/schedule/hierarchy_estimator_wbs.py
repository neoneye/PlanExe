from decimal import Decimal
from typing import Dict
from src.schedule.hierarchical_estimator import Node
from src.wbs.wbs_task import WBSProject, WBSTask

class HierarchyEstimatorWBS:

    @staticmethod
    def run(wbs_project: WBSProject, task_id_to_duration_dict: Dict[str, Decimal]) -> WBSProject:
        
        def visit_task(task: WBSTask, depth: int) -> Node:
            if depth > 10:
                raise Exception("Depth limit reached")

            task_id = task.id
            task_duration = task_id_to_duration_dict.get(task_id, None)
            
            node = Node(task_id, task_duration)
            for child in task.task_children:
                child_node = visit_task(child, depth + 1)
                node.add_child(child_node)

            return node

        root_node = visit_task(wbs_project.root_task, 0)
        root_node.resolve_duration()
        root_node.apply_minimum_duration()

        d = root_node.to_dict()
        print("!!!!!!!!!!!!!!!!", d)

        print("root_node.duration", root_node.duration)

        raise NotImplementedError("Not implemented")
    

