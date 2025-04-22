"""
Export Project Plan as Graphviz DOT code.

PROMPT> python -m src.schedule.export_graphviz
"""
from decimal import Decimal
from src.schedule.schedule import ProjectPlan, DependencyType, ZERO

class ExportGraphviz:
    @staticmethod
    def _lag_txt(lag: Decimal) -> str:
        """Return '', '2', or '-1.5' (Graphviz label)."""
        if lag == 0:
            return ""
        s = str(lag.normalize())      # strip trailing zeros on Decimals
        return s.lstrip("+")          # Graphviz label 'FS2' not 'FS+2'

    @staticmethod
    def to_graphviz(
        project_plan: ProjectPlan,
        *,
        include_dates: bool = False,
    ) -> str:
        """
        Return a string with Graphviz DOT code describing the CPM network.
        Critical path nodes and edges are highlighted in red with thicker lines.

        Parameters
        ----------
        project_plan
            The project plan to visualize
        include_dates
            If *True*, put ES/EF in the node record alongside the duration.
        """
        lines: list[str] = [
            "digraph {",
            "  graph [rankdir=LR];",
            "  node  [shape=record, fontsize=11];",
            "  edge  [fontsize=9];"  # Add default edge font size
        ]

        # Identify critical activity IDs (float == 0)
        critical_ids = {
            a.id for a in project_plan.activities.values()
            if a.float is not None and a.float == ZERO
        }

        # ── nodes ─────────────────────────────────────────────────────────────────
        for a in sorted(project_plan.activities.values(), key=lambda x: x.id):
            content = f"{a.id} | dur: {a.duration.normalize()}"
            if include_dates:
                es_str = f"{a.es.normalize()}"
                ef_str = f"{a.ef.normalize()}"
                content += f" | ES:{es_str} | EF:{ef_str}"
                if a.float is not None:
                    ls_str = f"{a.ls.normalize()}" if a.ls is not None else '?'
                    lf_str = f"{a.lf.normalize()}" if a.lf is not None else '?'
                    float_str = f"{a.float.normalize()}"
                    content += f" | LS:{ls_str} | LF:{lf_str} | F:{float_str}"

            node_attrs = []
            if a.id in critical_ids:
                node_attrs.append("color=red")
                node_attrs.append("penwidth=3.0")

            attrs_str = (", " + ", ".join(node_attrs)) if node_attrs else ""
            lines.append(f'  "{a.id}" [label="{{{content}}}"{attrs_str}];')

        # ── edges ─────────────────────────────────────────────────────────────────
        for succ in project_plan.activities.values():
            for info in succ.parsed_predecessors:
                pred = project_plan.activities.get(info.activity_id)
                if not pred: continue # Should not happen if data is valid

                label = f"{info.dep_type.value}{ExportGraphviz._lag_txt(info.lag)}"
                edge_attrs_list = [f'label="{label}"']

                # Determine if the edge is part of the critical path
                is_critical_edge = False
                if (pred.id in critical_ids and succ.id in critical_ids and
                    pred.lf is not None and succ.lf is not None): # Both nodes must be critical

                    lag = info.lag
                    dep_type = info.dep_type

                    # Check if this specific dependency is driving the timing
                    # These conditions check if the relationship holds exactly,
                    # implying it's potentially a driving constraint on the critical path.
                    try:
                        if dep_type == DependencyType.FS:
                            is_critical_edge = (succ.es == pred.ef + lag)
                        elif dep_type == DependencyType.SS:
                            is_critical_edge = (succ.es == pred.es + lag)
                        elif dep_type == DependencyType.FF:
                            # Check if the backward pass calculation was driven by this link
                            is_critical_edge = (pred.lf == succ.lf - lag)
                        elif dep_type == DependencyType.SF:
                            # Check if the backward pass calculation was driven by this link
                            is_critical_edge = (pred.lf == succ.lf - lag + pred.duration)
                    except TypeError:
                         # Handle potential None values during comparison if logic evolves
                         pass


                if is_critical_edge:
                    edge_attrs_list.append("color=red")
                    edge_attrs_list.append("penwidth=3.0")

                edge_attrs_str = ", ".join(edge_attrs_list)
                lines.append(
                    f'  "{info.activity_id}" -> "{succ.id}" [{edge_attrs_str}];'
                )

        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def export_graphviz(project_plan: ProjectPlan, path: str, **kwargs) -> None:
        """
        Write a `.dot` file ready for Graphviz.

        Example
        -------
        plan.export_graphviz("network.dot")
        # then, in a shell:
        #   dot -Tpng network.dot -o network.png
        """
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(ExportGraphviz.to_graphviz(project_plan, **kwargs))

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
    ExportGraphviz.export_graphviz(plan, "network.dot")