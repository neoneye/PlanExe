from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List, Optional, Set

from flask import Flask, abort, jsonify, render_template

from planexe.plan.filenames import FilenameEnum


TEMPLATE_DIR = Path(__file__).parent / "templates"
RUN_PIPELINE_FILE = Path(__file__).resolve().parents[1] / "plan" / "run_plan_pipeline.py"

ABSOLUTE_PATH_TO_A_PLANEXE_PROJECT = Path(
    "/Users/neoneye/git/PlanExeGroup/PlanExe/run/20251104_alien_mitigation"
).expanduser()

FILENAME_LOOKUP: Dict[str, str] = {name: enum.value for name, enum in FilenameEnum.__members__.items()}
_NAT_SORT_PATTERN = re.compile(r"(\d+)")


@dataclass(frozen=True)
class TaskDefinition:
    name: str
    dependencies: List[str]
    filename_keys: List[str]
    description: str


class _PipelineAstParser(ast.NodeVisitor):
    def __init__(self) -> None:
        self.tasks: Dict[str, TaskDefinition] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not self._inherits_plan_task(node):
            return

        dependencies = sorted(self._collect_dependencies(node))
        filename_keys = sorted(self._collect_filename_keys(node))
        description = ast.get_docstring(node) or ""

        self.tasks[node.name] = TaskDefinition(
            name=node.name,
            dependencies=dependencies,
            filename_keys=filename_keys,
            description=description,
        )

    def _inherits_plan_task(self, node: ast.ClassDef) -> bool:
        if node.name == "PlanTask":
            return False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "PlanTask":
                return True
        return False

    def _collect_dependencies(self, node: ast.ClassDef) -> Set[str]:
        dependencies: Set[str] = set()
        for child in node.body:
            if isinstance(child, ast.FunctionDef) and child.name == "requires":
                for return_expr in self._return_values(child):
                    dependencies.update(self._parse_dependency_expr(return_expr))
        return dependencies

    def _collect_filename_keys(self, node: ast.ClassDef) -> Set[str]:
        keys: Set[str] = set()
        for child in node.body:
            if isinstance(child, ast.FunctionDef) and child.name == "output":
                for attr_name in self._filename_enum_names(child):
                    keys.add(attr_name)
        return keys

    @staticmethod
    def _return_values(func: ast.FunctionDef) -> List[ast.AST]:
        return [
            stmt.value
            for stmt in ast.walk(func)
            if isinstance(stmt, ast.Return) and stmt.value is not None
        ]

    def _parse_dependency_expr(self, expr: ast.AST) -> Set[str]:
        deps: Set[str] = set()
        if isinstance(expr, ast.Dict):
            for value in expr.values:
                deps.update(self._parse_dependency_expr(value))
        elif isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
            for element in expr.elts:
                deps.update(self._parse_dependency_expr(element))
        elif isinstance(expr, ast.Call):
            if (
                isinstance(expr.func, ast.Attribute)
                and expr.func.attr == "clone"
                and expr.args
            ):
                dependency_name = self._dependency_name_from_arg(expr.args[0])
                if dependency_name:
                    deps.add(dependency_name)
            else:
                for arg in expr.args:
                    deps.update(self._parse_dependency_expr(arg))
                for keyword in expr.keywords:
                    deps.update(self._parse_dependency_expr(keyword.value))
        return deps

    @staticmethod
    def _dependency_name_from_arg(arg: ast.AST) -> Optional[str]:
        if isinstance(arg, ast.Name):
            return arg.id
        if isinstance(arg, ast.Attribute):
            return arg.attr
        return None

    def _filename_enum_names(self, func: ast.FunctionDef) -> Set[str]:
        names: Set[str] = set()
        for node in ast.walk(func):
            enum_name = self._extract_filename_enum_name(node)
            if enum_name:
                names.add(enum_name)
        return names

    @staticmethod
    def _extract_filename_enum_name(node: ast.AST) -> Optional[str]:
        attr_node = node
        if isinstance(attr_node, ast.Attribute) and attr_node.attr == "value":
            attr_node = attr_node.value
        if (
            isinstance(attr_node, ast.Attribute)
            and isinstance(attr_node.value, ast.Name)
            and attr_node.value.id == "FilenameEnum"
        ):
            return attr_node.attr
        return None


_TASK_DEFINITION_CACHE: Optional[tuple[str, Dict[str, TaskDefinition]]] = None


def _load_task_definitions() -> Dict[str, TaskDefinition]:
    global _TASK_DEFINITION_CACHE

    if not RUN_PIPELINE_FILE.exists():
        return {}

    source_text = RUN_PIPELINE_FILE.read_text()
    source_hash = hashlib.sha1(source_text.encode("utf-8")).hexdigest()

    if _TASK_DEFINITION_CACHE and _TASK_DEFINITION_CACHE[0] == source_hash:
        return _TASK_DEFINITION_CACHE[1]

    tree = ast.parse(source_text)
    parser = _PipelineAstParser()
    parser.visit(tree)
    _TASK_DEFINITION_CACHE = (source_hash, parser.tasks)
    return parser.tasks


def _resolve_output_filenames(filename_keys: List[str]) -> List[str]:
    files: List[str] = []
    for key in filename_keys:
        filename = FILENAME_LOOKUP.get(key)
        if filename:
            files.append(filename)
    return files


def _determine_status(project_dir: Path, filenames: List[str]) -> str:
    if not filenames:
        return "unknown"
    if not project_dir.exists():
        return "pending"

    existence = [(project_dir / name).exists() for name in filenames]
    if all(existence):
        return "complete"
    if any(existence):
        return "partial"
    return "pending"


def _natural_sort_key(value: str) -> List[tuple[int, object]]:
    key_parts: List[tuple[int, object]] = []
    for part in _NAT_SORT_PATTERN.split(value):
        if not part:
            continue
        if part.isdigit():
            key_parts.append((0, int(part)))
        else:
            key_parts.append((1, part.lower()))
    return key_parts


def _list_project_files(project_dir: Path) -> List[str]:
    if not project_dir.exists():
        return []
    files = [
        path.name
        for path in project_dir.iterdir()
        if path.is_file()
    ]
    files.sort(key=_natural_sort_key)
    return files


def _compute_layers(task_definitions: Dict[str, TaskDefinition]) -> Dict[str, int]:
    from collections import defaultdict, deque

    indegree: Dict[str, int] = {name: 0 for name in task_definitions}
    adjacency: Dict[str, Set[str]] = defaultdict(set)

    for task_name, task_def in task_definitions.items():
        for dependency in task_def.dependencies:
            if dependency not in task_definitions:
                continue
            indegree[task_name] += 1
            adjacency[dependency].add(task_name)

    queue = deque([name for name, degree in indegree.items() if degree == 0])
    layers: Dict[str, int] = {name: 0 for name in queue}

    while queue:
        current = queue.popleft()
        base_layer = layers.get(current, 0)
        for neighbor in adjacency.get(current, []):
            proposed_layer = base_layer + 1
            if proposed_layer > layers.get(neighbor, 0):
                layers[neighbor] = proposed_layer
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    for name in task_definitions:
        layers.setdefault(name, 0)

    return layers


def _compute_node_positions(layer_map: Dict[str, int]) -> Dict[str, Dict[str, float]]:
    layer_to_nodes: Dict[int, List[str]] = {}
    for task_name, layer in layer_map.items():
        layer_to_nodes.setdefault(layer, []).append(task_name)

    positions: Dict[str, Dict[str, float]] = {}
    x_spacing = 200.0
    y_spacing = 150.0

    for layer in sorted(layer_to_nodes.keys()):
        nodes = sorted(layer_to_nodes[layer])
        if not nodes:
            continue
        midpoint = (len(nodes) - 1) / 2
        for idx, task_name in enumerate(nodes):
            x = (idx - midpoint) * x_spacing
            y = layer * y_spacing
            positions[task_name] = {"x": x, "y": y}

    return positions


def _build_pipeline_graph(project_dir: Path) -> Dict[str, List[Dict[str, object]]]:
    task_definitions = _load_task_definitions()
    layer_map = _compute_layers(task_definitions)
    positions = _compute_node_positions(layer_map)
    nodes: List[Dict[str, Dict[str, object]]] = []
    edges: List[Dict[str, Dict[str, str]]] = []
    seen_edges: Set[str] = set()

    for task_name, task_def in task_definitions.items():
        filenames = _resolve_output_filenames(task_def.filename_keys)
        status = _determine_status(project_dir, filenames)

        nodes.append(
            {
                "data": {
                    "id": task_name,
                    "label": task_name,
                    "status": status,
                    "files": filenames,
                    "description": task_def.description,
                    "layer": layer_map.get(task_name, 0),
                },
                "position": positions.get(task_name, {"x": 0.0, "y": 0.0}),
            }
        )

        for dependency in task_def.dependencies:
            if dependency not in task_definitions:
                continue
            edge_id = f"{dependency}->{task_name}"
            if edge_id in seen_edges:
                continue
            seen_edges.add(edge_id)
            edges.append(
                {
                    "data": {
                        "id": edge_id,
                        "source": dependency,
                        "target": task_name,
                    }
                }
            )

    return {"nodes": nodes, "edges": edges}


def create_app() -> Flask:
    """
    Instantiate a Flask app that renders the split-panel editor with graph data.
    """
    app = Flask(__name__, template_folder=str(TEMPLATE_DIR))

    @app.route("/")
    def index() -> str:
        file_list = _list_project_files(ABSOLUTE_PATH_TO_A_PLANEXE_PROJECT)
        return render_template(
            "edit_index.html",
            file_list=file_list,
            project_dir=str(ABSOLUTE_PATH_TO_A_PLANEXE_PROJECT),
        )

    @app.route("/api/file/<path:filename>")
    def get_file_content(filename: str):
        file_path = (ABSOLUTE_PATH_TO_A_PLANEXE_PROJECT / filename).resolve()
        try:
            file_path.relative_to(ABSOLUTE_PATH_TO_A_PLANEXE_PROJECT)
        except ValueError:
            abort(400, description="Invalid file path")

        if not file_path.exists() or not file_path.is_file():
            return jsonify({"error": f"File '{filename}' not found"}), 404

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return jsonify({"error": str(exc)}), 500

        return jsonify({"fileName": filename, "content": content})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
