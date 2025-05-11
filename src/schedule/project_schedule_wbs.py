"""
From a work breakdown structure, create a project schedule.

PROMPT> python -m src.schedule.project_schedule_wbs
"""
from src.wbs.wbs_task import WBSProject, WBSTask
from src.schedule.schedule import Activity, ProjectSchedule, PredecessorInfo, DependencyType
from decimal import Decimal
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ProjectScheduleWBS:
    @staticmethod
    def convert(wbs_project: WBSProject, task_id_to_duration_dict: dict[str, Decimal]) -> ProjectSchedule:
        """
        Convert the WBSProject to a ProjectSchedule.

        Assumes that there is a 1-to-1 mapping between tasks in the WBSProject and in the task_id_to_duration_dict.

        Establish finish-to-start dependencies between sequential tasks.
        """
        activities = []

        zero = Decimal("0")
        def visit_task(task: WBSTask, depth: int, parent_id: Optional[str], prev_task_id: Optional[str], is_first_child: bool, is_last_child: bool):
            task_id = task.id
            duration = task_id_to_duration_dict.get(task_id)
            if duration is None:
                logger.error(f"Duration is None for task {task_id}, should have been estimated by HierarchyEstimatorWBS. There is not a 1-to-1 mapping between tasks in the WBSProject and in the task_id_to_duration_dict.")
                duration = Decimal("1")
            predecessors_str = ""
            pred_first_child = None
            pred_last_child = None
            pred_prev = None
            if is_first_child:
                if parent_id is not None:
                    predecessors_str = f"{parent_id}(SS)"
                    pred_first_child = PredecessorInfo(activity_id=parent_id, dep_type=DependencyType.SS, lag=zero)
            if is_last_child:
                if parent_id is not None:
                    predecessors_str = f"{parent_id}(FF)"
                    pred_last_child = PredecessorInfo(activity_id=parent_id, dep_type=DependencyType.FF, lag=zero)

            if prev_task_id is not None:
                predecessors_str = f"{prev_task_id}(FS)"
                pred_prev = PredecessorInfo(activity_id=prev_task_id, dep_type=DependencyType.FS, lag=zero)

            activity = Activity(id=task_id, duration=duration, predecessors_str=predecessors_str, title=task.description)

            if parent_id is not None:
                activity.parent_id = parent_id

            if pred_first_child is not None:
                activity.parsed_predecessors.append(pred_first_child)
            if pred_last_child is not None:
                activity.parsed_predecessors.append(pred_last_child)
            if pred_prev is not None:
                activity.parsed_predecessors.append(pred_prev)

            activities.append(activity)

            prev_task_id: Optional[str] = None
            for child_index, child in enumerate(task.task_children):
                is_first_child = child_index == 0
                is_last_child = child_index == len(task.task_children) - 1
                visit_task(child, depth + 1, parent_id=task.id, prev_task_id=prev_task_id, is_first_child=is_first_child, is_last_child=is_last_child)
                prev_task_id = child.id


        visit_task(wbs_project.root_task, 0, parent_id=None, prev_task_id=None, is_first_child=True, is_last_child=True)
        logger.debug(f"activities length: {len(activities)}")

        project_schedule = ProjectSchedule.create(activities)
        return project_schedule
