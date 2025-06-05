import unittest
import os
from planexe.prompt.prompt_catalog import PromptCatalog

class TestPromptCatalog(unittest.TestCase):
    def create_prompt_catalog(self) -> PromptCatalog:
        path_jsonl = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'prompts_simple.jsonl')
        prompt_catalog = PromptCatalog()
        prompt_catalog.load(path_jsonl)
        return prompt_catalog

    def test_find_simple(self):
        """Test finding a typical prompt, without any oddities."""
        # Arrange
        prompt_catalog = self.create_prompt_catalog()

        # Act
        prompt_item = prompt_catalog.find("cfd7aaf3-b521-42c6-ae50-6f0ecbc0c6ca")

        # Assert
        self.assertEqual(prompt_item.prompt, "I'm a prompt with 3 tags")
        self.assertEqual(prompt_item.tags, ["tag1","tag2","tag3"])
        self.assertEqual(len(prompt_item.extras), 0)

    def test_find_with_extra_field(self):
        """Test finding the prompt that has an extra 'comment' field."""
        # Arrange
        prompt_catalog = self.create_prompt_catalog()

        # Act
        prompt_item = prompt_catalog.find("25bd2b32-ac7c-4b71-ba55-a7c6e29d08c5")

        # Assert
        self.assertIsNotNone(prompt_item)
        self.assertEqual(prompt_item.prompt, "I'm a prompt with an extra field named 'comment'")
        self.assertEqual(prompt_item.tags, ["I'm a tag"])

        # Ensure the extra 'comment' field is correctly stored in extras
        self.assertIn("comment", prompt_item.extras)
        self.assertEqual(prompt_item.extras["comment"], "I'm a comment")
