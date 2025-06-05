import json
import pandas as pd
from pandas import DataFrame
from dataclasses import dataclass

@dataclass
class WBSTableForCostEstimation:
    wbs_table_df: DataFrame

    @classmethod
    def create(cls, path_wbs_table_csv: str, path_wbs_project_json: str) -> 'WBSTableForCostEstimation':
        """
        Enrich an existing Work Breakdown Structure (WBS) table with columns for cost estimation.
        """

        if not isinstance(path_wbs_table_csv, str):
            raise ValueError("Invalid path_wbs_table_csv.")
        if not isinstance(path_wbs_project_json, str):
            raise ValueError("Invalid path_wbs_project_json.")
        
        with open(path_wbs_project_json, 'r', encoding='utf-8') as f:
            wbs_project_json = json.load(f)

        df = pd.read_csv(path_wbs_table_csv, sep=';')

        # columns with estimated duration of each task
        df['days_min'] = 0
        df['days_max'] = 0
        df['days_realistic'] = 0
        df['delay_risks'] = None
        df['resources_needed'] = None

        def visit_json_item(item: dict, level: int, verbose: bool = False):
            if verbose:
                print(f"{'  ' * level}visit")
            if not isinstance(item, dict):
                if verbose:
                    print(f"{'  ' * level}item is not a dict")
                return
            task_id = item.get('id', None)
            extra_fields = item.get('extra_fields', {})
            if task_id is not None and extra_fields is not None:
                if verbose:
                    print(f"{'  ' * level}task_id: {task_id}")
                for key, value in extra_fields.items():
                    if key == 'days_min':
                        df.loc[df['Task ID'] == task_id, 'days_min'] = int(value)
                    elif key == 'days_max':
                        df.loc[df['Task ID'] == task_id, 'days_max'] = int(value)
                    elif key == 'days_realistic':
                        df.loc[df['Task ID'] == task_id, 'days_realistic'] = int(value)
                    elif key == 'delay_risks':
                        df.loc[df['Task ID'] == task_id, 'delay_risks'] = value
                    elif key == 'resources_needed':
                        s = None
                        if isinstance(value, list):
                            s = ','.join(value)
                        elif isinstance(value, str):
                            s = value
                        df.loc[df['Task ID'] == task_id, 'resources_needed'] = s
                    else:
                        if verbose:
                            print(f"{'  ' * level}{key}: {value} (ignored)")
            task_children = item.get('task_children', [])
            for task_child in task_children:
                visit_json_item(task_child, level + 1, verbose)

        verbose_traverse = False
        # traverse the hierarchy of tasks, find the corresponding row in the wbs_df, and update the days columns
        visit_json_item(wbs_project_json['wbs_project'], 0, verbose_traverse)

        return WBSTableForCostEstimation(wbs_table_df=df)

if __name__ == "__main__":
    import os

    basepath = os.path.join(os.path.dirname(__file__), 'test_data')
    path_csv = os.path.join(basepath, 'wbs_table.csv')
    path_json = os.path.join(basepath, 'wbs_project.json')

    instance = WBSTableForCostEstimation.create(path_csv, path_json)
    print(instance.wbs_table_df)

