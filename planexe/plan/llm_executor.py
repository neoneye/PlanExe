"""
Cycle through multiple LLMs, if one fails, try the next one.

I want all LLM invocations to go through this class.

IDEA: Make this the class that PlanTask is using.
IDEA: Exercise this class with mock LLMs that fails in various ways.
IDEA: Scheduling strategy: randomize the order of LLMs.
IDEA: Scheduling strategy: cycle through the LLM list twice, so there are two chances to succeed.
IDEA: Measure the number of tokens used by each LLM.
IDEA: Measure the duration of each LLM.
IDEA: Measure the number of times each LLM was used.
IDEA: Measure the number of times each LLM failed. Is there a common reason for failure.
IDEA: track stats about token usage
IDEA: track what LLM was succeeded
IDEA: track if the LLM failed and why
"""
import time
import logging
import inspect
from typing import Any, Callable, Optional, List, Union
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from planexe.llm_factory import get_llm

logger = logging.getLogger(__name__)

class ExecutionAbortedError(RuntimeError):
    """Raised when the execution is aborted by a callback after a task succeeds."""
    pass

class LLMModelBase:
    def create_llm(self) -> LLM:
        raise NotImplementedError("Subclasses must implement this method")

class LLMModelFromName(LLMModelBase):
    def __init__(self, name: str):
        self.name = name

    def create_llm(self) -> LLM:
        return get_llm(self.name)
    
    def __repr__(self) -> str:
        return f"LLMModelFromName(name='{self.name}')"

    @classmethod
    def from_names(cls, names: list[str]) -> list['LLMModelBase']:
        return [cls(name) for name in names]

class LLMModelWithInstance(LLMModelBase):
    def __init__(self, llm: LLM):
        self.llm = llm

    def create_llm(self) -> LLM:
        return self.llm
    
    def __repr__(self) -> str:
        return f"LLMModelWithInstance(llm={self.llm.__class__.__name__})"

    @classmethod
    def from_instances(cls, llms: list[LLM]) -> list['LLMModelBase']:
        return [cls(llm) for llm in llms]

@dataclass
class LLMAttempt:
    """Stores the result of a single LLM attempt."""
    stage: str
    llm_model: LLMModelBase
    success: bool
    duration: float
    result: Optional[Any] = None
    exception: Optional[Exception] = None

@dataclass
class ShouldStopCallbackParameters:
    """Parameters passed to the should_stop_callback after each attempt."""
    last_attempt: LLMAttempt
    total_duration: float
    attempt_index: int
    total_attempts: int

class LLMExecutor:
    """
    Cycle through multiple LLMs, falling back to the next on failure.
    A callback can be used to abort execution after any attempt.
    """
    def __init__(self, llm_models: list[LLMModelBase], should_stop_callback: Optional[Callable[[ShouldStopCallbackParameters], bool]] = None):
        if not llm_models:
            raise ValueError("No LLMs provided")
        
        if should_stop_callback is not None and not callable(should_stop_callback):
            raise TypeError("should_stop_callback must be a function that returns a boolean")
        
        self.llm_models = llm_models
        self.should_stop_callback = should_stop_callback
        self.attempts: List[LLMAttempt] = []

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def run(self, execute_function: Callable[[LLM], Any]):
        self._validate_execute_function(execute_function)

        # Reset attempts for each new run
        self.attempts = []
        overall_start_time = time.perf_counter()

        for index, llm_model in enumerate(self.llm_models):
            # Attempt invoking the execute_function with one LLM.
            attempt = self._try_one_attempt(llm_model, execute_function)
            self.attempts.append(attempt)

            # Check if the callback wants to abort execution.
            self._raise_exception_if_stop_callback_returns_true(attempt, overall_start_time, index)

            # If the attempt succeeded and we weren't told to abort, we are done.
            if attempt.success:
                return attempt.result

        # If we get here, all attempts have failed.
        self._raise_final_exception()

    def _validate_execute_function(self, execute_function: Callable[[LLM], Any]) -> None:
        """
        Validate that the execute_function is a function that takes a single LLM parameter.
        It doesn't matter what the return type is or if it doesn't return anything.
        """
        if not callable(execute_function):
            raise TypeError("validate_execute_function1: must be a function that takes a LLM parameter")
        
        # Validate function signature
        sig = inspect.signature(execute_function)
        params = list(sig.parameters.values())
        if len(params) != 1:
            raise TypeError("validate_execute_function2: must be a function that takes a single parameter")
        
        # Check if the parameter type annotation is compatible with LLM
        param = params[0]
        if param.annotation != inspect.Parameter.empty:
            # If there's a type annotation, check if it's compatible with LLM
            if param.annotation != LLM and not (hasattr(param.annotation, '__origin__') and param.annotation.__origin__ is Union and LLM in param.annotation.__args__):
                raise TypeError("validate_execute_function3: must be a function that takes a single parameter of type LLM, but got some other type")

    def _try_one_attempt(self, llm_model: LLMModelBase, execute_function: Callable[[LLM], Any]) -> LLMAttempt:
        """Performs a single, complete attempt with one LLM, returning a detailed result."""
        attempt_start_time = time.perf_counter()
        try:
            llm = llm_model.create_llm()
        except Exception as e:
            duration = time.perf_counter() - attempt_start_time
            logger.error(f"Error creating LLM {llm_model!r}: {e}")
            return LLMAttempt(stage='create', llm_model=llm_model, success=False, duration=duration, exception=e)

        try:
            result = execute_function(llm)
            duration = time.perf_counter() - attempt_start_time
            logger.info(f"Successfully ran with LLM {llm_model!r}. Duration: {duration:.2f} seconds")
            return LLMAttempt(stage='execute', llm_model=llm_model, success=True, duration=duration, result=result)
        except Exception as e:
            duration = time.perf_counter() - attempt_start_time
            logger.error(f"Error running with LLM {llm_model!r}: {e}")
            return LLMAttempt(stage='execute', llm_model=llm_model, success=False, duration=duration, exception=e)

    def _raise_exception_if_stop_callback_returns_true(self, last_attempt: LLMAttempt, start_time: float, attempt_index: int) -> None:
        """Checks the callback, if it exists, to see if execution should stop."""
        if self.should_stop_callback is None:
            return
        
        parameters = ShouldStopCallbackParameters(
            last_attempt=last_attempt,
            total_duration=time.perf_counter() - start_time,
            attempt_index=attempt_index,
            total_attempts=len(self.llm_models)
        )
        
        if self.should_stop_callback(parameters):
            logger.warning(f"Callback returned true. Aborting execution after attempt {attempt_index}.")
            raise ExecutionAbortedError(f"Execution aborted by callback after attempt {attempt_index}")

    def _raise_final_exception(self) -> None:
        """Raise the final exception when no attempt succeeds."""
        rows = []
        for attempt_index, attempt in enumerate(self.attempts):
            status = "success" if attempt.success else "failed"
            rows.append(f" - Attempt {attempt_index} with {attempt.llm_model!r} {status} during '{attempt.stage}' stage: {attempt.exception!r}")
        error_summary = "\n".join(rows)
        raise Exception(f"Failed to run. Exhausted all LLMs. Failure summary:\n{error_summary}")
