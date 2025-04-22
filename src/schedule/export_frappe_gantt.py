"""
Export Project Plan as Gantt chart, using Frappe Gantt chart library.
https://github.com/frappe/gantt

As of 2025-Apr-22, I'm not satisfied with the Frappe Gantt chart library, it cannot show 
the dependency types: FS, FF, SS, SF. It cannot show the lag. Essential stuff for a Gantt chart.

PROMPT> python -m src.schedule.export_frappe_gantt
"""
from datetime import date, timedelta
import json
import html
from src.schedule.schedule import ProjectPlan, DependencyType, PredecessorInfo, ZERO

class ExportFrappeGantt:
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
        project_plan: ProjectPlan,
        project_start: date | str | None = None,
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
        if project_start is None:
            project_start = date.today()
        elif isinstance(project_start, str):
            project_start = date.fromisoformat(project_start)

        tasks = []
        for a in sorted(project_plan.activities.values(), key=lambda x: x.es):
            start = project_start + timedelta(days=float(a.es))
            end   = project_start + timedelta(days=float(a.ef))
            fs_0  = [
                p.activity_id
                for p in a.parsed_predecessors
                if p.dep_type is DependencyType.FS and p.lag == 0
            ]
            tasks.append(
                {
                    "id":          a.id,
                    "name":        a.id,        # keep label short; full info is in pop‑up
                    "start":       start.isoformat(),
                    "end":         end.isoformat(),
                    "progress":    0,
                    "dependencies": ",".join(fs_0),
                    # anything extra can live under an arbitrary key:
                    "meta": ExportFrappeGantt._dep_summary(a.parsed_predecessors),
                }
            )
        return tasks

    @staticmethod
    def save(project_plan: ProjectPlan, path: str, **kwargs) -> None:
        """
        Write a self‑contained HTML file that renders a Frappe‑Gantt chart.
        Open it directly in any modern browser.

        Parameters
        ----------
        project_plan
            The project plan to visualize
        path
            Where to save the HTML file
        project_start
            • ``datetime.date`` → use it as day 0  
            • ``"YYYY‑MM‑DD"``  → parsed with ``date.fromisoformat``  
            • ``None``         → today (``date.today()``)
        title
            Shown at the top of the chart.
        """
        title = kwargs.get("title", "Project schedule")
        project_start = kwargs.get("project_start", None)

        tasks_json = json.dumps(
            ExportFrappeGantt.to_frappe_gantt_tasks(project_plan, project_start),
            indent=2
        )
        html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<script src="https://cdn.jsdelivr.net/npm/frappe-gantt/dist/frappe-gantt.umd.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt/dist/frappe-gantt.css">
<style>
 body {{font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
        margin: 2rem;}}
 svg {{border: 1px solid #ccc; border-radius: .5rem;}}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<svg id="gantt"></svg>

<script type="module">
const tasks = {tasks_json};

const gantt = new Gantt('#gantt', tasks, {{
    view_mode: 'Day',
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
    ExportFrappeGantt.save(plan, "frappe_gantt.html") 