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
        self.assertEqual(llm_executor.execute_count, 1)

    def test_medium_1st_llm_fails_2nd_succeeds(self):
        """Create two LLMs: one that fails, one that succeeds"""
        # Arrange
        bad_llm = ResponseMockLLM(responses=["raise:BAD"])
        good_llm = ResponseMockLLM(responses=["I'm the 2nd LLM"])
        llm_models = LLMModelWithInstance.from_instances([bad_llm, good_llm])
        llm_executor = LLMExecutor(llm_models=llm_models, pipeline_executor_callback=None)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        result = llm_executor.run(execute_function)

        # Assert - should succeed with the good LLM after the bad one fails
        self.assertEqual(result, "I'm the 2nd LLM")
        self.assertEqual(llm_executor.execute_count, 2)
