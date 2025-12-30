"""
Export ProjectSchedule as Gantt chart, using the Mermaid library.
https://github.com/mermaid-js/mermaid

As of 2025-May-10, I'm not satisfied with the Mermaid Gantt chart library, it cannot show 
the dependency types: FS, FF, SS, SF. It cannot show the lag. Essential stuff for a Gantt chart.
There is no way for the user to change the resolution of the x-axis: days, weeks, months.
No way to assign a custom css class to a specific activity, so it can be styled differently.

CSS styling of mermaid:
https://github.com/mermaid-js/mermaid/blob/develop/packages/mermaid/src/diagrams/gantt/styles.js

PROMPT> python -m worker_plan_internal.schedule.export_gantt_mermaid
"""
from datetime import date, timedelta
from worker_plan_internal.schedule.schedule import ProjectSchedule

class ExportGanttMermaid:
    @staticmethod
    def _escape_mermaid(text: str) -> str:
        """Escape special characters for Mermaid syntax. Replace characters that could break Mermaid syntax."""

        # Mermaid has problems with the colon character. 
        # The Mermaid docs says colon can be escaped with backslash colon. Alas it doesn't work for me. 
        # I have tried &colon; and \colon; and wrapping it all in quotes, but no luck.
        # My poor mans solution is to replace colon with a semicolon.
        text = text.replace(':', ';')

        # Escape other characters that may break the Mermaid syntax.
        text = text.replace('[', '\\[')
        text = text.replace(']', '\\]')
        text = text.replace('{', '\\{')
        text = text.replace('}', '\\}')
        text = text.replace('|', '\\|')
        text = text.replace('"', '\\"')
        text = text.replace("'", "\\'")
        return text
    
    @staticmethod
    def to_mermaid_gantt(
        project_schedule: ProjectSchedule,
        project_start: date,
        *,
        title: str = "Project schedule",
    ) -> str:
        """
        Return a Mermaid‑compatible Gantt diagram describing the CPM schedule.

        Parameters
        ----------
        project_schedule
            The project schedule to visualize
        project_start
            ``datetime.date`` → use it as day 0  
        title
            Shown at the top of the chart.
        """
        if not isinstance(project_schedule, ProjectSchedule):
            raise ValueError("project_schedule must be a ProjectSchedule")
        if not isinstance(project_start, date):
            raise ValueError("project_start must be a date")

        # build the Mermaid text -------------------------------------------------------
        lines: list[str] = [
            "gantt",
            "    dateFormat  YYYY-MM-DD",
            "    axisFormat  %d %b",
            "    todayMarker off",
        ]

        # order tasks by early‑start so the chart looks natural
        activities = sorted(project_schedule.activities.values(), key=lambda a: a.es)
        for index, act in enumerate(activities):
            start   = project_start + timedelta(days=float(act.es))
            dur_txt = f"{int(act.duration)}d" if act.duration % 1 == 0 else f"{act.duration}d"

            name = act.title if act.title else act.id
            label = ExportGanttMermaid._escape_mermaid(name)

            # insert a section for every 10 activities
            if index % 10 == 0:
                lines.append(f"    section {index}")

            lines.append(
                f"    {label} :{start.isoformat()}, {dur_txt}"
            )

        return "\n".join(lines)

    @staticmethod
    def save(project_schedule: ProjectSchedule, path: str, project_start: date, **kwargs) -> None:
        """
        Write a self‑contained HTML page with an embedded Mermaid Gantt chart.
        Simply open the resulting file in any modern browser.

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

        mermaid_code = ExportGanttMermaid.to_mermaid_gantt(project_schedule, project_start, title=title)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <!--HTML_HEAD_START-->
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ 
        "startOnLoad": true,
        "theme": "default",
        "themeVariables": {{
            "sectionBkgColor": "#777",
            "sectionBkgColor2": "#777"
        }},
        "gantt": {{
            "fontSize": 17,
            "sectionFontSize": 20
        }}
    }});
  </script>
  <!--HTML_HEAD_END-->
  <style>
    body {{
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
        margin: 2rem;
    }}
  </style>
</head>
<body>
<h1>{title}</h1>
<!--HTML_BODY_CONTENT_START-->
<div class="mermaid">
{mermaid_code}
</div>
<!--HTML_BODY_CONTENT_END-->
<!--HTML_BODY_SCRIPT_START-->
<!--HTML_BODY_SCRIPT_END-->
</body>
</html>"""
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(html)

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
    ExportGanttMermaid.save(project_schedule, "gantt_mermaid.html", project_start) 