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
