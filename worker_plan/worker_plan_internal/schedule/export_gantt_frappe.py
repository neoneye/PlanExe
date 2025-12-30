"""
Export ProjectSchedule as Gantt chart, using Frappe Gantt chart library.
https://github.com/frappe/gantt

As of 2025-May-08, I'm not satisfied with the Frappe Gantt chart library, it cannot show 
the dependency types: FS, FF, SS, SF. It cannot show the lag. Essential stuff for a Gantt chart.

With Frappe Gantt version 1.0.x the user can change the resolution of the x-axis: days, weeks, months.

Unfortunately version 1.0.x's horizontal scrolling is only rendering the viewport area, 
when scrolling outside the viewport, the gantt chart is blank.
Awaiting fix for horizontal scrolling bug, until then version 1.0.x is not usable.
https://github.com/frappe/gantt/issues/544

Frappe Gantt's horizontal scrolling is broken, in versions: 1.0.3, 1.0.0.
<script src="https://cdn.jsdelivr.net/npm/frappe-gantt@1.0.3/dist/frappe-gantt.umd.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@1.0.3/dist/frappe-gantt.min.css">

Frappe Gantt's horizontal scrolling is working in versions: 0.9.0, 0.6.1.
<script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.9.0/dist/frappe-gantt.umd.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.9.0/dist/frappe-gantt.css">
<script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.min.css">

Frappe Gantt version 1.0.x, with +100 tasks, the scrolling is laggy.

Frappe Gantt version 1.0.x, the activity durations are N time units. I prefer this behavior.
However older versions have activity duration are N+1 time units. I don't like that behavior.

PROMPT> python -m worker_plan_internal.schedule.export_gantt_frappe
"""
from datetime import date, timedelta
import json
import html
from worker_plan_internal.schedule.schedule import ProjectSchedule, DependencyType, PredecessorInfo

class ExportGanttFrappe:
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
    def to_frappe_gantt_tasks(
        project_schedule: ProjectSchedule,
        project_start: date,
    ) -> list[dict]:
        """
        Return a list of dicts ready for `new Gantt(container, tasks, …)`.
        Frappe supports *only* Finish‑to‑Start arrows (no SS/FF/SF, no lag),
        so we:
            • give every task a correct start/end (so the schedule is still right)  
            • pass *only* zero‑lag FS predecessors in `dependencies`  
            • stash the full "A SS+1, B FF‑2…" text in `meta`
            so a custom pop‑up can still show it.
        """
        if not isinstance(project_schedule, ProjectSchedule):
            raise ValueError("project_schedule must be a ProjectSchedule")
        if not isinstance(project_start, date):
            raise ValueError("project_start must be a date")

        tasks = []
        for a in sorted(project_schedule.activities.values(), key=lambda x: x.es):
            start = project_start + timedelta(days=float(a.es))
            end   = project_start + timedelta(days=float(a.ef))
            fs_0  = [
                p.activity_id
                for p in a.parsed_predecessors
                if p.dep_type is DependencyType.FS and p.lag == 0
            ]
            name = a.title if a.title else a.id
            tasks.append(
                {
                    "id":          a.id,
                    "name":        name,
                    "start":       start.isoformat(),
                    "end":         end.isoformat(),
                    "progress":    0,
                    "dependencies": ",".join(fs_0),
                    # anything extra can live under an arbitrary key:
                    "meta": ExportGanttFrappe._dep_summary(a.parsed_predecessors),
                }
            )
        return tasks

    @staticmethod
    def save(project_schedule: ProjectSchedule, path: str, project_start: date, **kwargs) -> None:
        """
        Write a self‑contained HTML file that renders a Frappe‑Gantt chart.
        Open it directly in any modern browser.

        Parameters
        ----------
        project_schedule
            The project schedule to visualize
        path
            Where to save the HTML file
        project_start
            ``datetime.date`` → use it as day 0
        title
            Shown at the top of the chart.
        """
        title = kwargs.get("title", "Project schedule")

        tasks_json = json.dumps(
            ExportGanttFrappe.to_frappe_gantt_tasks(project_schedule, project_start),
            indent=2
        )
        html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<script src="https://cdn.jsdelivr.net/npm/frappe-gantt@1.0.3/dist/frappe-gantt.umd.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@1.0.3/dist/frappe-gantt.min.css">

<!-- <script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.9.0/dist/frappe-gantt.umd.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.9.0/dist/frappe-gantt.css"> -->
<!-- <script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.min.css"> -->
<style>
 body {{
   font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
   margin: 2rem;
 }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div id="the-gantt-container"></div>

<script type="module">
const tasks = {tasks_json};

const gantt = new Gantt('#the-gantt-container', tasks, {{
    view_mode: 'Day',
    view_mode_select: true,
    today_button: false,
    readonly: true,
    infinite_padding: false,
    holidays: false,
    custom_popup_html: task => `
      <div style="padding:.5em 1em;max-width:18rem">
        <h4 style="margin:.2em 0">${{task.name}}</h4>
        <p style="margin:.2em 0"><strong>Start:</strong> ${{task._start.toLocaleDateString()}}</p>
        <p style="margin:.2em 0"><strong>End:</strong>   ${{task._end.toLocaleDateString()}}</p>
        ${{task.meta ? `<p style="margin:.2em 0"><strong>Deps:</strong> ${{task.meta}}</p>` : ''}}
      </div>`
}});
</script>
</body>
</html>"""
        with open(path, "w", encoding="utf‑8") as fp:
            fp.write(html_page)

if __name__ == "__main__":
    from worker_plan_internal.schedule.parse_schedule_input_data import parse_schedule_input_data
    from worker_plan_internal.schedule.schedule import ProjectSchedule
    from worker_plan_internal.utils.dedent_strip import dedent_strip

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

    project_schedule = ProjectSchedule.create(parse_schedule_input_data(input))
    project_start = date(1984, 12, 30)
    ExportGanttFrappe.save(project_schedule, "gantt_frappe.html", project_start) 