import unittest
from planexe.markdown_util.remove_bold_formatting import remove_bold_formatting

class TestRemoveBoldFormatting(unittest.TestCase):
    def test_remove_bold_formatting1(self):
        text = "**Hello** __World__"
        expected = "Hello World"
        self.assertEqual(remove_bold_formatting(text), expected)

    def test_remove_bold_formatting2(self):
        text = "**Hello** 123 World**"
        expected = "Hello 123 World**"
        self.assertEqual(remove_bold_formatting(text), expected)
