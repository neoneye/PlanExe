import unittest
from planexe.plan.llm_executor import LLMExecutor, LLMModelBase, LLMModelWithInstance, ExecutionAbortedError, ShouldStopCallbackParameters
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
        executor = LLMExecutor(llm_models=[llm_model])

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
        executor = LLMExecutor(llm_models=llm_models)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        result = executor.run(execute_function)

        # Assert - should succeed with the good LLM after the bad one fails
        self.assertEqual(result, "I'm the 2nd LLM")
        self.assertEqual(executor.attempt_count, 2)
        self.assertFalse(executor.attempts[0].success)
        self.assertTrue(executor.attempts[1].success)

    def test_exhaust_all_llms_but_none_succeeds(self):
        """Create two LLMs that raise exceptions"""
        # Arrange
        bad1_llm = ResponseMockLLM(responses=["raise:BAD1"])
        bad2_llm = ResponseMockLLM(responses=["raise:BAD2"])
        llm_models = LLMModelWithInstance.from_instances([bad1_llm, bad2_llm])
        executor = LLMExecutor(llm_models=llm_models)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        with self.assertRaises(Exception) as context:
            executor.run(execute_function)

        # Assert
        self.assertIn("Failed to run. Exhausted all LLMs.", str(context.exception))
        self.assertEqual(executor.attempt_count, 2)
        self.assertIn("BAD1", str(context.exception))
        self.assertIn("BAD2", str(context.exception))
        self.assertFalse(executor.attempts[0].success)
        self.assertFalse(executor.attempts[1].success)

    def test_failure_inside_create_llm(self):
        """Simulate that the LLM cannot be created, due to a possible configuration issue."""
        # Arrange
        class BadLLMModel(LLMModelBase):
            def create_llm(self) -> LLM:
                raise ValueError("Cannot initialize this model")
            def __repr__(self) -> str:
                return "BadLLMModel()"
           
        bad_llm_model = BadLLMModel()
        executor = LLMExecutor(llm_models=[bad_llm_model])

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        with self.assertRaises(Exception) as context:
            executor.run(execute_function)

        # Assert
        self.assertIn("Failed to run. Exhausted all LLMs.", str(context.exception))
        self.assertEqual(executor.attempt_count, 1)
        attempt0 = executor.attempts[0]
        self.assertIs(attempt0.llm_model, bad_llm_model)
        self.assertEqual(attempt0.stage, 'create')
        self.assertFalse(attempt0.success)
        self.assertIsNone(attempt0.result)
        self.assertIsInstance(attempt0.exception, ValueError)
        self.assertEqual(str(attempt0.exception), "Cannot initialize this model")

    def test_continue_execution_as_long_as_the_callback_returns_false(self):
        # Arrange
        llm0 = ResponseMockLLM(
            responses=["raise:BAD0"],
        )
        llm1 = ResponseMockLLM(
            responses=["I'm the last LLM"],
        )
        llm_models = LLMModelWithInstance.from_instances([llm0, llm1])

        def should_stop_callback(parameters: ShouldStopCallbackParameters) -> bool:
            # Returning False means continue execution
            return False
        
        executor = LLMExecutor(llm_models=llm_models, should_stop_callback=should_stop_callback)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        result = executor.run(execute_function)

        # Assert
        self.assertEqual(result, "I'm the last LLM")
        self.assertEqual(executor.attempt_count, 2)
        self.assertFalse(executor.attempts[0].success)
        self.assertTrue(executor.attempts[1].success)

    def test_stop_execution_when_the_callback_returns_true_with_one_llm(self):
        """Run the the first LLM, and stop execution before the second LLM is run."""
        # Arrange
        llm0 = ResponseMockLLM(
            responses=["I'm the first LLM and I'm good"],
        )
        llm1 = ResponseMockLLM(
            responses=["I'm the last LLM and I'm never supposed to be run"],
        )
        llm_models = LLMModelWithInstance.from_instances([llm0, llm1])

        def should_stop_callback(parameters: ShouldStopCallbackParameters) -> bool:
            # Stop execution
            return True
        
        executor = LLMExecutor(llm_models=llm_models, should_stop_callback=should_stop_callback)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        with self.assertRaises(ExecutionAbortedError):
            executor.run(execute_function)

        # Assert
        self.assertEqual(executor.attempt_count, 1)
        attempt0 = executor.attempts[0]
        self.assertTrue(attempt0.success)
        self.assertEqual(attempt0.result, "I'm the first LLM and I'm good")

    def test_stop_execution_when_the_callback_returns_true_with_two_llms(self):
        """
        Run the the first LLM and fallback to the second LLM, and then stop execution 
        just before the operation was about to succeed.
        """
        # Arrange
        llm0 = ResponseMockLLM(
            responses=["raise:I'm the first LLM and I'm bad"],
        )
        llm1 = ResponseMockLLM(
            responses=["I'm the last LLM and I'm not supposed to be run"],
        )
        llm_models = LLMModelWithInstance.from_instances([llm0, llm1])

        def should_stop_callback(parameters: ShouldStopCallbackParameters) -> bool:
            if parameters.attempt_index == 0:
                # Continue execution
                return False
            if parameters.attempt_index == 1:
                # Stop execution
                return True
            raise ValueError(f"Unexpected attempt index: {parameters.attempt_index}")
        
        executor = LLMExecutor(llm_models=llm_models, should_stop_callback=should_stop_callback)

        def execute_function(llm: LLM) -> str:
            return llm.complete("Hi").text

        # Act
        with self.assertRaises(ExecutionAbortedError):
            executor.run(execute_function)

        # Assert
        self.assertEqual(executor.attempt_count, 2)
        attempt0 = executor.attempts[0]
        self.assertFalse(attempt0.success)
        self.assertIsNone(attempt0.result)
        self.assertEqual(str(attempt0.exception), "I'm the first LLM and I'm bad")
        attempt1 = executor.attempts[1]
        self.assertTrue(attempt1.success)
        self.assertEqual(attempt1.result, "I'm the last LLM and I'm not supposed to be run")

    def test_llmexecutor_init_with_no_llms(self):
        """One or more LLMs are supposed to be provided."""
        # Act
        with self.assertRaises(ValueError) as context:
            LLMExecutor(llm_models=[])

        # Assert
        self.assertIn("No LLMs provided", str(context.exception))

    def test_llmexecutor_init_with_junk_callback(self):
        """The callback is supposed to be a function that returns a boolean."""
        # Arrange
        llm_model = LLMModelWithInstance(ResponseMockLLM(responses=["test"]))

        # Act
        with self.assertRaises(TypeError) as context:
            LLMExecutor(llm_models=[llm_model], should_stop_callback="I'm not a function")

        # Assert
        self.assertIn("should_stop_callback must be a function that returns a boolean", str(context.exception))

    def test_validate_execute_function1(self):
        """
        Invoke the run() function with a junk execute_function, and check that it detects that it's junk.
        The execute_function is supposed to be a function that takes a LLM parameter.
        """
        # Arrange
        llm_model = LLMModelWithInstance(ResponseMockLLM(responses=["test"]))
        executor = LLMExecutor(llm_models=[llm_model])

        # Act
        with self.assertRaises(TypeError) as context:
            executor.run("I'm not a function")

        # Assert
        self.assertIn("validate_execute_function1: must be a function that takes a LLM parameter", str(context.exception))

    def test_validate_execute_function2(self):
        """
        Invoke the run() function with a junk execute_function, and check that it detects that it's junk.
        The execute_function is supposed to be a function that takes a LLM parameter.
        """
        # Arrange
        llm_model = LLMModelWithInstance(ResponseMockLLM(responses=["test"]))
        executor = LLMExecutor(llm_models=[llm_model])

        def execute_function(a: int, b: int, c: int) -> str:
            raise ValueError("I take the wrong number of parameters, I'm not supposed to be called")

        # Act
        with self.assertRaises(TypeError) as context:
            executor.run(execute_function)

        # Assert
        self.assertIn("validate_execute_function2: must be a function that takes a single parameter", str(context.exception))

    def test_validate_execute_function3(self):
        """
        Invoke the run() function with a junk execute_function, and check that it detects that it's junk.
        The execute_function is supposed to be a function that takes a LLM parameter.
        """
        # Arrange
        llm_model = LLMModelWithInstance(ResponseMockLLM(responses=["test"]))
        executor = LLMExecutor(llm_models=[llm_model])

        def execute_function(wrong_parameter_type: str) -> str:
            raise ValueError("I have the wrong function type signature, I'm not supposed to be called")

        # Act
        with self.assertRaises(TypeError) as context:
            executor.run(execute_function)

        # Assert
        self.assertIn("validate_execute_function3: must be a function that takes a single parameter of type LLM, but got some other type", str(context.exception))
