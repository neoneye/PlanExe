"""
Cycle through the LLMs, if one fails, try the next one.

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
from typing import Any, Callable
from llama_index.core.llms.llm import LLM
from planexe.llm_factory import get_llm

logger = logging.getLogger(__name__)

class PlanTaskStop2(RuntimeError):
    """Raised when a pipeline task should be stopped by the callback."""
    pass

class ExecuteWithLLM:
    """
    Cycle through multiple LLMs. Start with the preferred LLM. 
    Fallback to the next LLM if the first one fails.
    If all LLMs fail, raise an exception.
    """
    def __init__(self, llm_models: list[str], pipeline_executor_callback: Callable[[float], bool]):
        self.llm_models = llm_models
        self.pipeline_executor_callback = pipeline_executor_callback

    def run(self, execute_function: Callable[[LLM], Any]):
        start_time: float = time.perf_counter()
        class_name = self.__class__.__name__
        attempt_count = len(self.llm_models)
        for index, llm_model in enumerate(self.llm_models, start=1):
            logger.info(f"Attempt {index} of {attempt_count}: Running {class_name} with LLM {llm_model!r}")
            try:
                llm = get_llm(llm_model)
                result = execute_function(llm)
            except Exception as e:
                logger.error(f"Error running {class_name} with LLM {llm_model!r}: {e}")
                continue
            duration: float = time.perf_counter() - start_time
            logger.info(f"Successfully ran {class_name} with LLM {llm_model!r}. Duration: {duration:.2f} seconds")
            # If a callback is provided by the pipeline executor, call it.
            if self.pipeline_executor_callback:
                should_stop = self.pipeline_executor_callback(duration)
                if should_stop:
                    logger.warning(f"Pipeline execution aborted by callback after task succeeded")
                    raise PlanTaskStop2(f"Pipeline execution aborted by callback after task succeeded")
            return result
        raise Exception(f"Failed to run {class_name} with any of the LLMs in the list: {self.llm_models!r}")
