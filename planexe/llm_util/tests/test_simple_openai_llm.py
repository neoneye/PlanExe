import unittest

from planexe.llm_util.simple_openai_llm import _normalize_content


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


if __name__ == "__main__":
    unittest.main()
