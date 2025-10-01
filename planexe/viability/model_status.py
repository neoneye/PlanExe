"""
Shared status enums for viability assessment modules.

This module contains the common StatusEnum that is used across multiple
viability assessment components to ensure consistency.
"""
from enum import Enum


class StatusEnum(str, Enum):
    """Status enumeration for viability assessment pillars."""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    GRAY = "GRAY"
