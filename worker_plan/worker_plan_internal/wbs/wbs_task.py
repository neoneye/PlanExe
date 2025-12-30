from typing import Optional

class WBSTask:
    def __init__(self, id: str, description: str):
        if not isinstance(id, str):
            raise ValueError("Invalid id.")
        if not isinstance(description, str):
            raise ValueError("Invalid description.")
        self.id = id
        self.parent_id = None
        self.description = description
        self.task_children = []
        self.extra_fields = {}

    def set_field(self, field_name: str, field_value: any):
        if not isinstance(field_name, str):
            raise ValueError("Invalid field_name.")
        self.extra_fields[field_name] = field_value

    def __str__(self, level=0):
        indent = "  " * level
        parent_info = f" (Parent ID: {self.parent_id})" if self.parent_id else ""
        task_str = f"{indent}Task ID: {self.id}{parent_info}\n{indent}Description: {self.description}\n"
        
        if self.extra_fields:
            task_str += f"{indent}Extra Fields: {self.extra_fields}\n"
        
        for child in self.task_children:
            task_str += child.__str__(level + 1)
        
        return task_str

    def find_task_by_id(self, task_id: str) -> Optional['WBSTask']:
        if self.id == task_id:
            return self
        
        for child in self.task_children:
            found_task = child.find_task_by_id(task_id)
            if found_task:
                return found_task
        
        return None

    def to_dict(self):
        result = {
            "id": self.id,
            "description": self.description,
        }
        if self.parent_id is not None:
            result["parent_id"] = self.parent_id
        if len(self.extra_fields) > 0:
            result["extra_fields"] = self.extra_fields
        if len(self.task_children) > 0:
            result["task_children"] = [child.to_dict() for child in self.task_children]
        return result
    
    def task_ids(self) -> list[str]:
        """uuid's of all tasks in the tree hierarchy."""
        result = [self.id]
        for child in self.task_children:
            result.extend(child.task_ids())
        return result
    
class WBSProject:
    def __init__(self, root_task: WBSTask):
        self.root_task = root_task

    def __str__(self):
        return f"WBS Project:\n{self.root_task}"

    def find_task_by_id(self, task_id: str) -> Optional[WBSTask]:
        return self.root_task.find_task_by_id(task_id)

    def to_dict(self):
        return {
            "wbs_project": self.root_task.to_dict()
        }
    
    def from_dict(json_dict: dict) -> 'WBSProject':
        root_task_dict = json_dict["wbs_project"]
        root_task = WBSProject.from_dict_recursive(root_task_dict)
        return WBSProject(root_task)
    
    def from_dict_recursive(json_dict: dict) -> WBSTask:
        root_task = WBSTask(json_dict["id"], json_dict["description"])
        if "parent_id" in json_dict:
            root_task.parent_id = json_dict["parent_id"]
        if "extra_fields" in json_dict:
            root_task.extra_fields = json_dict["extra_fields"]
        if "task_children" in json_dict:
            root_task.task_children = [WBSProject.from_dict_recursive(child_dict) for child_dict in json_dict["task_children"]]
        return root_task
    
    def to_csv_string(self) -> str:
        from worker_plan_internal.wbs.create_wsb_table_csv import CreateWBSTableCSV
        instance = CreateWBSTableCSV(self)
        instance.execute()
        return instance.to_csv_string()

    def task_ids_with_one_or_more_children(self) -> set[str]:
        """id's of all tasks in the tree hierarchy that have one or more children."""
        task_ids = set()
        def visit_task(task: WBSTask):
            if len(task.task_children) > 0:
                task_ids.add(task.id)
            for child in task.task_children:
                visit_task(child)
        visit_task(self.root_task)
        return task_ids
