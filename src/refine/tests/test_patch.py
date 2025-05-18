"""
Work with patches. Extraction of a patch from text. Apply a patch to text.

"""
from dataclasses import dataclass
import unittest
import re
from src.utils.dedent_strip import dedent_strip


@dataclass
class Patch:
    old_content: str
    new_content: str

    @staticmethod
    def create(text: str) -> 'Patch':
        """
        There can only be one patch in the text.

        Stuff before the SEARCH marker is ignored.
        <<<<<<< SEARCH
        old content line 1, may span multiple lines
        old content line 2
        =======
        new content line 1, may span multiple lines or be empty
        new content line 2
        >>>>>>> REPLACE
        Stuff after the REPLACE marker is ignored.
        """
        pattern = r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE"
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            raise ValueError("No valid patch found in text")
        
        old_content = match.group(1).strip()
        new_content = match.group(2).strip()
        return Patch(old_content=old_content, new_content=new_content)

class TestPatch(unittest.TestCase):
    def test_patch_create_oneline(self):
        text = dedent_strip("""
        a
        <<<<<<< SEARCH
        b
        =======
        c
        >>>>>>> REPLACE
        d
        """)
        patch = Patch.create(text)
        self.assertEqual(patch.old_content, "b")
        self.assertEqual(patch.new_content, "c")

    def test_patch_create_multiline(self):
        text = dedent_strip("""
        a
        <<<<<<< SEARCH
        b
        c
        d
        =======
        e
        f
        g
        >>>>>>> REPLACE
        h
        """)
        patch = Patch.create(text)
        self.assertEqual(patch.old_content, "b\nc\nd")
        self.assertEqual(patch.new_content, "e\nf\ng")

    def test_patch_create_missing_marker(self):
        text = dedent_strip("""
        a
        b
        c
        """)
        with self.assertRaises(ValueError):
            Patch.create(text)
