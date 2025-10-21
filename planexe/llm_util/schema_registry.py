"""
Author: ChatGPT gpt-5-codex
Date: 2025-10-18
PURPOSE: Central registry for structured LLM schema metadata reused by Responses API adapter.
SRP and DRY check: Pass - consolidates schema generation and caching to avoid duplication across tasks.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Type, TypeVar

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


_INVALID_NAME_CHARS = re.compile(r"[^0-9A-Za-z_-]")


@dataclass(frozen=True)
class SchemaRegistryEntry:
    """Metadata describing a structured output schema for a Luigi task."""

    model: Type[TModel]
    qualified_name: str
    sanitized_name: str
    schema: Dict[str, object]
    module: str
    file_path: Optional[Path]


def _sanitize_schema_name(raw_name: str, fallback: str) -> str:
    """Return a Responses-compatible name derived from a fully-qualified path."""

    sanitized = _INVALID_NAME_CHARS.sub("_", raw_name).strip("_")
    if not sanitized:
        sanitized = _INVALID_NAME_CHARS.sub("_", fallback).strip("_") or "PlanExeSchema"
    return sanitized


_SCHEMA_REGISTRY: Dict[str, SchemaRegistryEntry] = {}


def _compute_registry_key(model: Type[TModel]) -> str:
    return f"{model.__module__}.{model.__name__}"


def register_schema(model: Type[TModel]) -> SchemaRegistryEntry:
    """Register the schema for the supplied Pydantic model class if missing."""

    key = _compute_registry_key(model)
    if key in _SCHEMA_REGISTRY:
        return _SCHEMA_REGISTRY[key]

    schema = model.model_json_schema()
    file_path = None
    try:
        source_path = inspect.getsourcefile(model)
        if source_path:
            file_path = Path(source_path)
    except (TypeError, OSError):
        file_path = None

    sanitized_name = _sanitize_schema_name(key, model.__name__)

    entry = SchemaRegistryEntry(
        model=model,
        qualified_name=key,
        sanitized_name=sanitized_name,
        schema=schema,
        module=model.__module__,
        file_path=file_path,
    )
    _SCHEMA_REGISTRY[key] = entry
    return entry


def get_schema_entry(model: Type[TModel]) -> SchemaRegistryEntry:
    """Return the registry entry for a model, registering it on first access."""

    return register_schema(model)


def get_all_registered_schemas() -> Dict[str, SchemaRegistryEntry]:
    """Return a shallow copy of the registry for diagnostics and testing."""

    return dict(_SCHEMA_REGISTRY)

