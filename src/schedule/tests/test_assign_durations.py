from typing import Optional
import unittest
from decimal import ROUND_CEILING, Decimal as D
import math

class Node:
    def __init__(self, id: str, duration: Optional[D] = None):
        if not isinstance(id, str):
            raise ValueError("id must be a string")
        if duration is not None and not isinstance(duration, D):
            raise ValueError("duration must be a decimal or None")
        self.id = id
        self.duration = duration
        self.children = []

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
        If a child already has a duration, that duration is preserved and
        the remaining duration is distributed among other children.
        If the parent has no duration, it gets the sum of its children's durations."""
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
        
        # Count children without duration
        unassigned_children = sum(1 for child in self.children if child.duration == D(0))
        
        if unassigned_children > 0:
            # Calculate remaining duration to distribute
            remaining_duration = (self.duration or D(0)) - assigned_duration
            # Calculate duration per remaining child
            duration_per_child = remaining_duration / D(unassigned_children)
            
            # Assign durations to children without pre-existing duration
            for child in self.children:
                if child.duration == D(0):
                    child.duration = max(D(0), duration_per_child)
            
        # Always update parent's duration to match sum of children
        self.duration = sum(child.duration for child in self.children)

class TestAssignDurations(unittest.TestCase):
    def test_no_durations_yield_zeros(self):
        # Arrange
        root = Node("root")
        root.children.append(Node("child1"))
        root.children.append(Node("child2"))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 0,
            "children": [
                {"id": "child1", "duration": 0},
                {"id": "child2", "duration": 0},
            ]
        }
        self.assertEqual(root.to_dict(), expected)

    def test_split_evenly_integer(self):
        # Arrange
        root = Node("root", D(10))
        root.children.append(Node("child1"))
        root.children.append(Node("child2"))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 10,
            "children": [
                {"id": "child1", "duration": 5},
                {"id": "child2", "duration": 5},
            ],
        }
        self.assertEqual(root.to_dict(), expected)

    def test_split_evenly_fractional(self):
        # Arrange
        root = Node("root", D(10))
        root.children.append(Node("child1"))
        root.children.append(Node("child2"))
        root.children.append(Node("child3"))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 10,
            "children": [
                {"id": "child1", "duration": 4}, # The duration is 3.33 ceiled to 4
                {"id": "child2", "duration": 4}, # The duration is 3.33 ceiled to 4
                {"id": "child3", "duration": 4} # The duration is 3.33 ceiled to 4
            ]
        }
        self.assertEqual(root.to_dict(), expected)

    def test_split_unevenly_2levels(self):
        # Arrange
        root = Node("root", D(10))
        root.children.append(Node("child1", D(2)))
        root.children.append(Node("child2"))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 10,
            "children": [
                {"id": "child1", "duration": 2},
                {"id": "child2", "duration": 8},
            ],
        }
        self.assertEqual(root.to_dict(), expected)

    def test_split_unevenly_3levels(self):
        # Arrange
        root = Node("root")
        child1 = Node("child1", D(10))
        child2 = Node("child2", D(12))
        root.children.append(child1)
        root.children.append(child2)
        child1.children.append(Node("child1.1"))
        child1.children.append(Node("child1.2"))
        child2.children.append(Node("child2.1"))
        child2.children.append(Node("child2.2"))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 22,
            "children": [
                {
                    "id": "child1", 
                    "duration": 10,
                    "children": [
                        {"id": "child1.1", "duration": 5},
                        {"id": "child1.2", "duration": 5}
                    ]
                },
                {
                    "id": "child2", 
                    "duration": 12,
                    "children": [
                        {"id": "child2.1", "duration": 6},
                        {"id": "child2.2", "duration": 6}
                    ]
                }
            ]
        }
        self.assertEqual(root.to_dict(), expected)

    def test_sum_of_children_2levels(self):
        # Arrange
        root = Node("root")
        root.children.append(Node("child1", D(2)))
        root.children.append(Node("child2", D(3)))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 5,
            "children": [
                {"id": "child1", "duration": 2},
                {"id": "child2", "duration": 3},
            ],
        }
        self.assertEqual(root.to_dict(), expected)

    def test_sum_of_children_3levels(self):
        # Arrange
        root = Node("root") # without duration. It's up to the algorithm to distribute the duration
        child1 = Node("child1") # without duration. It's up to the algorithm to distribute the duration
        child2 = Node("child2") # without duration. It's up to the algorithm to distribute the duration
        root.children.append(child1)
        root.children.append(child2)
        child1.children.append(Node("child1.1", D(2)))
        child1.children.append(Node("child1.2", D(3)))
        child2.children.append(Node("child2.1", D(4)))
        child2.children.append(Node("child2.2", D(5)))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 14,
            "children": [
                {
                    "id": "child1", 
                    "duration": 5,
                    "children": [
                        {"id": "child1.1", "duration": 2},
                        {"id": "child1.2", "duration": 3}
                    ]
                },
                {
                    "id": "child2", 
                    "duration": 9,
                    "children": [
                        {"id": "child2.1", "duration": 4},
                        {"id": "child2.2", "duration": 5}
                    ]
                }
            ]
        }
        self.assertEqual(root.to_dict(), expected)

    def test_prevent_negative_durations(self):
        # Arrange
        root = Node("root", D(10))
        root.children.append(Node("child1", D(12)))
        root.children.append(Node("child2")) # would otherwise get a duration of -2. Clamp this to 0.

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 12,
            "children": [
                {"id": "child1", "duration": 12},
                {"id": "child2", "duration": 0},
            ],
        }
        self.assertEqual(root.to_dict(), expected)

    def test_replace_parents_short_duration_with_childrens_longer_duration(self):
        # Arrange
        root = Node("root", D(2)) # Pick the longest duration, In this case the sum of children's durations is 7, which is more than the parent's duration of 2.
        root.children.append(Node("child1", D(3)))
        root.children.append(Node("child2", D(4)))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 7,
            "children": [
                {"id": "child1", "duration": 3},
                {"id": "child2", "duration": 4},
            ],
        }
        self.assertEqual(root.to_dict(), expected)

