import unittest
import os
from ..wbs_populate import WBSPopulate

class TestWBSPopulate(unittest.TestCase):
    def test_project_from_level1_json(self):
        """
        Create a WBSProject from a level 1 JSON file.
        """
        # Arrange
        path_level1_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level1.json')

        # Act
        wbs_project = WBSPopulate.project_from_level1_json(path_level1_json)

        # Assert
        self.assertEqual(wbs_project.root_task.id, "2900c638-8e2a-4b7b-96ea-e096a7bc8b5e")
        self.assertEqual(wbs_project.root_task.description, "Denmark Solar Farm")
        self.assertEqual(wbs_project.root_task.extra_fields['final_deliverable'], "Operational Solar Farm")

    def test_extend_project_with_level2_json(self):
        """
        Create a WBSProject with a hierarchy of tasks.
        """
        # Arrange
        path_level1_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level1.json')
        path_level2_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level2.json')
        wbs_project = WBSPopulate.project_from_level1_json(path_level1_json)

        # Act
        WBSPopulate.extend_project_with_level2_json(wbs_project, path_level2_json)

        # Assert
        task1 = wbs_project.find_task_by_id("9180ee65-d7cf-47fe-ad75-b4bf073b4a16")
        self.assertIsNotNone(task1)
        self.assertEqual(task1.description, "Design Solar Farm Layout")
        self.assertEqual(len(task1.task_ids()), 1)

        task2 = wbs_project.find_task_by_id("99b2720a-d390-43b4-af18-da889d974a1a")
        self.assertIsNotNone(task2)
        self.assertEqual(task2.description, "Project Close-Out")
        self.assertEqual(len(task2.task_ids()), 3)

    def test_extend_project_with_dependencies_json(self):
        """
        Establish dependencies between tasks.
        """
        # Arrange
        path_level1_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level1.json')
        path_level2_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level2.json')
        path_dependencies_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solarfarm_task_dependencies.json')
        wbs_project = WBSPopulate.project_from_level1_json(path_level1_json)
        WBSPopulate.extend_project_with_level2_json(wbs_project, path_level2_json)

        # Act
        WBSPopulate.extend_project_with_dependencies_json(wbs_project, path_dependencies_json)

        # Assert
        task1 = wbs_project.find_task_by_id("6e6e7e83-8db9-4ac9-88d3-0aeda252a19e")
        self.assertIsNotNone(task1)
        self.assertEqual(task1.description, "Procure Land for Solar Farm")
        self.assertEqual(task1.extra_fields['depends_on_task_ids'], ["303c1a0b-9609-4297-8862-5b42a6230b2b"])
        self.assertEqual(task1.extra_fields['depends_on_task_explanations'], ["Land Acquisition and Preparation must be completed before Procuring Land for Solar Farm starts."])

    def test_extend_project_with_durations_json(self):
        """
        Assign time estimates to tasks.
        """
        # Arrange
        path_level1_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level1.json')
        path_level2_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level2.json')
        path_durations_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solarfarm_task_durations.json')
        wbs_project = WBSPopulate.project_from_level1_json(path_level1_json)
        WBSPopulate.extend_project_with_level2_json(wbs_project, path_level2_json)

        # Act
        WBSPopulate.extend_project_with_durations_json(wbs_project, path_durations_json)

        # Assert
        task1 = wbs_project.find_task_by_id("73f16e9d-58f0-4447-b8e2-beb13eedc1e5")
        self.assertIsNotNone(task1)
        self.assertEqual(task1.description, "Develop Detailed Project Plans")
        self.assertEqual(task1.extra_fields["delay_risks"], "Delays in creating detailed project plans due to complexity of the solar farm project, potential for changes to be made after completion.")
        self.assertEqual(task1.extra_fields["mitigation_strategy"], "Establish clear communication channels with stakeholders, utilize project management tools to track progress, and schedule regular meetings to ensure timely completion of the task.")
        self.assertEqual(task1.extra_fields["days_min"], 15)
        self.assertEqual(task1.extra_fields["days_max"], 30)
        self.assertEqual(task1.extra_fields["days_realistic"], 22)

    def test_extend_project_with_subtasks_json(self):
        """
        Bigger tasks that have been decomposed into smaller subtasks.
        """
        # Arrange
        path_level1_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level1.json')
        path_level2_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level2.json')
        path_level3_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solarfarm_wbs_level3.json')
        wbs_project = WBSPopulate.project_from_level1_json(path_level1_json)
        WBSPopulate.extend_project_with_level2_json(wbs_project, path_level2_json)

        # Act
        WBSPopulate.extend_project_with_decomposed_tasks_json(wbs_project, path_level3_json)
        # print(wbs_project.to_csv_string())

        # Assert
        task1 = wbs_project.find_task_by_id("6e6e7e83-8db9-4ac9-88d3-0aeda252a19e")
        self.assertIsNotNone(task1)
        self.assertEqual(task1.description, "Procure Land for Solar Farm")
        self.assertEqual(len(task1.task_children), 3)

        task2 = wbs_project.find_task_by_id("7570b5c4-50bc-4ba8-bb80-db193521759a")
        self.assertIsNotNone(task2)
        self.assertEqual(task2.description, "Conduct Environmental Impact Assessments")
        self.assertEqual(len(task2.task_children), 3)

        task3 = wbs_project.find_task_by_id("2d6452f9-274f-4160-aca4-642e9b0c6446")
        self.assertIsNotNone(task3)
        self.assertEqual(task3.description, "Obtain Land Permit")
        self.assertEqual(len(task3.task_children), 0)
        self.assertEqual(task3.extra_fields["detailed_description"], "Secure necessary permits for land use and environmental impact assessments.")
        self.assertEqual(task3.extra_fields["resources_needed"], ["Land permit"])

    def test_task_ids_with_one_or_more_children(self):
        """
        Extract only the parent tasks and ignore the leaf tasks.
        """
        # Arrange
        path_level1_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level1.json')
        path_level2_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level2.json')
        wbs_project = WBSPopulate.project_from_level1_json(path_level1_json)
        WBSPopulate.extend_project_with_level2_json(wbs_project, path_level2_json)

        # Act
        task_ids = wbs_project.task_ids_with_one_or_more_children()

        expected = set([
            "2900c638-8e2a-4b7b-96ea-e096a7bc8b5e", # root task
            "303c1a0b-9609-4297-8862-5b42a6230b2b",
            "1d3a023b-9c92-401a-9010-70e08109b0a3",
            "44fd780c-3052-4323-94c7-bdd86ca6d12f",
            "74d93fb2-6d2d-4ef8-b91a-ce496860faae",
            "d5d79ebd-c7eb-47ed-b955-48c85541259d",
            "c518c687-b757-4ba1-8af4-08b3e61dff67",
            "99b2720a-d390-43b4-af18-da889d974a1a",
        ])
        self.assertEqual(task_ids, expected)
