import unittest
from planexe.utils.enumerate_duplicate_strings import enumerate_duplicate_strings

class TestEnumerateDuplicateStrings(unittest.TestCase):
    def test_input_not_dict(self):
        with self.assertRaises(ValueError) as cm:
            enumerate_duplicate_strings("not a dict")
        self.assertIn("Input must be a dictionary", str(cm.exception))

    def test_empty_dict(self):
        result = enumerate_duplicate_strings({})
        self.assertEqual(result, {})

    def test_no_duplicates(self):
        # Arrange
        input = {
            'a': 'unique title a',
            'b': 'unique title b',
            'c': 'unique title c',
        }

        # Act
        result = enumerate_duplicate_strings(input)

        # Assert
        expected = {
            'a': 'unique title a',
            'b': 'unique title b',
            'c': 'unique title c',
        }
        self.assertEqual(result, expected)

    def test_duplicates1(self):
        # Arrange
        input = {
            'a': 'I\'m a duplicate title',
            'b': 'I\'m a duplicate title',
            'c': 'unique title c',
            'd': 'unique title d',
            'e': 'I\'m a duplicate title',
        }

        # Act
        result = enumerate_duplicate_strings(input)

        # Assert
        expected = {
            'a': 'I\'m a duplicate title (1)',
            'b': 'I\'m a duplicate title (2)',
            'c': 'unique title c',
            'd': 'unique title d',
            'e': 'I\'m a duplicate title (3)',
        }
        self.assertEqual(result, expected)

    def test_duplicates2(self):
        # Arrange
        input = {
            'a': 'duplicate x',
            'b': 'duplicate y',
            'c': 'duplicate x',
            'd': 'unique',
            'e': 'duplicate y',
        }

        # Act
        result = enumerate_duplicate_strings(input)

        # Assert
        expected = {
            'a': 'duplicate x (1)',
            'b': 'duplicate y (1)',
            'c': 'duplicate x (2)',
            'd': 'unique',
            'e': 'duplicate y (2)',
        }
        self.assertEqual(result, expected)

    def test_duplicates_case_insensitive1(self):
        # Arrange
        input = {
            'a': 'duplicate x',
            'b': 'duplicate Y',
            'c': 'duplicate X',
            'd': 'unique',
            'e': 'duplicate y',
        }

        # Act
        result = enumerate_duplicate_strings(input)

        # Assert
        expected = {
            'a': 'duplicate x (1)',
            'b': 'duplicate Y (1)',
            'c': 'duplicate X (2)',
            'd': 'unique',
            'e': 'duplicate y (2)',
        }
        self.assertEqual(result, expected)

    def test_duplicates_case_insensitive2(self):
        # Arrange
        input = {
            'a': 'duplicate ÆØÅ',
            'b': 'duplicate æøå',
            'c': 'unique',
        }

        # Act
        result = enumerate_duplicate_strings(input)

        # Assert
        expected = {
            'a': 'duplicate ÆØÅ (1)',
            'b': 'duplicate æøå (2)',
            'c': 'unique',
        }
        self.assertEqual(result, expected)
