"""
Create HTML tooltips for all tasks in the WBSProject.

Currently the root task and the parent tasks have a way too brief tooltip.
I would like to see a more detailed tooltip for the parent tasks.
"""
from planexe.wbs.wbs_task import WBSTask, WBSProject
import html

class WBSTaskHTMLTooltip:
    @staticmethod
    def html_tooltips(wbs_project: WBSProject) -> dict[str, str]:
        def formal_list_as_html_bullet_points(list_of_items: list[str]) -> str:
            return "<ul>" + "".join([f"<li>{html.escape(item)}</li>" for item in list_of_items]) + "</ul>"

        task_id_to_tooltip_dict: dict[str, str] = {}

        def visit_task(task: WBSTask):
            fields = task.extra_fields

            html_items: list[str] = []

            html_items.append(f"<b>{html.escape(task.description)}</b>")

            if 'final_deliverable' in fields:
                html_items.append("<b>Final deliverable:</b>")
                html_items.append(html.escape(fields['final_deliverable']))

            if 'detailed_description' in fields:
                html_items.append(html.escape(fields['detailed_description']))

            if 'resources_needed' in fields:
                html_items.append("<b>Resources needed:</b>")
                html_items.append(formal_list_as_html_bullet_points(fields['resources_needed']))

            if len(html_items) > 0:
                task_id_to_tooltip_dict[task.id] = "<br>".join(html_items)

            for child in task.task_children:
                visit_task(child)
        visit_task(wbs_project.root_task)

        return task_id_to_tooltip_dict
