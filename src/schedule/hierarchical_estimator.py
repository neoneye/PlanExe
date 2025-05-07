"""
Provides a system for generating initial time estimates for hierarchical tasks.

This module defines a `Node` class to represent tasks in a tree-like plan.
The core functionality lies in the `Node.resolve_duration()` method, which
recursively traverses the task tree to distribute and calculate time durations
based on a set of predefined hierarchical rules.

Key behaviors of the duration resolution process:
- **Parent-to-Child Distribution:** If a parent task has a specified duration,
  it's distributed among its children that were initially unspecified (had a
  `None` duration). Children explicitly given a duration (even `Decimal(0)`)
  generally retain their value unless a specific override rule applies.
- **Child-to-Parent Summation:** If a parent task's duration is initially
  unspecified, its duration is calculated as the sum of its children's
  resolved durations.
- **Override for Over-Specified Parent:** A special rule allows a parent with a
  pre-set duration, which is larger than the sum of its children's
  (all of whom must have been initially specified), to redistribute its
  total duration evenly among all its children, overwriting their
  original values.
- **Zero Duration Handling:** Children explicitly set to `Decimal(0)` maintain
  that duration unless overridden by the rule above. Children that were
  initially `None` and cannot receive distributed time (e.g., parent has
  insufficient duration or no duration to give) will also resolve to `Decimal(0)`.
  Negative durations are prevented; tasks will receive at least `Decimal(0)`.
- **Final Consistency:** The process aims to ensure that, after resolution,
  a parent's duration typically reflects the sum of its children's durations,
  except in the specific override case mentioned.

All durations are handled internally using Python's `Decimal` type for precision.
The `Node` class also provides a `to_dict()` method for serializing the task tree,
which converts durations to integers (using ceiling) for easier use in contexts
like testing or simple display.

The primary purpose of this module is to serve as an initial estimator,
providing a complete set of baseline durations for all tasks in a plan before
potentially more refined estimation techniques (e.g., human review, LLM-based
adjustments) are applied.
"""
from typing import Optional
from decimal import ROUND_CEILING, Decimal as D

class Node:
    def __init__(self, id: str, duration: Optional[D] = None):
        if not isinstance(id, str):
            raise ValueError("id must be a string")
        if duration is not None and not isinstance(duration, D):
            raise ValueError("duration must be a decimal or None")
        self.id = id
        self.duration = duration
        self.children = []
        self._had_none_duration = duration is None

    def to_dict(self):
        """Convert the node and its children to a JSON-compatible dictionary.
        The duration is ceiled to an integer value. This is to avoid floating point comparisions in unittests."""
        result = {
            "id": self.id,
            "duration": int(self.duration.to_integral_value(rounding=ROUND_CEILING)) if self.duration is not None else None,
        }
        if len(self.children) > 0:
            result["children"] = [child.to_dict() for child in self.children]
        return result

    def resolve_duration(self):
        """Distribute the parent's duration among its children.
        If a child already has a duration (i.e., not initially None), that duration is generally preserved
        unless a parent with a significantly larger duration forces an even redistribution across all children.
        The parent's duration is primarily distributed among children that were initially unspecified (had None duration).
        If the parent has no duration, it gets the sum of its children's durations.
        If the parent has a longer duration than the sum of its children's durations,
        and all children were initially specified with a duration (none were None),
        the parent's duration is distributed evenly among all children, overwriting their initial values."""
        # First resolve children's durations recursively
        for child in self.children:
            child.resolve_duration()

        if not self.children:
            return

        # Set any None durations to 0
        for child in self.children:
            if child.duration is None:
                child.duration = D(0)

        # Calculate total duration already assigned to children
        assigned_duration = sum(child.duration for child in self.children)
        
        # If parent has no duration, use sum of children's durations
        if self.duration is None:
            self.duration = assigned_duration
            return

        # Parent has a duration. Now decide how to reconcile with children.

        # Count children that had None duration originally
        unassigned_children = sum(1 for child in self.children if child._had_none_duration)
        
        # If parent has a longer duration than sum of children AND all children have durations,
        # redistribute evenly
        if self.duration > assigned_duration and unassigned_children == 0:
            duration_per_child = self.duration / D(len(self.children))
            for child in self.children:
                child.duration = duration_per_child
            return
        
        if unassigned_children > 0:
            # Calculate remaining duration to distribute
            remaining_duration = self.duration - assigned_duration
            # Calculate duration per remaining child
            duration_per_child = remaining_duration / D(unassigned_children)
            
            # Assign durations to children that had None duration originally
            for child in self.children:
                if child._had_none_duration:
                    child.duration = max(D(0), duration_per_child)
            
        # Always update parent's duration to match sum of children
        self.duration = sum(child.duration for child in self.children)
