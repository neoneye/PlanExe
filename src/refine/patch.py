"""
Work with patches. Extraction of a patch from text. Apply a patch to text.
"""
from dataclasses import dataclass
import re

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
