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

    def apply(self, text: str) -> str:
        """
        Apply the patch to the text.

        Search for the old_content and replace it with the new_content.

        Raises ValueError if the old_content is not found in the text.
        Raises ValueError if the old_content is found multiple times in the text.
        """
        pattern = re.escape(self.old_content)
        matches = list(re.finditer(pattern, text))
        
        if not matches:
            raise ValueError("Old content not found in text")
        if len(matches) > 1:
            raise ValueError("Old content found multiple times in text")
            
        return re.sub(pattern, self.new_content, text)

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

    def test_patch_apply(self):
        # Test successful patch application
        patch = Patch(old_content="hello", new_content="world")
        text = "greeting: hello"
        result = patch.apply(text)
        self.assertEqual(result, "greeting: world")

        # Test multiline patch application
        patch = Patch(old_content="line1\nline2", new_content="new1\nnew2")
        text = "before\nline1\nline2\nafter"
        result = patch.apply(text)
        self.assertEqual(result, "before\nnew1\nnew2\nafter")

        # Test patch with empty new content
        patch = Patch(old_content="remove me", new_content="")
        text = "keep this remove me keep this"
        result = patch.apply(text)
        self.assertEqual(result, "keep this  keep this")

        # Test patch with special characters
        patch = Patch(old_content="a.b", new_content="c.d")
        text = "text a.b text"
        result = patch.apply(text)
        self.assertEqual(result, "text c.d text")

        # Test error cases
        # Old content not found
        patch = Patch(old_content="not here", new_content="new")
        with self.assertRaises(ValueError) as cm:
            patch.apply("some text")
        self.assertEqual(str(cm.exception), "Old content not found in text")

        # Old content found multiple times
        patch = Patch(old_content="duplicate", new_content="new")
        with self.assertRaises(ValueError) as cm:
            patch.apply("duplicate duplicate")
        self.assertEqual(str(cm.exception), "Old content found multiple times in text")
