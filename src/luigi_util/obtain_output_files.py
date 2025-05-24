"""
In order to make a progress bar, we need to know all the files that will be created by the pipeline.
This class identifies all the output files from a Luigi task graph.

It doesn't identify extra files outputted by the tasks.
There are several tasks that outputs extra files, these are not identified by this class.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union
import luigi
import logging

logger = logging.getLogger(__name__)

@dataclass(frozen=True) # Makes the dataclass immutable
class ObtainOutputFiles:
    """
    Collects and stores output filenames from a Luigi task graph.
    This class is immutable once created.
    """
    collected_outputs: List[Dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def execute(root_task: luigi.Task) -> 'ObtainOutputFiles':
        
        # --- State and helper function inside execute ---
        _visited_task_ids_local: Set[int] = set()
        _collected_outputs_local: List[Dict[str, Any]] = []

        def _collect_recursive_local(current_task: luigi.Task, indent_level: int = 0):
            task_instance_id = id(current_task)

            if task_instance_id in _visited_task_ids_local:
                return
            _visited_task_ids_local.add(task_instance_id)

            task_info: Dict[str, Any] = {
                "task_name": str(current_task),
                "outputs": [],
                "dependencies": [] # Store names of dependent tasks
            }
            
            # Collect outputs
            try:
                outputs = current_task.output()
                formatted_outputs: Union[List[str], str, Dict[str,str]]
                if isinstance(outputs, dict):
                    formatted_outputs = {
                        k: str(v.path if hasattr(v, 'path') else v) 
                        for k, v in outputs.items()
                    }
                elif isinstance(outputs, (list, tuple)):
                    formatted_outputs = [
                        str(o.path if hasattr(o, 'path') else o) 
                        for o in outputs
                    ]
                elif hasattr(outputs, 'path'): 
                    formatted_outputs = str(outputs.path)
                else: 
                    formatted_outputs = str(outputs)
                task_info["outputs"] = formatted_outputs
            except Exception as e:
                logger.error(f"Error getting outputs for {current_task}: {e}", exc_info=True)
                task_info["outputs"] = f"Error: {e}"

            _collected_outputs_local.append(task_info)

            # Get and process dependencies
            try:
                dependencies = current_task.requires() if hasattr(current_task, 'requires') else None
            except Exception as e:
                logger.error(f"Error getting dependencies for {current_task}: {e}", exc_info=True)
                return 

            if isinstance(dependencies, dict):
                task_info["dependencies"] = [str(dep_task) for dep_task in dependencies.values()]
                for dep_task_instance in dependencies.values():
                    _collect_recursive_local(dep_task_instance, indent_level + 1)
            elif isinstance(dependencies, (list, tuple)):
                task_info["dependencies"] = [str(dep_task) for dep_task in dependencies]
                for dep_task_instance in dependencies:
                    _collect_recursive_local(dep_task_instance, indent_level + 1)
            elif isinstance(dependencies, luigi.Task):
                task_info["dependencies"] = [str(dependencies)]
                _collect_recursive_local(dependencies, indent_level + 1)
            elif dependencies: 
                logger.warning(f"Unknown/unhandled dependency type: {type(dependencies)} for task {current_task}")
        # --- End of local state and helper function ---

        _collect_recursive_local(root_task)
        return ObtainOutputFiles(collected_outputs=_collected_outputs_local)

    def get_all_filepaths(self) -> List[str]:
        """Extracts all unique file paths from the collected outputs."""
        filepaths = set()
        for task_info in self.collected_outputs:
            outputs = task_info.get("outputs")
            if isinstance(outputs, str) and ("/" in outputs or "\\" in outputs):
                filepaths.add(outputs)
            elif isinstance(outputs, list):
                for item in outputs:
                    if isinstance(item, str) and ("/" in item or "\\" in item):
                        filepaths.add(item)
            elif isinstance(outputs, dict):
                for item in outputs.values():
                    if isinstance(item, str) and ("/" in item or "\\" in item):
                        filepaths.add(item)
        return sorted(list(filepaths))
