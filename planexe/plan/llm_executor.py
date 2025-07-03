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
from typing import Any, Callable, Optional, List
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
    stage: str  # 'create' or 'execute'
    llm_model: LLMModelBase
    success: bool
    duration: float
    result: Optional[Any] = None
    exception: Optional[Exception] = None

class LLMExecutor:
    """
    Cycle through multiple LLMs. Start with the preferred LLM. 
    Fallback to the next LLM if the first one fails.
    If all LLMs fail, raise an exception.
    """
    def __init__(self, llm_models: list[LLMModelBase], should_stop_callback: Optional[Callable[[float], bool]] = None):
        self.llm_models = llm_models
        self.should_stop_callback = should_stop_callback
        self.attempts: List[LLMAttempt] = []

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def run(self, execute_function: Callable[[LLM], Any]):
        overall_start_time: float = time.perf_counter()
        
        # Reset attempts for each new run
        self.attempts = []

        for index, llm_model in enumerate(self.llm_models, start=1):
            attempt_start_time = time.perf_counter()
            logger.info(f"Attempt {index} of {len(self.llm_models)}: Running with LLM {llm_model!r}")
            
            # Stage 1: Create the LLM instance
            try:
                llm = llm_model.create_llm()
            except Exception as e:
                duration = time.perf_counter() - attempt_start_time
                logger.error(f"Error creating LLM {llm_model!r}: {e}")
                self.attempts.append(LLMAttempt(
                    stage='create',
                    llm_model=llm_model,
                    success=False,
                    duration=duration,
                    exception=e
                ))
                self.raise_exception_if_stop_callback_returns_true(overall_start_time)
                continue

            # Stage 2: Execute the function with the LLM
            try:
                result = execute_function(llm)
            except Exception as e:
                duration = time.perf_counter() - attempt_start_time
                logger.error(f"Error running with LLM {llm_model!r}: {e}")
                self.attempts.append(LLMAttempt(
                    stage='execute',
                    llm_model=llm_model,
                    success=False,
                    duration=duration,
                    exception=e
                ))
                continue

            duration = time.perf_counter() - attempt_start_time
            logger.info(f"Successfully ran with LLM {llm_model!r}. Duration: {duration:.2f} seconds")
            self.attempts.append(LLMAttempt(
                stage='execute',
                llm_model=llm_model,
                success=True,
                duration=duration,
                result=result
            ))
            self.raise_exception_if_stop_callback_returns_true(overall_start_time)
            return result
        
        # Build a detailed error message if all attempts failed
        error_summary = "\n".join(
            f"  - Attempt with {attempt.llm_model!r} failed during '{attempt.stage}' stage: {attempt.exception!r}"
            for attempt in self.attempts
        )
        raise Exception(f"Failed to run. Exhausted all LLMs. Failure summary:\n{error_summary}")

    def raise_exception_if_stop_callback_returns_true(self, start_time: float) -> None:
        """
        If there is no callback, do nothing.
        If the callback returns True, raise an exception to stop execution.
        If the callback returns False, continue execution.
        """
        if self.should_stop_callback is None:
            return

        total_duration = time.perf_counter() - start_time
        should_stop = self.should_stop_callback(total_duration)
        if should_stop:
            logger.warning(f"Execution aborted by callback after task succeeded")
            raise ExecutionAbortedError(f"Execution aborted by callback after task succeeded")