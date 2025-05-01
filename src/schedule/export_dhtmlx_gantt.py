"""
Export Project Plan as Gantt chart, using the DHTMLX Gantt library.
https://dhtmlx.com/docs/products/dhtmlxGantt/

PROMPT> python -m src.schedule.export_dhtmlx_gantt
"""
from datetime import date, timedelta
import json
import html
from src.schedule.schedule import ProjectPlan, DependencyType, PredecessorInfo

class ExportDHTMLXGantt:
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
    def to_dhtmlx_gantt_data(
        project_plan: ProjectPlan,
        project_start: date | str | None = None,
    ) -> dict:
        """
        Return a dict with tasks and links ready for DHTMLX Gantt initialization.

        Parameters
        ----------
        project_plan
            The project plan to visualize
        project_start
            • ``datetime.date`` → use it as day 0  
            • ``"YYYY‑MM‑DD"``  → parsed with ``date.fromisoformat``  
            • ``None``         → today (``date.today()``)
        """
        if project_start is None:
            project_start = date.today()
        elif isinstance(project_start, str):
            project_start = date.fromisoformat(project_start)

        tasks = []
        links = []
        link_id = 1

        # order tasks by early‑start so the chart looks natural
        for act in sorted(project_plan.activities.values(), key=lambda a: a.es):
            start = project_start + timedelta(days=float(act.es))
            end = project_start + timedelta(days=float(act.ef))
            
            title = act.title if act.title else act.id

            # Create task
            task = {
                "id": act.id,
                "text": title,
                "start_date": start.isoformat(),
                "duration": float(act.duration),
                "progress": 0,
                "open": True,
                "meta": ExportDHTMLXGantt._dep_summary(act.parsed_predecessors)
            }
            tasks.append(task)

            # Create links for dependencies
            for pred in act.parsed_predecessors:
                link = {
                    "id": f"link_{link_id}",
                    "source": pred.activity_id,
                    "target": act.id,
                    "type": ExportDHTMLXGantt._get_dhtmlx_link_type(pred.dep_type),
                    "lag": float(pred.lag)
                }
                links.append(link)
                link_id += 1

        return {
            "data": tasks,
            "links": links
        }

    @staticmethod
    def save(project_plan: ProjectPlan, path: str, **kwargs) -> None:
        """
        Write a self‑contained HTML page with an embedded DHTMLX Gantt chart.
        Simply open the resulting file in any modern browser.

        Parameters
        ----------
        project_plan
            The project plan to visualize
        path
            Where to save the HTML file
        project_start
            • ``datetime.date`` → use it as day 0  
            • ``"YYYY‑MM‑DD"``  → parsed with ``date.fromisoformat``  
            • ``None``         → today (``date.today()``)
        title
            Shown at the top of the chart.
        """
        title = kwargs.get("title", "Project schedule")
        project_start = kwargs.get("project_start", None)

        gantt_data = ExportDHTMLXGantt.to_dhtmlx_gantt_data(project_plan, project_start)
        gantt_data_json = json.dumps(gantt_data, indent=2)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="https://cdn.dhtmlx.com/gantt/edge/dhtmlxgantt.css">
  <script src="https://cdn.dhtmlx.com/gantt/edge/dhtmlxgantt.js"></script>
  <style>
    body {{
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
        margin: 2rem;
    }}
    .gantt_container {{
        width: 100%;
        height: 80vh;
        border: 1px solid #ccc;
        border-radius: .5rem;
    }}
  </style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div id="gantt_container" class="gantt_container"></div>

<script>
    // Initialize Gantt
    gantt.config.date_format = "%Y-%m-%d";
    gantt.config.scale_unit = "month";
    gantt.config.step = 1;
    gantt.config.subscales = [
        {{unit: "day", step: 1, date: "%d"}}
    ];
    
    // Configure tooltips
    gantt.templates.tooltip_text = function(start, end, task) {{
        return "<b>" + task.text + "</b><br>" +
               "Start: " + gantt.templates.tooltip_date_format(start) + "<br>" +
               "End: " + gantt.templates.tooltip_date_format(end) + "<br>" +
               "Duration: " + task.duration + " days<br>" +
               "Dependencies: " + (task.meta || "None");
    }};

    // Load data and initialize
    const gantt_data = {gantt_data_json};
    gantt.init("gantt_container");
    gantt.parse(gantt_data);
</script>
</body>
</html>"""
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(html_content)

if __name__ == "__main__":
    from src.schedule.parse_schedule_input_data import parse_schedule_input_data
    from src.schedule.schedule import ProjectPlan
    from src.utils.dedent_strip import dedent_strip

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

    plan = ProjectPlan.create(parse_schedule_input_data(input))
    ExportDHTMLXGantt.save(plan, "dhtmlx_gantt.html") 