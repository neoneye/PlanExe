"""
Shared status enums for viability assessment modules.

This module contains the common StatusEnum that is used across multiple
viability assessment components to ensure consistency.
"""
from enum import Enum


class StatusEnum(str, Enum):
    """Status enumeration for viability assessment domains.
    
    This enum represents the overall viability status of a project or plan
    based on evidence and assessment of critical factors.
    
    Attributes:
        GREEN: Good to go. You have solid evidence and no open critical 
               unknowns. Proceed. Any remaining tasks are minor polish.
        YELLOW: Viable, but risks/unknowns exist. There's promise, but you're 
                missing proof on key points or see non-fatal risks. Proceed 
                with caution and a focused checklist.
        RED: Not viable right now. There's a concrete blocker or negative 
             evidence (legal, technical, economic) that stops execution until 
             fixed. Pause or pivot.
        GRAY: Unknown / unassessed. You don't have enough information to judge. 
              Don't guess—add a "first measurement" task to get out of uncertainty.
    """
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    GRAY = "GRAY"
