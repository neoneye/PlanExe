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

    def test_fallback_to_the_2nd_llm(self):
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

    def test_exhaust_all_llms_but_none_succeeds(self):
        """Create two LLMs that raise exceptions"""
        # Arrange
        bad1_llm = ResponseMockLLM(responses=["raise:BAD1"])
        bad2_llm = ResponseMockLLM(responses=["raise:BAD2"])
        llm_models = LLMModelWithInstance.from_instances([bad1_llm, bad2_llm])
        llm_executor = LLMExecutor(llm_models=llm_models, pipeline_executor_callback=None)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        with self.assertRaises(Exception) as context:
            llm_executor.run(execute_function)

        # Assert
        self.assertIn("Failed to run. Exhausted all the LLMs in the list", str(context.exception))
        self.assertEqual(llm_executor.execute_count, 2)
