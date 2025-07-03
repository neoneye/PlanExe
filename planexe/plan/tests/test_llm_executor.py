import unittest
from planexe.plan.llm_executor import LLMExecutor, LLMModelBase, LLMModelWithInstance
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
        executor = LLMExecutor(llm_models=[llm_model], pipeline_executor_callback=None)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        result = executor.run(execute_function)

        # Assert
        self.assertEqual(result, "Hello, world!")
        self.assertEqual(executor.attempt_count, 1)

    def test_fallback_to_the_2nd_llm(self):
        """Create two LLMs: one that fails, one that succeeds"""
        # Arrange
        bad_llm = ResponseMockLLM(responses=["raise:BAD"])
        good_llm = ResponseMockLLM(responses=["I'm the 2nd LLM"])
        llm_models = LLMModelWithInstance.from_instances([bad_llm, good_llm])
        executor = LLMExecutor(llm_models=llm_models, pipeline_executor_callback=None)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        result = executor.run(execute_function)

        # Assert - should succeed with the good LLM after the bad one fails
        self.assertEqual(result, "I'm the 2nd LLM")
        self.assertEqual(executor.attempt_count, 2)

    def test_exhaust_all_llms_but_none_succeeds(self):
        """Create two LLMs that raise exceptions"""
        # Arrange
        bad1_llm = ResponseMockLLM(responses=["raise:BAD1"])
        bad2_llm = ResponseMockLLM(responses=["raise:BAD2"])
        llm_models = LLMModelWithInstance.from_instances([bad1_llm, bad2_llm])
        executor = LLMExecutor(llm_models=llm_models, pipeline_executor_callback=None)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        with self.assertRaises(Exception) as context:
            executor.run(execute_function)

        # Assert
        self.assertIn("Failed to run. Exhausted all LLMs.", str(context.exception))
        self.assertEqual(executor.attempt_count, 2)

    def test_failure_inside_create_llm(self):
        """Simulate that the LLM cannot be created, due to a possible configuration issue."""
        # Arrange
        class BadLLMModel(LLMModelBase):
            def create_llm(self) -> LLM:
                raise ValueError("Cannot initialize this model")
            def __repr__(self) -> str:
                return "BadLLMModel()"
           
        bad_llm_model = BadLLMModel()
        executor = LLMExecutor(llm_models=[bad_llm_model], pipeline_executor_callback=None)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        with self.assertRaises(Exception) as context:
            executor.run(execute_function)

        # Assert
        self.assertIn("Failed to run. Exhausted all LLMs.", str(context.exception))
        self.assertEqual(executor.attempt_count, 1)

        # Verify the exception is the one that was raised in the create_llm() method
        # Since the LLMExecutor can have a long list of LLMs, the number of exceptions can vary, so a list of events.
        attempt0 = executor.attempts[0]
        self.assertIs(attempt0.llm_model, bad_llm_model)
        self.assertEqual(attempt0.stage, 'create')
        self.assertFalse(attempt0.success)
        self.assertIsNone(attempt0.result)
        self.assertIsInstance(attempt0.exception, ValueError)
        self.assertEqual(str(attempt0.exception), "Cannot initialize this model")
