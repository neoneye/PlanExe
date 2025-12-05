"""
Create tooltips for all tasks in the WBSProject.

Currently the root task and the parent tasks have a way too brief tooltip.
I would like to see a more detailed tooltip for the parent tasks.
"""
from planexe.wbs.wbs_task import WBSTask, WBSProject
import html

class WBSTaskTooltip:
    @staticmethod
    def text_tooltips(wbs_project: WBSProject) -> dict[str, str]:
        """
        Create text tooltips for all tasks in the WBSProject.

        The returned dictionary is a mapping of task ID to text tooltip.
        """
        def format_list_as_text(list_of_items: list[str]) -> str:
            return "\n".join([f"• {item}" for item in list_of_items])

        task_id_to_tooltip_dict: dict[str, str] = {}

        def visit_task(task: WBSTask):
            fields = task.extra_fields

            items: list[str] = []

            items.append(str(task.description))

            if 'final_deliverable' in fields:
                items.append("\nFinal deliverable:")
                items.append(str(fields['final_deliverable']))

            if 'detailed_description' in fields:
                items.append("\nDescription:")
                items.append(str(fields['detailed_description']))

            if 'resources_needed' in fields:
                items.append("\nResources needed:")
                items.append(format_list_as_text(fields['resources_needed']))

            if len(items) > 0:
                task_id_to_tooltip_dict[task.id] = "\n".join(items)

            for child in task.task_children:
                visit_task(child)
        
        visit_task(wbs_project.root_task)

        return task_id_to_tooltip_dict 
    
    @staticmethod
    def html_tooltips(wbs_project: WBSProject) -> dict[str, str]:
        """
        Create HTML tooltips for all tasks in the WBSProject.

        The returned dictionary is a mapping of task ID to HTML tooltip.
        """
        def formal_list_as_html_bullet_points(list_of_items: list[str]) -> str:
            return "<ul>" + "".join([f"<li>{html.escape(item)}</li>" for item in list_of_items]) + "</ul>"

        task_id_to_tooltip_dict: dict[str, str] = {}

        def visit_task(task: WBSTask):
            fields = task.extra_fields

            items: list[str] = []

            items.append(f"<b>{html.escape(task.description)}</b>")

            if 'final_deliverable' in fields:
                items.append("<b>Final deliverable:</b>")
                items.append(html.escape(fields['final_deliverable']))

            if 'detailed_description' in fields:
                items.append(html.escape(fields['detailed_description']))

            if 'resources_needed' in fields:
                items.append("<b>Resources needed:</b>")
                items.append(formal_list_as_html_bullet_points(fields['resources_needed']))

            if len(items) > 0:
                task_id_to_tooltip_dict[task.id] = "<br>".join(items)

            for child in task.task_children:
                visit_task(child)
        visit_task(wbs_project.root_task)

        return task_id_to_tooltip_dict
