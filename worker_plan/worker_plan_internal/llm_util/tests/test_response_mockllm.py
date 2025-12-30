import unittest
from llama_index.core.llms import ChatMessage, MessageRole, ChatResponse, CompletionResponse
from worker_plan_internal.llm_util.response_mockllm import ResponseMockLLM

class TestResponseMockLLM(unittest.TestCase):
    def test_complete_function_best_case_scenario(self):
        # Arrange
        responses = ["or not to be", "123 123 123 123 123", "abc"]
        llm = ResponseMockLLM(responses=responses)
        prompt = "To be "

        # Act
        response = llm.complete(prompt)

        # Assert
        self.assertIsInstance(response, CompletionResponse)
        self.assertEqual(response.text, responses[0])

    def test_complete_function_raise_exception(self):
        # Arrange
        responses = ["raise:BOOM"]
        llm = ResponseMockLLM(responses=responses)
        prompt = "To be "

        # Act / Assert
        with self.assertRaises(Exception) as context:
            llm.complete(prompt)
        self.assertEqual(str(context.exception), "BOOM")

    def test_chat_function_best_case_scenario(self):
        # Arrange
        responses = ["Hello there!", "How can I help?", "Goodbye!"]
        llm = ResponseMockLLM(responses=responses)
        message = ChatMessage(
            role=MessageRole.USER,
            content="Hello"
        )
        
        # Act
        response = llm.chat([message])

        # Assert
        self.assertIsInstance(response, ChatResponse)
        self.assertEqual(response.message.content, responses[0])

    def test_chat_function_raise_exception(self):
        # Arrange
        responses = ["raise:BOOM"]
        llm = ResponseMockLLM(responses=responses)
        message = ChatMessage(
            role=MessageRole.USER,
            content="Hello"
        )

        # Act / Assert
        with self.assertRaises(Exception) as context:
            llm.chat([message])
        self.assertEqual(str(context.exception), "BOOM")

if __name__ == '__main__':
    unittest.main()
