import unittest
from planexe.markdown_util.escape_markdown import escape_markdown

class TestEscapeMarkdown(unittest.TestCase):
    def test_escape_greater_than(self):
        """Test escaping > which creates blockquotes"""
        input_text = ">=10% contingency approved"
        expected_output = "\\>=10% contingency approved"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_asterisk(self):
        """Test escaping * which creates emphasis"""
        input_text = "*Important* note"
        expected_output = "\\*Important\\* note"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_underscore(self):
        """Test escaping _ which creates emphasis"""
        input_text = "CONTINGENCY_LOW"
        expected_output = "CONTINGENCY\\_LOW"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_parentheses(self):
        """Test escaping parentheses"""
        input_text = "Some text (no score)"
        expected_output = "Some text \\(no score\\)"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_square_brackets(self):
        """Test escaping square brackets which create links"""
        input_text = "[link text]"
        expected_output = "\\[link text\\]"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_hash(self):
        """Test escaping # which creates headers"""
        input_text = "# Not a header"
        expected_output = "\\# Not a header"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_backtick(self):
        """Test escaping backticks which create code"""
        input_text = "`code here`"
        expected_output = "\\`code here\\`"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_pipe(self):
        """Test escaping pipe which creates tables"""
        input_text = "col1 | col2"
        expected_output = "col1 \\| col2"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_backslash(self):
        """Test escaping backslash itself"""
        input_text = "path\\to\\file"
        expected_output = "path\\\\to\\\\file"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_no_special_characters(self):
        """Test text without special characters remains unchanged (except for the actual chars)"""
        input_text = "Normal text"
        # Even normal text has some chars that get escaped
        expected_output = "Normal text"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_multiple_special_characters(self):
        """Test escaping multiple different special characters"""
        input_text = ">=10% *approved* [link] (note)"
        expected_output = "\\>=10% \\*approved\\* \\[link\\] \\(note\\)"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_minus_and_plus(self):
        """Test escaping minus and plus signs"""
        input_text = "- Item with +5 points"
        expected_output = "\\- Item with \\+5 points"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_escape_curly_braces(self):
        """Test escaping curly braces"""
        input_text = "Variable {name} here"
        expected_output = "Variable \\{name\\} here"
        self.assertEqual(escape_markdown(input_text), expected_output)

    def test_real_world_example(self):
        """Test with a real-world example from the issue"""
        input_text = "Monte Carlo risk workbook attached"
        expected_output = "Monte Carlo risk workbook attached"
        self.assertEqual(escape_markdown(input_text), expected_output)
