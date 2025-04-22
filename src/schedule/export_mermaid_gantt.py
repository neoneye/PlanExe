"""
Export Project Plan as Gantt chart, using the Mermaid library.
https://github.com/mermaid-js/mermaid

As of 2025-Apr-22, I'm not satisfied with the Mermaid Gantt chart library, it cannot show 
the dependency types: FS, FF, SS, SF. It cannot show the lag. Essential stuff for a Gantt chart.

PROMPT> python -m src.schedule.export_mermaid_gantt
"""
from datetime import date, timedelta
from src.schedule.schedule import ProjectPlan, PredecessorInfo

class ExportMermaidGantt:
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
    def to_mermaid_gantt(
        project_plan: ProjectPlan,
        project_start: date | str | None = None,
        *,
        title: str = "Project schedule",
    ) -> str:
        """
        Return a Mermaid‑compatible Gantt diagram describing the CPM schedule.

        Parameters
        ----------
        project_plan
            The project plan to visualize
        project_start
            • ``datetime.date`` → use it as day 0  
            • ``"YYYY‑MM‑DD"``  → parsed with ``date.fromisoformat``  
            • ``None``         → today (``date.today()``)
        title
            Shown at the top of the chart.
        """
        # normalise the reference date -------------------------------------------------
        if project_start is None:
            project_start = date.today()
        elif isinstance(project_start, str):
            project_start = date.fromisoformat(project_start)

        # build the Mermaid text -------------------------------------------------------
        lines: list[str] = [
            "gantt",
            f"    title {title}",
            "    dateFormat  YYYY-MM-DD",
            "    axisFormat  %d %b",
            "",
            "    section Activities",
        ]

        # order tasks by early‑start so the chart looks natural
        for act in sorted(project_plan.activities.values(), key=lambda a: a.es):
            start   = project_start + timedelta(days=float(act.es))
            dur_txt = f"{int(act.duration)}d" if act.duration % 1 == 0 else f"{act.duration}d"

            label = act.id
            depinfo = ExportMermaidGantt._dep_summary(act.parsed_predecessors)
            if depinfo:
                label += f" ({depinfo})"

            lines.append(
                f"    {label} :{act.id.lower()}, {start.isoformat()}, {dur_txt}"
            )

        return "\n".join(lines)

    @staticmethod
    def save(project_plan: ProjectPlan, path: str, **kwargs) -> None:
        """
        Write a self‑contained HTML page with an embedded Mermaid Gantt chart.
        Simply open the resulting file in any modern browser.

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

        mermaid_code = ExportMermaidGantt.to_mermaid_gantt(project_plan, project_start, title=title)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: true }});
  </script>
  <style>
    body {{
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
        margin: 2rem;
    }}
  </style>
</head>
<body>
<h1>{title}</h1>
<div class="mermaid">
{mermaid_code}
</div>
</body>
</html>"""
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(html)

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
    ExportMermaidGantt.save(plan, "mermaid_gantt.html") 