import unittest
from decimal import Decimal as D
from src.schedule.hierarchical_estimator import Node

class TestHierarchicalEstimator(unittest.TestCase):
    def test_negative_duration_in_constructor(self):
        # Arrange/Act/Assert
        with self.assertRaises(ValueError) as cm:
            Node("root", D(-5))
        self.assertIn("duration cannot be negative", str(cm.exception))

    def test_no_durations_yield_zeros(self):
        # Arrange
        root = Node("root")
        root.add_child(Node("child1"))
        root.add_child(Node("child2"))

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
        root.add_child(Node("child1"))
        root.add_child(Node("child2"))

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
        root.add_child(Node("child1"))
        root.add_child(Node("child2"))
        root.add_child(Node("child3"))

        # Act
        root.resolve_duration()

        # Assert
        # 10 / 3 = 3.33...
        # to_dict() with ROUND_CEILING: ceil(3.33...) = 4
        expected = {
            "id": "root",
            "duration": 10, # Parent duration remains 10 (sum of children: 3*3.33... = 10)
            "children": [
                {"id": "child1", "duration": 4}, # ceil(3.33...)
                {"id": "child2", "duration": 4}, # ceil(3.33...)
                {"id": "child3", "duration": 4}  # ceil(3.33...)
            ]
        }
        self.assertEqual(root.to_dict(), expected)

    def test_split_unevenly_2levels_nonzero_duration(self):
        # Arrange
        root = Node("root", D(10))
        root.add_child(Node("child1", D(2))) # Keep this duration of 2
        root.add_child(Node("child2")) # assign the remaining duration to this child, which is 8

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

    def test_split_unevenly_2levels_zero_duration_2children(self):
        # Arrange
        root = Node("root", D(10))
        root.add_child(Node("child1", D(0))) # Keep the duration of 0
        root.add_child(Node("child2")) # assign the remaining duration to this child, which is 10

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 10,
            "children": [
                {"id": "child1", "duration": 0},
                {"id": "child2", "duration": 10},
            ],
        }
        self.assertEqual(root.to_dict(), expected)

    def test_split_unevenly_2levels_zero_duration_3children(self):
        # Arrange
        root = Node("root", D(10))
        root.add_child(Node("child1", D(0))) # Keep the duration of 0
        root.add_child(Node("child2")) # assign the remaining duration to this child, which is 10
        root.add_child(Node("child3", D(0))) # Keep the duration of 0

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 10,
            "children": [
                {"id": "child1", "duration": 0},
                {"id": "child2", "duration": 10},
                {"id": "child3", "duration": 0},
            ],
        }
        self.assertEqual(root.to_dict(), expected)

    def test_split_unevenly_3levels(self):
        # Arrange
        root = Node("root")
        child1 = root.add_child(Node("child1", D(10)))
        child2 = root.add_child(Node("child2", D(12)))
        child1.add_child(Node("child1.1"))
        child1.add_child(Node("child1.2"))
        child2.add_child(Node("child2.1"))
        child2.add_child(Node("child2.2"))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 22, # Sum of child1 (10) + child2 (12)
            "children": [
                {
                    "id": "child1",
                    "duration": 10, # Sum of child1.1 (5) + child1.2 (5)
                    "children": [
                        {"id": "child1.1", "duration": 5},
                        {"id": "child1.2", "duration": 5}
                    ]
                },
                {
                    "id": "child2",
                    "duration": 12, # Sum of child2.1 (6) + child2.2 (6)
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
        root = Node("root") # Parent is None, will get sum of children
        root.add_child(Node("child1", D(2)))
        root.add_child(Node("child2", D(3)))

        # Act
        root.resolve_duration()

        # Assert
        expected = {
            "id": "root",
            "duration": 5, # Sum of child1 (2) + child2 (3)
            "children": [
                {"id": "child1", "duration": 2},
                {"id": "child2", "duration": 3},
            ],
        }
        self.assertEqual(root.to_dict(), expected)

    def test_sum_of_children_3levels(self):
        # Arrange
        root = Node("root") # without duration. It's up to the algorithm to distribute the duration
        child1 = root.add_child(Node("child1")) # without duration. It's up to the algorithm to distribute the duration
        child2 = root.add_child(Node("child2")) # without duration. It's up to the algorithm to distribute the duration
        child1.add_child(Node("child1.1", D(2)))
        child1.add_child(Node("child1.2", D(3)))
        child2.add_child(Node("child2.1", D(4)))
        child2.add_child(Node("child2.2", D(5)))

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
        root.add_child(Node("child1", D(12)))
        root.add_child(Node("child2")) # would otherwise get a duration of -2. Clamp this to 0.

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
        root.add_child(Node("child1", D(3)))
        root.add_child(Node("child2", D(4)))

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

    def test_assign_longer_duration_to_children(self):
        # Arrange
        root = Node("root", D(10))
        root.add_child(Node("child1", D(3))) # too short, will be replaced by the parent's duration / 2 children, thus 5
        root.add_child(Node("child2", D(4))) # too short, will be replaced by the parent's duration / 2 children, thus 5

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