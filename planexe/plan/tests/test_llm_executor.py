import unittest
from planexe.plan.llm_executor import LLMExecutor, LLMModelWithInstance
from planexe.llm_util.response_mockllm import ResponseMockLLM
from llama_index.core.llms import MockLLM, ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

class TestLLMExecutor(unittest.TestCase):
    def test_simple(self):
        # Arrange
        llm = ResponseMockLLM(
            responses=["Hello, world!"],
        )
        llm_model = LLMModelWithInstance(llm)
        llm_executor = LLMExecutor(llm_models=[llm_model], pipeline_executor_callback=None)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        result = llm_executor.run(execute_function)

        # Assert
        self.assertEqual(result, "Hello, world!")
