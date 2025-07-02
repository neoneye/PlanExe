import unittest
from llama_index.core.llms import ChatMessage, MessageRole, ChatResponse
from planexe.llm_util.response_mockllm import ResponseMockLLM

class TestResponseMockLLM(unittest.TestCase):
    def test_chat_function(self):
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
        
if __name__ == '__main__':
    unittest.main()
