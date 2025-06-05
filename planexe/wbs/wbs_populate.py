import os
import json
import logging
from planexe.wbs.wbs_task import WBSTask, WBSProject
from planexe.uuid_util.is_valid_uuid import is_valid_uuid

logger = logging.getLogger(__name__)

class WBSPopulate:
    @staticmethod
    def project_from_level1_json(path_level1_json: str) -> WBSProject:
        """
        Create a WBSProject from a level 1 JSON file.
        """
        if not isinstance(path_level1_json, str):
            raise ValueError("Invalid path_level1_json.")
        
        with open(path_level1_json) as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise ValueError("Expected a dictionary in the JSON file.")

        root_task_id = d.get('id', None)
        project_title = d.get('project_title', None)
        final_deliverable = d.get('final_deliverable', None)

        if not is_valid_uuid(root_task_id):
            logger.error(f"Expected valid UUID, but got root_task_id: {root_task_id}")

        root_task = WBSTask(
            id = root_task_id,
            description=project_title,
        )
        root_task.set_field('final_deliverable', final_deliverable)
        return WBSProject(root_task)

    @staticmethod
    def extend_project_with_level2_json(wbs_project: WBSProject, path_level2_json: str):
        """
        Grow the tree hierarchy with tasks from a WBS Level 2 JSON file.
        """
        if not isinstance(wbs_project, WBSProject):
            raise ValueError("Expected a WBSProject object.")
        if not isinstance(path_level2_json, str):
            raise ValueError("Invalid path_level2_json.")

        with open(path_level2_json) as f:
            task_item_list = json.load(f)
        if not isinstance(task_item_list, list):
            raise ValueError("Expected a list of tasks in the JSON file.")

        for task_index, task_json in enumerate(task_item_list):
            task_id = task_json.get('id', None)
            if not is_valid_uuid(task_id):
                logger.error(f"Expected valid UUID, but got task_id: {task_id} for task_index: {task_index}")
                task_id = "MISSING_TASK_ID"

            major_phase_title = task_json.get('major_phase_title', None)
            if not major_phase_title:
                logger.error(f"Missing 'major_phase_title' for task with id: {task_id} for task_index: {task_index}")
                major_phase_title = "MISSING_MAJOR_PHASE_TITLE"

            task = WBSTask(
                id=task_id,
                description=major_phase_title
            )
            wbs_project.root_task.task_children.append(task)

            subtask_list = task_json.get('subtasks', None)
            if not subtask_list:
                logger.error(f"Missing 'subtasks' for task with id: {task_id}")
                subtask_list = []

            for subtask_json in subtask_list:
                subtask_id = subtask_json.get('id', None)
                if not is_valid_uuid(subtask_id):
                    logger.error(f"Expected valid UUID, but got subtask_id: {subtask_id} for task with id: {task_id}")

                subtask_description = subtask_json.get('description', None)
                if not subtask_description:
                    logger.error(f"Missing 'description' for subtask with id: {subtask_id}")
                    subtask_description = "MISSING_SUBTASK_DESCRIPTION"

                subtask = WBSTask(
                    id=subtask_id,
                    description=subtask_description
                )
                task.task_children.append(subtask)

    @staticmethod
    def extend_project_with_dependencies_json(wbs_project: WBSProject, path_dependencies_json: str):
        """
        Enrich the tree hierarchy with tasks from a dependencies JSON file.
        
        Establish dependencies between tasks, with explanations why these dependencies exists.
        """
        if not isinstance(wbs_project, WBSProject):
            raise ValueError("Expected a WBSProject object.")
        if not isinstance(path_dependencies_json, str):
            raise ValueError("Invalid path_dependencies_json.")

        with open(path_dependencies_json) as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise ValueError("Expected a dictionary in the JSON file.")

        task_item_list = d.get('task_dependency_details', [])

        for task_json in task_item_list:
            dependent_task_id = task_json['dependent_task_id']
            dependent_task = wbs_project.root_task.find_task_by_id(dependent_task_id)
            if not dependent_task:
                logger.debug(f"ERROR: Task with id {dependent_task_id} not found. Cannot set dependencies.")
                continue
            depends_on_task_id_list = task_json['depends_on_task_id_list']

            # Check if all uuid's in the depends_on_task_id_list are valid
            for depends_on_task_id in depends_on_task_id_list:
                depends_on_task = wbs_project.root_task.find_task_by_id(depends_on_task_id)
                if not depends_on_task:
                    logger.debug(f"ERROR: Task with id {depends_on_task_id} not found. Cannot set dependency for task {dependent_task_id}.")
                    continue

            dependent_task.set_field('depends_on_task_ids', depends_on_task_id_list)

            depends_on_task_explanation_list = task_json['depends_on_task_explanation_list']
            dependent_task.set_field('depends_on_task_explanations', depends_on_task_explanation_list)

    @staticmethod
    def extend_project_with_durations_json(wbs_project: WBSProject, path_durations_json: str):
        """
        Enrich the task hierarchy with time estimates from a task_durations JSON file.
        """
        if not isinstance(wbs_project, WBSProject):
            raise ValueError("Expected a WBSProject object.")
        if not isinstance(path_durations_json, str):
            raise ValueError("Invalid path_dependencies_json.")

        with open(path_durations_json) as f:
            task_duration_list = json.load(f)
        if not isinstance(task_duration_list, list):
            raise ValueError("Expected a list in the JSON file.")
        # logger.debug(f"task_duration_list length: {len(task_duration_list)}")

        for task_duration_index, task_duration_json in enumerate(task_duration_list):
            task_id = task_duration_json.get('task_id', None)
            if not is_valid_uuid(task_id):
                logger.error(f"Expected valid UUID, but got task_id: {task_id} for task_duration_index: {task_duration_index}")
                continue
            task = wbs_project.root_task.find_task_by_id(task_id)
            if not task:
                logger.error(f"Task with id {task_id} not found in WBSProject. Cannot set duration fields.")
                continue
            delay_risks = task_duration_json.get('delay_risks', None)
            if delay_risks:
                task.set_field('delay_risks', delay_risks)
            mitigation_strategy = task_duration_json.get('mitigation_strategy', None)
            if mitigation_strategy:
                task.set_field('mitigation_strategy', mitigation_strategy)
            days_min = task_duration_json.get('days_min', None)
            if days_min:
                task.set_field('days_min', days_min)
            days_max = task_duration_json.get('days_max', None)
            if days_max:
                task.set_field('days_max', days_max)
            days_realistic = task_duration_json.get('days_realistic', None)
            if days_realistic:
                task.set_field('days_realistic', days_realistic)

    @staticmethod
    def extend_project_with_decomposed_tasks_json(wbs_project: WBSProject, path_decomposed_tasks_json: str):
        """
        Enrich the task hierarchy with more subtasks from a decomposed_tasks JSON file.
        """
        if not isinstance(wbs_project, WBSProject):
            raise ValueError("Expected a WBSProject object.")
        if not isinstance(path_decomposed_tasks_json, str):
            raise ValueError("Invalid path_decomposed_tasks_json.")

        with open(path_decomposed_tasks_json) as f:
            task_list = json.load(f)
        if not isinstance(task_list, list):
            raise ValueError("Expected a list in the JSON file.")
        # logger.debug(f"Number of subtasks to be added. count: {len(task_list)}")

        for task_index, task_json in enumerate(task_list):
            task_id = task_json.get('id', None)
            if not is_valid_uuid(task_id):
                logger.error(f"Expected valid UUID, but got task_id: {task_id} for task_index: {task_index}. Cannot create subtask.")
                continue
            task_parent_id = task_json.get('parent_id', None)
            if not is_valid_uuid(task_parent_id):
                logger.error(f"Expected valid UUID, but got task_parent_id: {task_parent_id} for task_index: {task_index}. Cannot create subtask.")
                continue
            subtask_name = task_json.get('name', None)
            if not subtask_name:
                logger.error(f"Missing 'name' for task with id: {task_id}.")
                subtask_name = "MISSING_SUBTASK_NAME"

            parent_task = wbs_project.root_task.find_task_by_id(task_parent_id)
            if not parent_task:
                logger.error(f"Task with id {task_parent_id} not found. Cannot create subtask for child task {task_id}.")
                continue
            task = WBSTask(
                id=task_id,
                description=subtask_name
            )
            subtask_detailed_description = task_json.get('description', None)
            if subtask_detailed_description:
                task.set_field('detailed_description', subtask_detailed_description)
            subtask_resources_needed = task_json.get('resources_needed', None)
            if subtask_resources_needed:
                task.set_field('resources_needed', subtask_resources_needed)
            parent_task.task_children.append(task)
            # logger.debug(f"Added task {task_id} to parent task {task_parent_id}")

