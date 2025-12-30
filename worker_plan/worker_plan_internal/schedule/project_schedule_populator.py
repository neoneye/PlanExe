"""
From a work breakdown structure, assign estimated durations and create the project schedule.

PROMPT> python -m worker_plan_internal.schedule.project_schedule_populator
"""
from worker_plan_internal.schedule.hierarchy_estimator_wbs import HierarchyEstimatorWBS
from worker_plan_internal.schedule.project_schedule_wbs import ProjectScheduleWBS
from worker_plan_internal.wbs.wbs_task import WBSProject
from worker_plan_internal.schedule.schedule import ProjectSchedule
from decimal import Decimal
from typing import Any
import logging

logger = logging.getLogger(__name__)

class ProjectSchedulePopulator:
    @staticmethod
    def populate(wbs_project: WBSProject, duration_list: list[dict[str, Any]]) -> ProjectSchedule:
        """
        Create a ProjectSchedule.
        """
        if not isinstance(wbs_project, WBSProject):
            raise ValueError(f"wbs_project must be a WBSProject, but got {type(wbs_project)}")
        if not isinstance(duration_list, list):
            raise ValueError(f"duration_list must be a list, but got {type(duration_list)}")
        if not all(isinstance(duration_dict, dict) for duration_dict in duration_list):
            raise ValueError("duration_list must be a list of dicts, but got {type(duration_list)}")

        # The number of hours per day is hardcoded. This should be determined by the task_duration agent. Is it 8 hours or 24 hours, or instead of days is it hours or weeks.
        # hours_per_day = 8
        hours_per_day = 1
        task_id_to_duration_dict: dict[str, Decimal] = {}
        for duration_dict in duration_list:
            task_id = duration_dict['task_id']
            duration = duration_dict['days_realistic'] * hours_per_day
            if duration < 0:
                logger.warning(f"Duration for task {task_id} is negative: {duration}. Setting to 1.")
                duration = 1
            task_id_to_duration_dict[task_id] = Decimal(duration)

        # Estimate the durations for all tasks in the WBS project.
        task_id_to_duration_dict2 = HierarchyEstimatorWBS.run(wbs_project, task_id_to_duration_dict)

        # Convert the WBSProject to a ProjectSchedule.
        project_schedule = ProjectScheduleWBS.convert(wbs_project, task_id_to_duration_dict2)
        return project_schedule
