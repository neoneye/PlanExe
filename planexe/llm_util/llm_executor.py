"""
Cycle through multiple LLMs, if one fails, try the next one.

I want all LLM invocations to go through this class.

It happens that the json output of the LLM doesn't match the expected schema.
When I inspect the raw response, I can see that the json comes close to the expected schema,
with tiny mistakes here and there. I guess with a more fuzzy json parser than Pydantic, 
the json could be extracted.

It happens that an LLM provider is unavailable. Where a model used to be available, and have been removed from the provider.
Or the LLM server has to be started by the developer on the local machine.

Having multiple LLMs available is a good idea, because it increases the chances of success.
If one fails, then the next one may be able to respond.
If all of them fails, then the exception is raised. Exhausted all LLMs.

This is the class that `PlanTask` is using, the root class of all tasks in the pipeline.
Subtasks such as `ReviewPlan` are also using this class to invoke the LLM.

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
import typing
import traceback
from uuid import uuid4
from typing import Any, Callable, Optional, List
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from llama_index.core.instrumentation.dispatcher import instrument_tags
from planexe.llm_factory import get_llm

logger = logging.getLogger(__name__)

class PipelineStopRequested(RuntimeError):
    """
    Raised when the pipeline execution is requested to stop by `should_stop_callback` after a task succeeds.

    This exception happens when the user presses Ctrl-C or closes the browser tab,
    so there is no point in continuing wasting resources on a 30 minute task.

    The PlanTask.run() method intercepts the PipelineStopRequested exception and create a the PIPELINE_STOP_REQUESTED_FLAG file,
    signaling that the pipeline was stopped by the user. So in post-mortem, it's fast to determine if the pipeline was stopped with this exception.
    """
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
    def __init__(self, llm_models: list[LLMModelBase], should_stop_callback: Optional[Callable[[ShouldStopCallbackParameters], None]] = None):
        """
        Args:
            llm_models: A list of LLM models to try.
            should_stop_callback: A function that will be called after each attempt.
                If the callback raises PipelineStopRequested, the execution will be aborted. This is the only exception that is allowed to be raised by the callback, that doesn't indicate a problem.
                If the callback raises any other exception, the execution will be aborted. This indicates a problem with the callback.
                If the callback returns None, the execution will continue.
                If no callback is provided, the execution will continue until all LLMs are exhausted.
        """
        if not llm_models:
            raise ValueError("No LLMs provided")
        
        if should_stop_callback is not None and not callable(should_stop_callback):
            raise TypeError("should_stop_callback must be a function that can raise PipelineStopRequested to stop execution")
        
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
            self._check_stop_callback(attempt, overall_start_time, index)

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
        
        try:
            # Use get_type_hints to correctly resolve postponed annotations (strings)
            # This is the key to supporting `from __future__ import annotations`
            type_hints = typing.get_type_hints(execute_function)
            param_name = params[0].name
            param_type = type_hints.get(param_name)
        except (NameError, TypeError) as e:
            # NameError happens if a type hint string can't be resolved.
            # TypeError can happen with complex but invalid type hints.
            raise TypeError(f"Could not resolve type hints for execute_function. Error: {e}")

        if param_type is None:
            # No type hint provided, so we can't validate. Let it pass.
            return

        # Now `param_type` is guaranteed to be a real type object.
        # Use issubclass for the most flexible and correct check.
        if not (isinstance(param_type, type) and issubclass(param_type, LLM)):
            raise TypeError(
                f"validate_execute_function3: must be a function that takes a single parameter of type LLM, "
                f"but got type '{param_type}'"
            )

    def _try_one_attempt(self, llm_model: LLMModelBase, execute_function: Callable[[LLM], Any]) -> LLMAttempt:
        """
        Performs a single, complete attempt with one LLM, returning a detailed result.
        
        Args:
            llm_model: The LLM model to try.
            execute_function: The callback to execute with the llm. The callback must not raise the PipelineStopRequested exception, since that interferes with the `ExecutePipeline.stopped_by_callback` property.

        Returns:
            A detailed result of the attempt.
        """
        attempt_start_time = time.perf_counter()
        try:
            llm = llm_model.create_llm()
        except Exception as e:
            duration = time.perf_counter() - attempt_start_time
            logger.error(f"LLMExecutor: Error creating LLM {llm_model!r}: {e!r} traceback: {traceback.format_exc()}")
            return LLMAttempt(stage='create', llm_model=llm_model, success=False, duration=duration, exception=e)

        llm_executor_uuid = str(uuid4())
        try:
            logger.debug(f"LLMExecutor will invoke execute_function. LLM {llm_model!r}. llm_executor_uuid: {llm_executor_uuid!r}")
            with instrument_tags({"llm_executor_uuid": llm_executor_uuid}):
                result = execute_function(llm)
            duration = time.perf_counter() - attempt_start_time
            logger.info(f"LLMExecutor did invoke execute_function. LLM {llm_model!r}. llm_executor_uuid: {llm_executor_uuid!r}. Duration: {duration:.2f} seconds")
            return LLMAttempt(stage='execute', llm_model=llm_model, success=True, duration=duration, result=result)
        except PipelineStopRequested as e:
            logger.info(f"LLMExecutor: Stopping because the execute_function callback raised PipelineStopRequested: {e!r}")
            raise
        except Exception as e:
            duration = time.perf_counter() - attempt_start_time
            logger.error(f"LLMExecutor: error when invoking execute_function. LLM {llm_model!r} and llm_executor_uuid: {llm_executor_uuid!r}: {e!r} traceback: {traceback.format_exc()}")
            return LLMAttempt(stage='execute', llm_model=llm_model, success=False, duration=duration, exception=e)

    def _check_stop_callback(self, last_attempt: LLMAttempt, start_time: float, attempt_index: int) -> None:
        """Checks the callback, if it exists, to see if execution should stop."""
        if self.should_stop_callback is None:
            return
        
        parameters = ShouldStopCallbackParameters(
            last_attempt=last_attempt,
            total_duration=time.perf_counter() - start_time,
            attempt_index=attempt_index,
            total_attempts=len(self.llm_models)
        )
        
        try:
            self.should_stop_callback(parameters)
        except PipelineStopRequested as e:
            logger.warning(f"Callback raised PipelineStopRequested. Aborting execution after attempt {attempt_index}: {e}")
            raise

    def _raise_final_exception(self) -> None:
        """Raise the final exception when no attempt succeeds."""
        rows = []
        for attempt_index, attempt in enumerate(self.attempts):
            status = "success" if attempt.success else "failed"
            rows.append(f" - Attempt {attempt_index} with {attempt.llm_model!r} {status} during '{attempt.stage}' stage: {attempt.exception!r}")
        error_summary = "\n".join(rows)
        raise Exception(f"Failed to run. Exhausted all LLMs. Failure summary:\n{error_summary}")
