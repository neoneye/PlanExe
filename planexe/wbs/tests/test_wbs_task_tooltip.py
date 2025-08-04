import unittest
import os
from ..wbs_task import WBSProject
from ..wbs_populate import WBSPopulate
from ..wbs_task_tooltip import WBSTaskTooltip

class TestWBSTaskTooltip(unittest.TestCase):
    def create_wbs_project_solarfarm(self) -> WBSProject:
        path_level1_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level1.json')
        path_level2_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solorfarm_wbs_level2.json')
        path_level3_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solarfarm_wbs_level3.json')
        path_dependencies_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'solarfarm_task_dependencies.json')
        wbs_project = WBSPopulate.project_from_level1_json(path_level1_json)
        WBSPopulate.extend_project_with_level2_json(wbs_project, path_level2_json)
        WBSPopulate.extend_project_with_dependencies_json(wbs_project, path_dependencies_json)
        WBSPopulate.extend_project_with_decomposed_tasks_json(wbs_project, path_level3_json)
        return wbs_project
    
    def test_text_tooltips_root_task(self):
        # Arrange
        wbs_project = self.create_wbs_project_solarfarm()

        # Act
        task_id_to_tooltip_dict = WBSTaskTooltip.text_tooltips(wbs_project)

        # Assert
        tooltip = task_id_to_tooltip_dict["2900c638-8e2a-4b7b-96ea-e096a7bc8b5e"]
        self.assertIn("Denmark Solar Farm", tooltip)
        self.assertIn("\n\nFinal deliverable:\nOperational Solar Farm", tooltip)

    def test_text_tooltips_task_with_children(self):
        # Arrange
        wbs_project = self.create_wbs_project_solarfarm()

        # Act
        task_id_to_tooltip_dict = WBSTaskTooltip.text_tooltips(wbs_project)

        # Assert
        tooltip = task_id_to_tooltip_dict["2d6452f9-274f-4160-aca4-642e9b0c6446"]
        self.assertIn("Obtain Land Permit", tooltip)
        self.assertIn("\n\nResources needed:\n", tooltip)
        self.assertIn("• Land permit", tooltip)
        
    def test_html_tooltips_root_task(self):
        # Arrange
        wbs_project = self.create_wbs_project_solarfarm()

        # Act
        task_id_to_tooltip_dict = WBSTaskTooltip.html_tooltips(wbs_project)

        # Assert
        tooltip = task_id_to_tooltip_dict["2900c638-8e2a-4b7b-96ea-e096a7bc8b5e"]
        self.assertIn("<b>Denmark Solar Farm</b>", tooltip)
        self.assertIn("<b>Final deliverable:</b><br>Operational Solar Farm", tooltip)

    def test_html_tooltips_task_with_children(self):
        # Arrange
        wbs_project = self.create_wbs_project_solarfarm()

        # Act
        task_id_to_tooltip_dict = WBSTaskTooltip.html_tooltips(wbs_project)

        # Assert
        tooltip = task_id_to_tooltip_dict["2d6452f9-274f-4160-aca4-642e9b0c6446"]
        self.assertIn("<b>Obtain Land Permit</b><br>Secure necessary permits for land use and environmental impact assessments.<br>", tooltip)
        self.assertIn("<b>Resources needed:</b><br><ul><li>Land permit</li></ul>", tooltip)
