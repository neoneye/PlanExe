import unittest
from decimal import Decimal as D
from src.schedule.hierarchical_estimator import Node

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

    def test_negative_durations_yield_zeros(self):
        # Arrange
        root = Node("root", D(-10)) # negative duration. Clamp this to 0.
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

    def test_split_unevenly_2levels_nonzero_duration(self):
        # Arrange
        root = Node("root", D(10))
        root.children.append(Node("child1", D(2))) # Keep this duration of 2
        root.children.append(Node("child2")) # assign the remaining duration to this child, which is 8

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
        root.children.append(Node("child1", D(0))) # Keep the duration of 0
        root.children.append(Node("child2")) # assign the remaining duration to this child, which is 10

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
        root.children.append(Node("child1", D(0))) # Keep the duration of 0
        root.children.append(Node("child2")) # assign the remaining duration to this child, which is 10
        root.children.append(Node("child3", D(0))) # Keep the duration of 0

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

    def test_assign_longer_duration_to_children(self):
        # Arrange
        root = Node("root", D(10))
        root.children.append(Node("child1", D(3))) # too short, will be replaced by the parent's duration / 2 children, thus 5
        root.children.append(Node("child2", D(4))) # too short, will be replaced by the parent's duration / 2 children, thus 5

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