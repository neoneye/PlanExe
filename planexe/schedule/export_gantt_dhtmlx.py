"""
Export ProjectSchedule as Gantt chart, using the DHTMLX Gantt library.
https://dhtmlx.com/docs/products/dhtmlxGantt/

I'm a developer, not a license lawyer. DHTMLX Gantt is GPL. PlanExe is MIT.
AFAIK, linking to a GPL component via a CDN from an MIT-licensed project is 
considered compatible and does not force the MIT project code to become GPL.

PROMPT> python -m planexe.schedule.export_gantt_dhtmlx
"""
from datetime import date, timedelta
import json
import html
import re
import importlib.resources
from typing import Optional
from planexe.schedule.schedule import ProjectSchedule, DependencyType, PredecessorInfo
from planexe.utils.dedent_strip import dedent_strip

class ExportGanttDHTMLX:
    @staticmethod
    def _dep_summary(preds: list[PredecessorInfo]) -> str:
        """Return 'A FS, B SS+2' etc. for the tooltip/label."""
        parts = []
        for p in preds:
            lag = p.lag
            lag_txt = ("" if lag == 0
                    else f"{'+' if lag > 0 else ''}{lag}")   # +2  or  -1
            parts.append(f"{p.activity_id} {p.dep_type.value}{lag_txt}")
        return ", ".join(parts)

    @staticmethod
    def _get_dhtmlx_link_type(dep_type: DependencyType) -> str:
        """Convert our dependency types to DHTMLX Gantt link types.
        
        https://docs.dhtmlx.com/gantt/desktop__link_properties.html
        """
        return {
            DependencyType.FS: "0",  # finish_to_start
            DependencyType.SS: "1",  # start_to_start
            DependencyType.FF: "2",  # finish_to_finish
            DependencyType.SF: "3"   # start_to_finish
        }[dep_type]

    @staticmethod
    def _javascript_csv_filename(title: str) -> str:
        """
        Convert title to a sanitized filename for the CSV file.
        The filename is wrapped in double quotes.
        
        Parameters
        ----------
        title : str
            The title to convert to a filename
            
        Returns
        -------
        str
            A sanitized filename with format '"PlanExe_Export_{sanitized_title}.csv"'
        """
        sanitized = re.sub(r'[^a-zA-Z0-9]+', '_', title).strip('_') or "MissingTitle"
        return f'"PlanExe_Export_{sanitized}.csv"'

    @staticmethod
    def _javascript_csv_data(csv_data: Optional[str]) -> str:
        """
        Convert CSV data to a JavaScript-safe string value.
        
        If csv_data is None, returns "null".
        If csv_data is a string, convert it to a JavaScript-safe string value.
        
        Parameters
        ----------
        csv_data : Optional[str]
            The CSV data to convert, or None
            
        Returns
        -------
        str
            JavaScript-safe string value: "null" if input is None, otherwise sanitized and quoted CSV data
        """
        if csv_data is None:
            return "null"

        return json.dumps(csv_data)

    @staticmethod
    def to_dhtmlx_gantt_data(
        project_schedule: ProjectSchedule,
        project_start: date,
        task_ids_to_treat_as_project_activities: set[str],
        task_id_to_tooltip_dict: dict[str, str]
    ) -> dict:
        """
        Return a dict with tasks and links ready for DHTMLX Gantt initialization.

        Parameters
        ----------
        project_schedule
            The project schedule to visualize
        project_start
            ``datetime.date`` → use it as day 0  
        """
        if not isinstance(project_schedule, ProjectSchedule):
            raise ValueError("project_schedule must be a ProjectSchedule")
        if not isinstance(project_start, date):
            raise ValueError("project_start must be a date")
        if not isinstance(task_ids_to_treat_as_project_activities, set):
            raise ValueError("task_ids_to_treat_as_project_activities must be a set")
        if not isinstance(task_id_to_tooltip_dict, dict):
            raise ValueError("task_id_to_tooltip_dict must be a dict")

        tasks = []
        links = []
        link_id = 1

        # order tasks by early‑start so the chart looks natural
        for act in sorted(project_schedule.activities.values(), key=lambda a: a.es):
            start = project_start + timedelta(days=float(act.es))
            end = project_start + timedelta(days=float(act.ef))
            
            title = act.title if act.title else act.id

            fallback_tooltip = dedent_strip(f"""
            <b>{html.escape(title)}</b><br>
            """)

            tooltip = task_id_to_tooltip_dict.get(act.id, fallback_tooltip)

            # Create task
            task = {
                "id": act.id,
                "text": title,
                "custom_tooltip": tooltip,
                "start_date": start.isoformat(),
                "duration": float(act.duration),
                "progress": 0,
                "open": True,
                "meta": ExportGanttDHTMLX._dep_summary(act.parsed_predecessors)
            }
            if act.parent_id:
                task["parent"] = act.parent_id
            if act.id in task_ids_to_treat_as_project_activities:
                task["type"] = "project"
                del task["start_date"]
                del task["duration"]
            tasks.append(task)

            # Create links for dependencies
            for pred in act.parsed_predecessors:
                is_leaf = act.id not in task_ids_to_treat_as_project_activities
                is_parent_project = pred.activity_id in task_ids_to_treat_as_project_activities
                if is_leaf and is_parent_project:
                    # print(f"Skipping link {pred.activity_id} -> {act.id} because it's a leaf activity and the parent is a project")
                    continue
                link = {
                    "id": f"link_{link_id}",
                    "source": pred.activity_id,
                    "target": act.id,
                    "type": ExportGanttDHTMLX._get_dhtmlx_link_type(pred.dep_type),
                    "lag": float(pred.lag)
                }
                links.append(link)
                link_id += 1

        return {
            "tasks": tasks,
            "links": links
        }

    @staticmethod
    def save(project_schedule: ProjectSchedule, path: str, project_start: date, **kwargs) -> None:
        """
        Write a self‑contained HTML page with an embedded DHTMLX Gantt chart.
        Simply open the resulting file in any modern browser.

        Parameters
        ----------
        project_schedule
            The project schedule to visualize
        path
            Where to save the HTML file
        project_start
            ``datetime.date`` → use it as day 0  
        title
            Shown at the top of the chart.
        csv_data
            CSV data to embed in the HTML file.
            If ``None``, the "Export to CSV" button is hidden.
            If a string, it's the CSV data, eg: `"hello;csv;world"` and the button is shown.
        """
        title = kwargs.get("title", "Project schedule")
        csv_data: Optional[str] = kwargs.get("csv_data", None)
        task_ids_to_treat_as_project_activities = kwargs.get("task_ids_to_treat_as_project_activities", set())
        task_id_to_tooltip_dict = kwargs.get("task_id_to_tooltip_dict", {})
        
        gantt_data = ExportGanttDHTMLX.to_dhtmlx_gantt_data(
            project_schedule, 
            project_start, 
            task_ids_to_treat_as_project_activities, 
            task_id_to_tooltip_dict
        )
        gantt_data_json = json.dumps(gantt_data, indent=2)

        template_path = importlib.resources.files('planexe.schedule') / 'export_gantt_dhtmlx_template.html'
        with importlib.resources.as_file(template_path) as path_to_template:
            with open(path_to_template, "r", encoding="utf-8") as f:
                html_template = f.read()
        
        csv_data_value = ExportGanttDHTMLX._javascript_csv_data(csv_data)
        csv_filename_value = ExportGanttDHTMLX._javascript_csv_filename(title)

        html_content = html_template.replace("PLACEHOLDER_TITLE", html.escape(title))
        html_content = html_content.replace("PLACEHOLDER_GANTT_DATA_DHTMLX", gantt_data_json)
        html_content = html_content.replace("PLACEHOLDER_GANTT_DATA_CSV", csv_data_value)
        html_content = html_content.replace("PLACEHOLDER_GANTT_FILENAME_CSV", csv_filename_value)

        with open(path, "w", encoding="utf-8") as fp:
            fp.write(html_content)

if __name__ == "__main__":
    from planexe.schedule.parse_schedule_input_data import parse_schedule_input_data
    from planexe.schedule.schedule import ProjectSchedule
    from planexe.utils.dedent_strip import dedent_strip

    input = dedent_strip("""
        Activity;Predecessor;Duration;Comment
        A;-;3;Start node
        B;A(FS2);2;
        C;A(SS);2; C starts when A starts
        D;B(SS1);4; D starts 1 after B starts
        E;C(SF3);1; E starts 3 after C finishes (E_ef >= C_es + 3)? No SF is Start-Finish E_lf >= C_es + lag + E_dur
        F;C(FF3);2; F finishes 3 after C finishes
        G;D(SS1),E;4;Multiple preds (E is FS default)
        H;F(SF2),G;3;Multiple preds (G is FS default)
    """)

    csv_data = "demo;of;csv\na;b;c\nx;y;z"
    project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))
    project_start = date(1984, 12, 30)
    ExportGanttDHTMLX.save(project_schedule, "gantt_dhtmlx.html", project_start, csv_data=csv_data) 