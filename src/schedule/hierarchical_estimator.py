"""
Provides a system for generating initial time estimates for hierarchical tasks.

This module defines a `Node` class to represent tasks in a tree-like plan.
The core functionality lies in the `Node.resolve_duration()` method, which
recursively traverses the task tree to distribute and calculate time durations
based on a set of predefined hierarchical rules.

Key behaviors of the duration resolution process:
- **Child Resolution First:** Children's durations are resolved recursively
  before the parent's duration is finalized.
- **Initial None Handling:** Tasks initially set to `None` duration, which
  end up as leaves (no children or children resolve to 0), will finalize at `Decimal(0)`.
- **Bottom-Up Summation:** If a parent task's duration was initially `None`,
  its resolved duration becomes the sum of its children's resolved durations.
- **Top-Down Distribution (if parent > sum of children):**
    - If a parent has a specified duration (`!= None`) and it's greater than
      the sum of its children's resolved durations:
        - If *all* children originally had a specified duration (none were `None`),
          the parent's total duration is distributed *evenly* among all children,
          overwriting their initial values. The parent's duration remains the sum
          of these newly assigned child durations.
        - If *some* children originally had `None` duration, the excess duration
          (`parent duration - sum of currently resolved children durations`) is
          distributed among *only* those children that were originally `None`.
          Children with initial specified durations keep them unless the override
          rule above applied (which it wouldn't in this case). Any remaining
          duration after distribution is added to the parent's total.
- **Top-Down Constraint (if parent <= sum of children):**
    - If a parent has a specified duration (`!= None`) and it's less than or
      equal to the sum of its children's resolved durations, children initially
      set to `None` will receive `Decimal(0)` duration. Children with initial
      specified durations keep them. The parent's final duration will be the
      sum of its children's resolved durations (which will be >= the original
      parent duration).
- **Preventing Negatives:** Initial durations must be non-negative or `None`.
  Calculated durations during distribution are clamped at `Decimal(0)`.
- **Final Consistency:** The parent's duration is *always* set to the final
  sum of its children's durations after the children have been resolved and
  any distribution/assignment logic for them has occurred.

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
        if duration is not None:
            if not isinstance(duration, D):
                 raise ValueError("duration must be a Decimal or None")
            if duration < D(0):
                 raise ValueError("duration cannot be negative")

        self.id = id
        self.duration = duration
        self.children = []
        # Flag to remember if the duration was initially None, needed for distribution logic
        self._had_none_duration = duration is None

    def add_child(self, child: 'Node') -> 'Node':
        """Adds a child node and returns it."""
        if not isinstance(child, Node):
            raise TypeError("Can only add Node instances as children")
        self.children.append(child)
        return child

    def to_dict(self):
        """Convert the node and its children to a JSON-compatible dictionary.
        The duration is ceiled to an integer value for simpler testing/display."""
        result = {
            "id": self.id,
            "duration": int(self.duration.to_integral_value(rounding=ROUND_CEILING)) if self.duration is not None else None,
        }
        if self.children: # Use if self.children to avoid empty list in output for leaves
            result["children"] = [child.to_dict() for child in self.children]
        return result

    def resolve_duration(self):
        """
        Recursively resolves durations in the subtree rooted at this node.
        Applies hierarchical rules: bottom-up summation and top-down distribution.
        Ensures parent duration is the sum of children's resolved durations at the end.
        """
        # 1. Recursively resolve children first (bottom-up pass)
        for child in self.children:
            child.resolve_duration()

        # If no children, we are done for this leaf node.
        # If duration was None, it remains None until the very end where it's
        # set to 0 if it's still None and no children.
        if not self.children:
             # If a leaf node had None duration, set it to 0
             if self.duration is None:
                 self.duration = D(0)
             return

        # 2. At this point, all children have resolved durations (Decimal).
        # Calculate the sum of the children's resolved durations.
        sum_children_duration = sum(child.duration for child in self.children)

        # Store parent's *initial* state before potential modification
        initial_parent_duration = self.duration # This could be None or a Decimal
        parent_was_initially_none = self._had_none_duration

        # 3. Apply parent logic based on initial state and children's sum

        if parent_was_initially_none:
            # Case A: Parent had no initial duration, its duration is the sum of children.
            # Children's durations are already resolved recursively. No distribution needed from parent.
            pass # Parent duration will be set to sum_children_duration in step 4

        elif initial_parent_duration is not None:
            # Case B: Parent had an initial duration.

            # Count children that were initially None
            unassigned_children_count = sum(1 for child in self.children if child._had_none_duration)

            if initial_parent_duration > sum_children_duration:
                 # Parent has more duration than the sum of its children's resolved durations.
                 # This excess duration needs to be distributed.

                 if unassigned_children_count == 0:
                    # Case B1: Parent > sum, AND all children originally had durations.
                    # Apply the override rule: distribute parent's duration evenly among ALL children.
                    duration_per_child = initial_parent_duration / D(len(self.children))
                    for child in self.children:
                         child.duration = duration_per_child
                    # Parent duration will become the sum of these in step 4 (which equals initial_parent_duration)

                 else:
                    # Case B2: Parent > sum, AND some children originally had None duration.
                    # Distribute the *remaining* duration (parent_duration - sum of already assigned children)
                    # among the children that were initially None.
                    already_assigned_sum = sum(child.duration for child in self.children if not child._had_none_duration)
                    remaining_duration_to_distribute = initial_parent_duration - already_assigned_sum

                    # Ensure remaining duration is non-negative before distributing
                    remaining_duration_to_distribute = max(D(0), remaining_duration_to_distribute)

                    duration_per_unassigned_child = D(0)
                    if unassigned_children_count > 0:
                         duration_per_unassigned_child = remaining_duration_to_distribute / D(unassigned_children_count)

                    for child in self.children:
                         if child._had_none_duration:
                            child.duration = max(D(0), duration_per_unassigned_child)
                    # Parent duration will become the sum of all children in step 4 (which might be > initial_parent_duration if distribution wasn't enough, or equals it if it was exactly distributed)

            else: # initial_parent_duration <= sum_children_duration
                # Case B3: Parent duration is less than or equal to the sum of children's resolved durations.
                # The parent's duration doesn't constrain the children in a top-down way in this scenario.
                # Children initially None already resolved to 0 in step 1 or 2 if they were leaves.
                # If children initially None are parents, their duration is sum of their kids >= 0.
                # Children with initial specified durations keep them.
                # No distribution from parent needed. The parent's duration will simply become the sum of children.
                pass # Parent duration will be set to sum_children_duration in step 4

        # 4. Final Step: Ensure parent's duration is the sum of its children's *final* durations.
        # This provides the invariant: parent_duration == sum(children_durations).
        self.duration = sum(child.duration for child in self.children)

    def apply_minimum_duration(self):
        """
        Ensures that no node has a duration less than 1.
        For leaf nodes (no children), sets duration to 1 if it was 0.
        For parent nodes, distributes the minimum duration among children evenly.
        Maintains the invariant that parent duration equals sum of children's durations.
        """
        # First recursively apply minimum duration to all children
        for child in self.children:
            child.apply_minimum_duration()

        # If this is a leaf node (no children)
        if not self.children:
            # Set minimum duration to 1 if it was 0
            if self.duration == D(0):
                self.duration = D(1)
            return

        # For parent nodes, ensure each child has at least duration 1
        # and parent duration is sum of children
        for child in self.children:
            if child.duration < D(1):
                child.duration = D(1)

        # Update parent duration to be sum of children
        self.duration = sum(child.duration for child in self.children)
