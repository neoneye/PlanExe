import unittest
import os
from ..wbs_table_for_cost_estimation import WBSTableForCostEstimation

class TestWBSTableForCostEstimation(unittest.TestCase):
    def test_days_min_max_realistic(self):
        # Arrange
        path_csv = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'wbs_table.csv')
        path_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'wbs_project.json')
        # Act
        wbs_table = WBSTableForCostEstimation.create(path_csv, path_json)
        # Assert
        wbs_table_df = wbs_table.wbs_table_df
        df = wbs_table_df.loc[wbs_table_df['Task ID'] == '53129dfa-f0c5-469f-be45-16663dfb40d1']
        self.assertEqual(df['days_min'].values[0], 100)
        self.assertEqual(df['days_max'].values[0], 200)
        self.assertEqual(df['days_realistic'].values[0], 150)

    def test_delay_risks(self):
        # Arrange
        path_csv = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'wbs_table.csv')
        path_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'wbs_project.json')
        # Act
        wbs_table = WBSTableForCostEstimation.create(path_csv, path_json)
        # Assert
        wbs_table_df = wbs_table.wbs_table_df
        df = wbs_table_df.loc[wbs_table_df['Task ID'] == '4ea89bdc-6772-4b4c-b3be-172ab4f2770f']
        self.assertEqual(df['delay_risks'].values[0], 'The remote may be found but could be non-functional due to damage or battery depletion.')

    def test_resources_needed(self):
        # Arrange
        path_csv = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'wbs_table.csv')
        path_json = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'wbs_project.json')
        # Act
        wbs_table = WBSTableForCostEstimation.create(path_csv, path_json)
        # Assert
        wbs_table_df = wbs_table.wbs_table_df
        df = wbs_table_df.loc[wbs_table_df['Task ID'] == '7ed1bb76-ca0a-4c8e-9475-f590ac39a509']
        self.assertEqual(df['resources_needed'].values[0], 'Time,Household members')
