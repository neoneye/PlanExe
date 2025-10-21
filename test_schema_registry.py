#!/usr/bin/env python3
"""
Author: ChatGPT (gpt-5-codex)
Date: 2025-10-30
PURPOSE: Validate that every PlanExe structured LLM usage references a
          registered Pydantic model with a stable schema label.
SRP and DRY check: Pass - single responsibility for auditing the schema
          registry consistency used across Luigi tasks.
"""

from __future__ import annotations

import ast
import importlib
import os
from shutil import copyfile
from pathlib import Path
from typing import List, Tuple

import pytest
from pydantic import BaseModel

from planexe.llm_util.schema_registry import register_schema, sanitize_schema_label


@pytest.fixture(scope="session", autouse=True)
def _provide_planexe_config(tmp_path_factory):
    """Ensure PlanExeConfig sees a valid .env during module imports."""

    config_dir = tmp_path_factory.mktemp("planexe_config")
    env_path = config_dir / ".env"
    env_path.write_text("PLANEXE_TEST=1\n", encoding="utf-8")
    llm_config_src = Path("llm_config.json")
    llm_config_dst = config_dir / "llm_config.json"
    if llm_config_src.exists():
        copyfile(llm_config_src, llm_config_dst)
    else:
        llm_config_dst.write_text("{}", encoding="utf-8")
    os.environ["PLANEXE_CONFIG_PATH"] = str(config_dir)
    from planexe.utils.planexe_config import PlanExeConfig  # noqa: WPS433 - local import for monkeypatching

    PlanExeConfig._instance = None  # type: ignore[attr-defined]


def _collect_structured_calls(base_dir: Path) -> List[Tuple[str, str]]:
    """Return (module_path, expression) pairs for every as_structured_llm call."""

    references: List[Tuple[str, str]] = []
    allowed_roots = {
        "plan",
        "assume",
        "document",
        "team",
        "questions_answers",
        "lever",
        "diagnostics",
        "pitch",
        "swot",
        "expert",
        "governance",
        "fiction",
    }
    for file_path in base_dir.rglob("*.py"):
        if file_path.name == "__init__.py":
            continue
        relative = file_path.relative_to(base_dir)
        if relative.parts[0] not in allowed_roots:
            continue
        module_path = "planexe." + relative.with_suffix("").as_posix().replace("/", ".")
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "as_structured_llm":
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            expression = None
            if isinstance(first_arg, ast.Name):
                expression = first_arg.id
            elif isinstance(first_arg, ast.Attribute):
                parts: List[str] = []
                current = first_arg
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                    expression = ".".join(reversed(parts))
            if expression:
                references.append((module_path, expression))
    return references


@pytest.mark.parametrize("module_path, expression", _collect_structured_calls(Path("planexe")))
def test_structured_models_registerable(module_path: str, expression: str) -> None:
    """Ensure every structured LLM call references a registered Pydantic model."""

    module = importlib.import_module(module_path)
    namespace = vars(module)
    try:
        model_candidate = eval(expression, namespace, {})  # noqa: S307 - trusted source from AST parsing
    except Exception as exc:  # pragma: no cover - defensive guard
        raise AssertionError(f"Failed to resolve structured model '{expression}' in {module_path}") from exc

    assert isinstance(model_candidate, type) and issubclass(
        model_candidate, BaseModel
    ), f"{expression} in {module_path} is not a Pydantic BaseModel"

    entry = register_schema(model_candidate)
    expected_name = sanitize_schema_label(entry.qualified_name, model_candidate.__name__)
    assert entry.sanitized_name == expected_name
    assert entry.schema == model_candidate.model_json_schema()
