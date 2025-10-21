"""
Author: ChatGPT gpt-5-codex
Date: 2025-10-18
PURPOSE: Regression coverage for the schema registry that feeds Responses API structured calls.
SRP and DRY check: Pass - isolates registry behavior without touching Luigi pipeline code.
"""

from __future__ import annotations

from pydantic import BaseModel

from planexe.llm_util.schema_registry import get_all_registered_schemas, get_schema_entry


class _ExampleModel(BaseModel):
    field_a: str
    field_b: int


def test_register_schema_is_idempotent() -> None:
    entry_first = get_schema_entry(_ExampleModel)
    entry_second = get_schema_entry(_ExampleModel)

    assert entry_first is entry_second
    assert entry_first.schema["properties"]["field_a"]["type"] == "string"
    assert entry_first.schema["properties"]["field_b"]["type"] == "integer"


def test_registry_export_includes_registered_model() -> None:
    _ = get_schema_entry(_ExampleModel)
    registry = get_all_registered_schemas()

    key = f"{_ExampleModel.__module__}.{_ExampleModel.__name__}"
    assert key in registry
    assert registry[key].qualified_name == key
    assert registry[key].sanitized_name == "planexe_llm_util_tests_test_schema_registry__ExampleModel"
