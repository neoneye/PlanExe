import unittest
from worker_plan_internal.markdown_util.fix_bullet_lists import fix_bullet_lists

class TestFixBulletLists(unittest.TestCase):
    def test_fix_bullet_lists(self):
        input_text = """Lorem ipsum:
- Item A
- Item B
- Item C"""
        expected_output = """Lorem ipsum:

- Item A
- Item B
- Item C
"""
        self.assertEqual(fix_bullet_lists(input_text), expected_output)

    def test_no_bullet_list(self):
        input_text = """Lorem ipsum:
Lorem ipsum dolor sit amet."""
        expected_output = """Lorem ipsum:
Lorem ipsum dolor sit amet."""
        self.assertEqual(fix_bullet_lists(input_text), expected_output)

    def test_already_fixed(self):
        input_text = """Lorem ipsum:

- Item A
- Item B
- Item C

Lorem ipsum dolor sit amet."""
        expected_output = """Lorem ipsum:

- Item A
- Item B
- Item C

Lorem ipsum dolor sit amet."""
        self.assertEqual(fix_bullet_lists(input_text), expected_output)

    def test_multiple_lists(self):
        input_text = """Lorem ipsum:
- Item A
- Item B

Lorem ipsum:
- Item C
- Item D"""
        expected_output = """Lorem ipsum:

- Item A
- Item B

Lorem ipsum:

- Item C
- Item D
"""
        self.assertEqual(fix_bullet_lists(input_text), expected_output)
