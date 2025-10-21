import unittest

from planexe.llm_util.simple_openai_llm import (
    SimpleOpenAILLM,
    _normalize_content,
)


class NormalizeContentTests(unittest.TestCase):
    def test_string_becomes_input_text_segment(self) -> None:
        self.assertEqual(
            _normalize_content("hello world"),
            [{"type": "input_text", "text": "hello world"}],
        )

    def test_text_alias_dict_converted_to_input_text(self) -> None:
        result = _normalize_content([{"type": "text", "text": "payload"}])
        self.assertEqual(result, [{"type": "input_text", "text": "payload"}])

    def test_missing_text_field_uses_content_value(self) -> None:
        result = _normalize_content([{"type": "text", "content": "from content"}])
        self.assertEqual(result, [{"type": "input_text", "text": "from content"}])

    def test_existing_input_text_segment_preserved(self) -> None:
        result = _normalize_content([{"type": "input_text", "text": "ok"}])
        self.assertEqual(result, [{"type": "input_text", "text": "ok"}])

    def test_non_text_supported_types_pass_through(self) -> None:
        payload = [{"type": "input_image", "image_url": "https://example.com"}]
        self.assertEqual(_normalize_content(payload), payload)


class NormalizeMessagesTests(unittest.TestCase):
    def test_text_type_segments_are_coerced(self) -> None:
        messages = [{"role": "user", "content": [{"type": "text", "text": "payload"}]}]
        normalized = SimpleOpenAILLM.normalize_input_messages(messages)
        self.assertEqual(
            normalized,
            [{"role": "user", "content": [{"type": "input_text", "text": "payload"}]}],
        )

    def test_string_content_converted_to_input_text(self) -> None:
        normalized = SimpleOpenAILLM.normalize_input_messages(
            [{"role": "system", "content": "System guidance"}]
        )
        self.assertEqual(
            normalized,
            [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": "System guidance"}],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
