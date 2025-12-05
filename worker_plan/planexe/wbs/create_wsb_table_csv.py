import json
from planexe.wbs.wbs_task import WBSTask, WBSProject

class CreateWBSTableCSV:
    """
    Create a CSV representation of a Work Breakdown Structure (WBS).
    """
    def __init__(self, wsb_project: WBSProject):
        if not isinstance(wsb_project, WBSProject):
            raise ValueError("wsb_project must be an instance of WBSProject")
        self.wsb_project = wsb_project
        self.separator = ';'
        self.csv_rows = []

    def max_level(self, task: WBSTask, level=0):
        max_level = level
        for child in task.task_children:
            max_level = max(max_level, self.max_level(child, level + 1))
        return max_level

    def visit_task(self, task: WBSTask, number_of_levels: int, level=0):
        columns = []
        for i in range(number_of_levels):
            s = ''
            if i == level:
                s = task.description
            columns.append(s)
        columns.append(task.id)
        csv_row = self.separator.join(columns)
        self.csv_rows.append(csv_row)
        for child in task.task_children:
            self.visit_task(child, number_of_levels, level + 1)

    def execute(self):
        number_of_levels = self.max_level(self.wsb_project.root_task) + 1
        columns = []
        for i in range(number_of_levels):
            columns.append(f"Level {i+1}")
        columns.append("Task ID")
        csv_row = self.separator.join(columns)
        self.csv_rows.append(csv_row)

        self.visit_task(self.wsb_project.root_task, number_of_levels)

    def to_csv_string(self):
        return '\n'.join(self.csv_rows)

if __name__ == "__main__":
    # TODO: Eliminate hardcoded paths
    path = '/Users/neoneye/Desktop/planexe_data/011-wbs_project.json'

    print(f"loading file: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        wsb_project_json = json.load(f)

    wsb_project = WBSProject.from_dict(wsb_project_json)

    instance = CreateWBSTableCSV(wsb_project)
    instance.execute()
    print("Generated wbs_table.csv")
    print(instance.to_csv_string())